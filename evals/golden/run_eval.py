#!/usr/bin/env python3
"""Golden Dataset evaluation: runs the prioritization agent and gates on NDCG@k (spec §5, AGENTS.md §3).

  # live agent (Claude Code headless; costs tokens, needs WireMock + built jar):
  docker compose -f docker-compose.e2e.yml up -d --wait wiremock && mvn -q -DskipTests package
  python3 -I evals/golden/run_eval.py --agent claude --runs 3

  # re-score saved agent inputs without any LLM (CI of the pipeline itself, or old runs):
  python3 -I evals/golden/run_eval.py --agent replay:evals/golden/runs/<stamp>/run-1/prio-input.json

  # first live check before expert labels exist: rules + triage only, no NDCG / gold needed:
  python3 -I evals/golden/run_eval.py --agent claude --compliance-only

Against the real YouTrack sandbox instead of WireMock (same GOLD data, e2e/youtrack-sandbox):
  source e2e/youtrack-sandbox/.env && python3 -I evals/golden/run_eval.py --agent claude \
      --youtrack-url "$YOUTRACK_SANDBOX_URL"

Options: --gold PATH (default: gold-standard.json if present, else gold-standard.model-proxy.json,
         the project reference since 2026-11-08: labels by two other models)  --k 10  --min-ndcg 0.90
         --runs N  --model NAME  --wiremock-url URL  --out DIR  --keep-workspace

What is evaluated: the agent's *judgments*. The agent must save the exact calculator input it
used (prio-input.json); the harness re-runs priority.py on it, so ranking math is deterministic
and identical to production.

Gates (exit 1 if any fails): mean NDCG@k >= --min-ndcg; critical recall == 1.0 (a missed critical
item is never acceptable); every compliance check passes in every run.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import shutil
import statistics
import subprocess
import sys
import tempfile
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
SKILL = ROOT / "skills/backlog-prioritization-engine"
JAR = ROOT / "target/backlog-mcp-server.jar"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(SKILL / "scripts"))

import metrics  # noqa: E402
import priority  # noqa: E402

CALCULATOR = ".claude/skills/backlog-prioritization-engine/scripts/priority.py"


def agent_tools(ws: pathlib.Path) -> list[str]:
    """Allow-list for the headless agent. `Skill` is required to load the skill at all; the
    calculator is allowed by relative and absolute path (a chained command never matches)."""
    return ["Skill", "mcp__backlog__youtrack_query_backlog", "mcp__backlog__youtrack_count_issues",
            "mcp__backlog__adr_list", "mcp__backlog__adr_read",
            "Read", "Grep", "Glob", "Write", "Edit",
            f"Bash(python3 -I {CALCULATOR} *)", f"Bash(python3 -I {ws / CALCULATOR} *)"]


def skill_fingerprint(ws: pathlib.Path) -> dict[str, str]:
    """Hashes of every file of the skills in the workspace (the agent may edit prio-input.json, never the skill)."""
    import hashlib
    root = ws / ".claude/skills"
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


def tamper_check(before: dict[str, str], ws: pathlib.Path) -> dict:
    after = skill_fingerprint(ws)
    changed = sorted(k for k in before.keys() | after.keys() if before.get(k) != after.get(k))
    return {"check": "skill and calculator files untouched", "ok": not changed, "detail": f"changed: {changed}"}


def denial_checks(transcript: dict) -> list[dict]:
    """The run is only valid if the skill loaded and the agent itself ran the calculator."""
    denials = transcript.get("permission_denials") or []
    def denied(pred):
        return [d for d in denials if pred(d)]
    skill = denied(lambda d: d.get("tool_name") == "Skill")
    calc = denied(lambda d: d.get("tool_name") == "Bash" and "priority.py" in (d.get("tool_input") or {}).get("command", ""))
    return [
        {"check": "skill loaded (no Skill permission denial)", "ok": not skill, "detail": f"{len(skill)} denial(s)"},
        {"check": "agent ran the calculator itself (no denied priority.py call)", "ok": not calc,
         "detail": "; ".join((d.get("tool_input") or {}).get("command", "")[:120] for d in calc)},
    ]


class EvalError(RuntimeError):
    pass


# ---------------------------------------------------------------- agent prompt

def build_prompt(dataset: dict) -> str:
    uc = dataset["user_context"]
    est = "\n".join(f"  - {i}: opt {e['opt']}, real {e['real']}, pess {e['pess']}" for i, e in uc["estimates"].items())
    answers = "\n".join(f"  - {i}: {a['answer']}" for i, a in uc["triage_answers"].items())
    return f"""Prioritize the YouTrack backlog of project {dataset['project']} using the backlog-prioritization-engine skill.
