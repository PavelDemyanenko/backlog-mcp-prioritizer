#!/usr/bin/env python3
"""Golden eval for the adr-custodian skill (Mode A: backlog vs ADRs). On demand only (ADR-0006).

  docker compose -f docker-compose.e2e.yml up -d --wait wiremock && mvn -q -DskipTests package
  python3 -I evals/golden/run_custodian_eval.py --agent claude
  python3 -I evals/golden/run_custodian_eval.py --agent replay:evals/golden/runs/<stamp>/run-1/adr-findings.json

The agent saves its findings as JSON (adr-findings.json); expectations come from dataset.json:
  BROKEN_LINK  required for every adr_refs entry with status "missing"   (GOLD-23 -> 0031)
  NEEDS_ADR    required for every architectural task without any ADR ref (GOLD-8)
  clean        tasks whose ADR is accepted get no finding                (GOLD-7)
  CONFLICT     none exist in the dataset: any CONFLICT is a false positive
Extra NEEDS_ADR on other tasks are reported, not failed (a judgment call).
Live runs also fail on a denied Skill call or on any file written to docs/adr (read-only mode).
Exit code: 0 passed, 1 a gate failed, 2 setup error.
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import shutil
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import run_eval  # noqa: E402
from run_eval import EvalError  # noqa: E402

SKILL = "adr-custodian"
FINDING_TYPES = {"BROKEN_LINK", "SUPERSEDED_LINK", "NOT_ACCEPTED", "NEEDS_ADR", "CONFLICT"}
TOOLS = ["Skill", "mcp__backlog__adr_list", "mcp__backlog__adr_read", "mcp__backlog__youtrack_query_backlog",
         "Read", "Grep", "Glob", "Write"]


def build_prompt(dataset: dict) -> str:
    return f"""Use the adr-custodian skill in Mode A: check the backlog of YouTrack project {dataset['project']}
(query: project: {dataset['project']} State: Submitted, Open, {{To Do}}) against the project's ADRs.