Today is {dataset['as_of']}.

This is a non-interactive evaluation run: you cannot ask the user anything. These are the user's
answers to every question the skill would ask:
- Team capacity: {uc['capacity']} items in parallel.
- 3-point estimates from the team:
{est}
- Triage answers:
{answers}
- Any other triage candidate: not critical. Financial risk > 500 000 RUB: only where stated above.

Requirements for this run:
1. Follow the skill exactly, including the live In Progress count for utilization.
2. Save the exact calculator input JSON to ./prio-input.json and run the calculator as one plain
   command, nothing chained: python3 -I .claude/skills/backlog-prioritization-engine/scripts/priority.py prio-input.json
   (overwrite it if you re-run the calculator; the last version is evaluated).
3. Produce the report, then stop. Do not wait for Approve/Reject.
"""


# ---------------------------------------------------------------- runners

def wiremock_healthy(url: str, path: str = "/__admin/health") -> bool:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # never via HTTP_PROXY
    try:
        with opener.open(url.rstrip("/") + path, timeout=3) as r:
            return r.status == 200
    except OSError:
        return False


def tracker(opts: dict) -> tuple[str, str]:
    """YouTrack the agent talks to: WireMock fixtures (default) or the real sandbox (--youtrack-url)."""
    if opts.get("--youtrack-url"):
        token = opts.get("--youtrack-token") or os.environ.get("YOUTRACK_SANDBOX_TOKEN", "")
        if not token:
            raise EvalError("--youtrack-url needs --youtrack-token or YOUTRACK_SANDBOX_TOKEN "
                            "(source e2e/youtrack-sandbox/.env)")
        return opts["--youtrack-url"], token
    return opts["--wiremock-url"], "golden-token"


def tracker_args(opts: dict, skill: str = "backlog-prioritization-engine") -> tuple[str, str, str]:
    url, token = tracker(opts)
    return url, skill, token


def prepare_workspace(tracker_url: str, skill: str = "backlog-prioritization-engine",
                      token: str = "golden-token") -> pathlib.Path:
    """Throw-away workspace: one skill, the ADR fixture as docs/adr, an MCP config pointing at WireMock.
    Nothing from evals/ (dataset, expected outcomes) is copied."""
    ws = pathlib.Path(tempfile.mkdtemp(prefix="golden-eval-"))
    shutil.copytree(ROOT / "skills" / skill, ws / ".claude/skills" / skill,
                    ignore=shutil.ignore_patterns("__pycache__", "test_*.py", "example-input.json"))
    (ws / "docs/adr").mkdir(parents=True)
    for adr in (HERE / "adr").glob("*.md"):
        shutil.copy(adr, ws / "docs/adr" / adr.name)
    mcp = {"mcpServers": {"backlog": {
        "type": "stdio", "command": "java", "args": ["-jar", str(JAR)],
        "env": {"YOUTRACK_BASE_URL": tracker_url, "YOUTRACK_TOKEN": token,
                "ADR_DIR": str(ws / "docs/adr")}}}}
    (ws / "mcp.json").write_text(json.dumps(mcp, indent=2), encoding="utf-8")
    return ws


def preflight(opts: dict) -> None:
    if shutil.which("claude") is None:
        raise EvalError("`claude` CLI not found on PATH")
    if not JAR.exists():
        raise EvalError(f"{JAR} missing: run `mvn -q -DskipTests package`")
    if opts.get("--youtrack-url"):
        url = opts["--youtrack-url"]
        if not wiremock_healthy(url, "/api/config"):
            raise EvalError(f"YouTrack sandbox not reachable at {url}: "
                            "docker compose -f docker-compose.e2e.yml --profile sandbox up -d --wait youtrack")
        return
    url = opts["--wiremock-url"]
    if not wiremock_healthy(url):
        raise EvalError(f"WireMock not reachable at {url}: "
                        "docker compose -f docker-compose.e2e.yml up -d --wait wiremock")


def headless(ws: pathlib.Path, prompt: str, tools: list[str], run_dir: pathlib.Path, opts: dict,
             resume: str | None = None, name: str = "transcript") -> tuple[int, dict]:
    """Runs `claude -p` isolated in `ws` (optionally continuing session `resume`); saves transcript and
    stderr as <name>.json / <name>.stderr.log; returns (exit code, transcript)."""
    cmd = ["claude", "-p", prompt, "--output-format", "json",
           "--mcp-config", str(ws / "mcp.json"), "--strict-mcp-config",
           "--setting-sources", "project", "--allowedTools", *tools]
    if resume:
        cmd += ["--resume", resume]
    if opts.get("--model"):
        cmd += ["--model", opts["--model"]]
    proc = subprocess.run(cmd, cwd=ws, capture_output=True, text=True, timeout=int(opts["--timeout"]))
    (run_dir / f"{name}.json").write_text(proc.stdout, encoding="utf-8")
    (run_dir / ("agent.stderr.log" if name == "transcript" else f"{name}.stderr.log")).write_text(proc.stderr, encoding="utf-8")
    try:
        transcript = json.loads(proc.stdout)
    except json.JSONDecodeError:
        transcript = {}
    return proc.returncode, transcript


def run_claude(dataset: dict, run_dir: pathlib.Path, opts: dict) -> dict:
    preflight(opts)
    ws = prepare_workspace(*tracker_args(opts))
    fingerprint = skill_fingerprint(ws)
    try:
        returncode, transcript = headless(ws, build_prompt(dataset), agent_tools(ws), run_dir, opts)
        produced = ws / "prio-input.json"
        if returncode != 0 or not produced.exists():
            raise EvalError(f"agent run failed (exit {returncode}, prio-input.json "
                            f"{'present' if produced.exists() else 'missing'}); see {run_dir}")
        shutil.copy(produced, run_dir / "prio-input.json")
        agent_input = json.loads(produced.read_text(encoding="utf-8"))
        agent_input["__run_checks__"] = denial_checks(transcript) + [tamper_check(fingerprint, ws)]
        return agent_input
    finally:
        if "--keep-workspace" in opts:
            print(f"workspace kept: {ws}", file=sys.stderr)
        else:
            shutil.rmtree(ws, ignore_errors=True)


def run_replay(source: pathlib.Path, run_dir: pathlib.Path) -> dict:
    shutil.copy(source, run_dir / "prio-input.json")
    return json.loads(source.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- evaluation

def expected_critical(dataset: dict) -> set[str]:
    """Critical set implied by the dataset rules + user answers (used when no gold exists yet)."""
    auto = {t["id"] for t in dataset["tasks"] if t["expected"]["triage"] == "auto_critical"}
    confirmed = {i for i, a in dataset["user_context"]["triage_answers"].items() if a["critical"]}
    return auto | confirmed


def evaluate_run(agent_input: dict, dataset: dict, gold: dict | None, k: int) -> dict:
    run_checks = agent_input.pop("__run_checks__", [])   # live runs only; replays have no transcript
    checks = metrics.compliance(agent_input, dataset) + run_checks
    try:
        result = priority.run(agent_input)
    except priority.InputError as e:
        return {"error": f"calculator rejected the agent's input: {e}", "compliance": checks}
    ranked = [s["id"] for s in result["ranked"]]
    agent_critical = {s["id"] for s in result["critical"]}
    if gold is None:
        return {"ranking": ranked, "ndcg": None, "unranked_relevant": [],
                "triage": metrics.triage_accuracy(agent_critical, expected_critical(dataset)),
                "compliance": checks}
    rankable = metrics.rankable_tasks(dataset, gold)
    relevance = {i: gold["tasks"][i]["relevance"] for i in rankable}
    return {
        "ranking": ranked,
        "ndcg": metrics.ndcg_at_k(ranked, relevance, k),
        "unranked_relevant": sorted(i for i in rankable if i not in ranked and relevance[i] > 0),
        "triage": metrics.triage_accuracy(agent_critical, {i for i, g in gold["tasks"].items() if g["critical"]}),
        "compliance": checks,
    }


def summarize(runs: list[dict], k: int, min_ndcg: float, compliance_only: bool = False) -> dict:
    ok_runs = [r for r in runs if "error" not in r]
    ndcgs = [r["ndcg"] for r in ok_runs if r["ndcg"] is not None]
    mean_ndcg = statistics.mean(ndcgs) if ndcgs and len(ok_runs) == len(runs) else None
    recall = min((r["triage"]["recall"] for r in ok_runs), default=0.0)
    failed_checks = sorted({c["check"] for r in runs for c in r["compliance"] if not c["ok"]})
    gates = {} if compliance_only else {f"mean NDCG@{k} >= {min_ndcg}": mean_ndcg is not None and mean_ndcg >= min_ndcg}
    gates.update({
        "critical recall == 1.0 in every run": len(ok_runs) == len(runs) and recall == 1.0,
        "all compliance checks pass": not failed_checks and len(ok_runs) == len(runs),
    })
    return {"mean_ndcg": mean_ndcg, "min_ndcg": min(ndcgs) if ndcgs else None,
            "asi": metrics.stability_index([r["ranking"] for r in ok_runs]),
            "min_critical_recall": recall, "failed_checks": failed_checks,
            "gates": gates, "passed": all(gates.values())}


def report(summary: dict, runs: list[dict], k: int) -> str:
    fmt = lambda v: "n/a" if v is None else f"{v:.3f}"
    lines = [f"## Golden eval: {'PASSED' if summary['passed'] else 'FAILED'}", "",
             "| Gate | Result |", "|---|---|"]
    lines += [f"| {g} | {'✅' if ok else '❌'} |" for g, ok in summary["gates"].items()]
    lines += ["", f"- mean NDCG@{k}: {fmt(summary['mean_ndcg'])} (min {fmt(summary['min_ndcg'])})",
              f"- ASI (mean pairwise Kendall tau, {len(runs)} run(s)): {fmt(summary['asi'])}",
              f"- min critical recall: {summary['min_critical_recall']:.2f}", ""]
    for n, r in enumerate(runs, 1):
        lines.append(f"### Run {n}")
        if "error" in r:
            lines.append(f"- ERROR: {r['error']}")
        else:
            t = r["triage"]
            lines += [f"- NDCG@{k}: {fmt(r['ndcg'])}; ranking: {', '.join(r['ranking'])}",
                      f"- relevant but not ranked: {', '.join(r['unranked_relevant']) or 'none'}",
                      f"- triage: precision {t['precision']:.2f}, recall {t['recall']:.2f}, "
                      f"missed {t['missed'] or 'none'}, false alarms {t['false_alarms'] or 'none'}"]
        for c in r["compliance"]:
            if not c["ok"]:
                lines.append(f"- ❌ {c['check']}: {c['detail']}")
        lines.append("")
    return "\n".join(lines)


def parse(argv: list[str]) -> dict:
    default_gold = HERE / "gold-standard.json"
    if not default_gold.exists():
        default_gold = HERE / "gold-standard.model-proxy.json"
    opts = {"--gold": str(default_gold), "--k": "10", "--min-ndcg": "0.90", "--runs": "1",
            "--agent": "claude", "--wiremock-url": "http://localhost:8089", "--out": str(HERE / "runs"),
            "--youtrack-url": "", "--youtrack-token": "",
            "--timeout": "1200"}
    it = iter(argv[1:])
    for a in it:
        if a in ("--keep-workspace", "--compliance-only"):
            opts[a] = "1"
        elif a.startswith("--") and a in opts or a == "--model":
            opts[a] = next(it)
        else:
            raise EvalError(f"unknown argument {a}\n{__doc__}")
    return opts


def main(argv: list[str]) -> int:
    try:
        opts = parse(argv)
        dataset = json.loads((HERE / "dataset.json").read_text(encoding="utf-8"))
        compliance_only = "--compliance-only" in opts
        gold = None
        if not compliance_only:
            gold_path = pathlib.Path(opts["--gold"])
            if not gold_path.exists():
                raise EvalError(f"{gold_path} not found: build it from expert labels with consensus.py "
                                "(or use --compliance-only)")
            gold = json.loads(gold_path.read_text(encoding="utf-8"))
            if gold.get("dataset_version") != dataset["version"]:
                raise EvalError(f"gold standard is for dataset {gold.get('dataset_version')}, "
                                f"dataset is {dataset['version']}")
        k = int(opts["--k"])

        out = pathlib.Path(opts["--out"]) / dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        agent = opts["--agent"]
        sources = []
        if agent.startswith("replay:"):
            sources = [pathlib.Path(p) for p in agent.removeprefix("replay:").split(",")]
        elif agent != "claude":
            raise EvalError("--agent must be 'claude' or 'replay:<file>[,<file>...]'")
        n_runs = len(sources) if sources else int(opts["--runs"])

        runs = []
        for n in range(n_runs):
            run_dir = out / f"run-{n + 1}"
            run_dir.mkdir(parents=True)
            try:
                agent_input = run_replay(sources[n], run_dir) if sources else run_claude(dataset, run_dir, opts)
                runs.append(evaluate_run(agent_input, dataset, gold, k))
            except EvalError as e:
                runs.append({"error": str(e), "compliance": []})
        summary = summarize(runs, k, float(opts["--min-ndcg"]), compliance_only)
        text = report(summary, runs, k)
        if gold and gold.get("source") == "model-proxy":
            summary["gold_source"] = "model-proxy"
            text = ("> Reference = **model labels** (" + ", ".join(gold.get("experts", [])) + "), not human "
                    "experts: NDCG measures agreement with other models.\n\n" + text)
        (out / "report.md").write_text(text + "\n", encoding="utf-8")
        (out / "results.json").write_text(json.dumps({"summary": summary, "runs": runs}, indent=2,
                                                     ensure_ascii=False) + "\n", encoding="utf-8")
        print(text)
        print(f"\nartifacts: {out}", file=sys.stderr)
        return 0 if summary["passed"] else 1
    except EvalError as e:
        print(f"eval error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