This is a non-interactive evaluation run: do not ask questions and do not draft or write any ADR.
Produce the Mode A report. Also save every finding from your table to ./adr-findings.json as a JSON
array of objects {{"task": "<id>", "finding": "<type>", "adr": "<4-digit id or null>", "quote": "<basis>"}},
one object per row. Write [] if there are no findings."""


def expectations(dataset: dict) -> dict:
    required, clean = set(), set()
    for t in dataset["tasks"]:
        e = t["expected"]
        for ref in e["adr_refs"]:
            if ref["status"] == "missing":
                required.add((t["id"], "BROKEN_LINK"))
        if e["adr"] == "missing" and not e["adr_refs"]:
            required.add((t["id"], "NEEDS_ADR"))
        if e["adr"] == "present":
            clean.add(t["id"])
    return {"required": required, "clean": clean}


def evaluate(findings, dataset: dict, run_checks: list[dict] | None = None) -> dict:
    checks = list(run_checks or [])

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"check": name, "ok": bool(ok), "detail": detail})

    valid = isinstance(findings, list) and all(isinstance(f, dict) and f.get("finding") in FINDING_TYPES
                                              and f.get("task") for f in findings)
    check("findings file is a list of known finding types", valid,
          "" if valid else f"got {json.dumps(findings, ensure_ascii=False)[:200]}")
    if not valid:
        return {"checks": checks, "passed": False}

    exp = expectations(dataset)
    got = {(f["task"], f["finding"]) for f in findings}
    missing = sorted(exp["required"] - got)
    check("required findings reported (BROKEN_LINK, NEEDS_ADR)", not missing, f"missing: {missing}")
    noisy = sorted({f["task"] for f in findings} & exp["clean"])
    check("tasks backed by an accepted ADR have no findings", not noisy, f"tasks: {noisy}")
    conflicts = [f["task"] for f in findings if f["finding"] == "CONFLICT"]
    check("no false CONFLICT (dataset has none)", not conflicts, f"tasks: {conflicts}")
    unquoted = [f["task"] for f in findings if f["finding"] == "CONFLICT" and not (f.get("quote") or "").strip()]
    check("every CONFLICT quotes its ADR", not unquoted, f"tasks: {unquoted}")

    extra = sorted(t for t, kind in got if kind == "NEEDS_ADR" and (t, kind) not in exp["required"])
    return {"checks": checks, "passed": all(c["ok"] for c in checks), "extra_needs_adr": extra,
            "findings": sorted(got)}


def run_live(dataset: dict, run_dir: pathlib.Path, opts: dict) -> tuple[object, list[dict]]:
    run_eval.preflight(opts)
    ws = run_eval.prepare_workspace(*run_eval.tracker_args(opts, SKILL))
    adr_before = sorted(p.name for p in (ws / "docs/adr").iterdir())
    try:
        returncode, transcript = run_eval.headless(ws, build_prompt(dataset), TOOLS, run_dir, opts)
        produced = ws / "adr-findings.json"
        if returncode != 0 or not produced.exists():
            raise EvalError(f"agent run failed (exit {returncode}, adr-findings.json "
                            f"{'present' if produced.exists() else 'missing'}); see {run_dir}")
        shutil.copy(produced, run_dir / "adr-findings.json")
        denied_skill = [d for d in transcript.get("permission_denials") or [] if d.get("tool_name") == "Skill"]
        adr_after = sorted(p.name for p in (ws / "docs/adr").iterdir())
        run_checks = [
            {"check": "skill loaded (no Skill permission denial)", "ok": not denied_skill,
             "detail": f"{len(denied_skill)} denial(s)"},
            {"check": "read-only: no ADR file written", "ok": adr_after == adr_before,
             "detail": f"new: {sorted(set(adr_after) - set(adr_before))}"},
        ]
        return json.loads(produced.read_text(encoding="utf-8")), run_checks
    finally:
        if "--keep-workspace" in opts:
            print(f"workspace kept: {ws}", file=sys.stderr)
        else:
            shutil.rmtree(ws, ignore_errors=True)


def report(result: dict) -> str:
    lines = [f"## Custodian eval: {'PASSED' if result['passed'] else 'FAILED'}", "", "| Check | Result |", "|---|---|"]
    lines += [f"| {c['check']} | {'✅' if c['ok'] else '❌ ' + c['detail']} |" for c in result["checks"]]
    if "findings" in result:
        lines += ["", "Findings: " + ", ".join(f"{t} {k}" for t, k in result["findings"]),
                  "Extra NEEDS_ADR (judgment, not failed): " + (", ".join(result["extra_needs_adr"]) or "none")]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    opts = {"--agent": "claude", "--wiremock-url": "http://localhost:8089", "--out": str(HERE / "runs"),
            "--youtrack-url": "", "--youtrack-token": "",
            "--timeout": "900"}
    it = iter(argv[1:])
    try:
        for a in it:
            if a == "--keep-workspace":
                opts[a] = "1"
            elif a in opts or a == "--model":
                opts[a] = next(it)
            else:
                raise EvalError(f"unknown argument {a}\n{__doc__}")
        dataset = json.loads((HERE / "dataset.json").read_text(encoding="utf-8"))
        run_dir = pathlib.Path(opts["--out"]) / ("custodian-" + dt.datetime.now().strftime("%Y%m%d-%H%M%S")) / "run-1"
        run_dir.mkdir(parents=True)
        agent = opts["--agent"]
        if agent.startswith("replay:"):
            src = pathlib.Path(agent.removeprefix("replay:"))
            shutil.copy(src, run_dir / "adr-findings.json")
            findings, run_checks = json.loads(src.read_text(encoding="utf-8")), []
        elif agent == "claude":
            findings, run_checks = run_live(dataset, run_dir, opts)
        else:
            raise EvalError("--agent must be 'claude' or 'replay:<file>'")
        result = evaluate(findings, dataset, run_checks)
        text = report(result)
        (run_dir.parent / "report.md").write_text(text + "\n", encoding="utf-8")
        (run_dir.parent / "results.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                                                     encoding="utf-8")
        print(text)
        print(f"\nartifacts: {run_dir.parent}", file=sys.stderr)
        return 0 if result["passed"] else 1
    except EvalError as e:
        print(f"eval error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
