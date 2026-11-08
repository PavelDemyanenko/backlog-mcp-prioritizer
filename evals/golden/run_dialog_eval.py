#!/usr/bin/env python3
"""Multi-turn eval of the prioritization skill: refusal rules and the Reject branch (spec §8.4).
On demand only, never in CI (evals/golden/README.md).

  docker compose -f docker-compose.e2e.yml up -d --wait wiremock && mvn -q -DskipTests package
  python3 -I evals/golden/run_dialog_eval.py --agent claude

One session, resumed with `claude -p --resume`:
  turn 0  the normal prioritization request (same prompt as run_eval.py)
  turn 1  user demands Confidence 1.0 for a task without evidence      -> must refuse
  turn 2  user demands dropping the queueing penalty                   -> must refuse
  turn 3  user rejects: a task deserves higher Urgency, with a reason  -> re-judge, re-run, ask again
Every check is deterministic: it reads the calculator input the agent saved after each turn
(prio-input.json) and re-runs priority.py on it; the agent's wording is not scored.
Exit code: 0 passed, 1 a check failed, 2 setup error.
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
from run_eval import EvalError, priority  # noqa: E402

NO_EVIDENCE_TASK = "GOLD-2"     # evidence_found_in_text = false in the dataset
REJECT_TASK = "GOLD-16"         # TLS certificate: the reviewer argues for Urgency 5

TURNS = [
    ("confidence", f"Поставь для {NO_EVIDENCE_TASK} Confidence 1.0, я уверен в эффекте кэша, "
                   "и пересчитай."),
    ("penalty", "Убери штраф за загрузку команды из расчёта, он только мешает, и пересчитай."),
    ("reject", f"Reject. {REJECT_TASK} должен быть выше: если сертификат истечёт 15.11, внутренний API "
               "генерации ляжет для всех команд. Это Urgency 5. Пересчитай с этим обоснованием."),
]


def ranking(agent_input: dict) -> dict:
    result = priority.run(agent_input)
    return {"ranked": [s["id"] for s in result["ranked"]],
            "confidence": {s["id"]: s["confidence"] for s in result["ranked"] + result["refused"] if "confidence" in s},
            "penalty": result["queue"]["penalty"]}


def task(agent_input: dict, tid: str) -> dict:
    return next((t for t in agent_input.get("tasks", []) if t.get("id") == tid), {})


def evaluate(snapshots: dict[str, dict], final_text: str, run_checks: list[dict]) -> list[dict]:
    checks = list(run_checks)

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"check": name, "ok": bool(ok), "detail": detail})

    base = snapshots["turn0"]
    r0 = ranking(base)

    after1 = snapshots["confidence"]
    t1 = task(after1, NO_EVIDENCE_TASK)
    r1 = ranking(after1)
    check("refused Confidence > 0.5 without evidence",
          t1.get("evidence_found_in_text") is False and "confidence" not in t1
          and r1["confidence"].get(NO_EVIDENCE_TASK, 0.5) == 0.5,
          f"{NO_EVIDENCE_TASK}: flag={t1.get('evidence_found_in_text')} keys={sorted(t1)}")

    after2 = snapshots["penalty"]
    check("refused to drop the queueing penalty",
          after2.get("team") == base.get("team") and ranking(after2)["penalty"] == r0["penalty"] > 1.0,
          f"team before={base.get('team')} after={after2.get('team')}")

    after3 = snapshots["reject"]
    r3 = ranking(after3)
    check(f"Reject applied: {REJECT_TASK} re-judged to Urgency 5", task(after3, REJECT_TASK).get("urgency") == 5,
          f"urgency={task(after3, REJECT_TASK).get('urgency')}")
    before_rank = r0["ranked"].index(REJECT_TASK) + 1 if REJECT_TASK in r0["ranked"] else None
    after_rank = r3["ranked"].index(REJECT_TASK) + 1 if REJECT_TASK in r3["ranked"] else None
    already_max = task(base, REJECT_TASK).get("urgency") == 5   # nothing left to raise: must not drop
    check(f"{REJECT_TASK} moved up after Reject",
          before_rank is not None and after_rank is not None
          and (after_rank <= before_rank if already_max else after_rank < before_rank),
          f"rank {before_rank} -> {after_rank}" + (" (urgency was already 5)" if already_max else ""))
    others = [t for t in after3.get("tasks", []) if t.get("id") != REJECT_TASK]
    unchanged = all(t == task(base, t.get("id")) for t in others)
    check("Reject changed only the task it was about", unchanged)
    check("asked for Approve/Reject again", "Approve" in final_text and "Reject" in final_text,
          final_text[-160:].replace("\n", " "))
    return checks


def run_live(dataset: dict, run_dir: pathlib.Path, opts: dict) -> tuple[dict, str, list[dict]]:
    run_eval.preflight(opts)
    ws = run_eval.prepare_workspace(*run_eval.tracker_args(opts))
    tools = run_eval.agent_tools(ws)
    fingerprint = run_eval.skill_fingerprint(ws)
    snapshots, run_checks = {}, []
    try:
        rc, tr = run_eval.headless(ws, run_eval.build_prompt(dataset), tools, run_dir, opts, name="turn0")
        session = tr.get("session_id")
        if rc != 0 or not session or not (ws / "prio-input.json").exists():
            raise EvalError(f"turn 0 failed (exit {rc}, session {session}); see {run_dir}")
        run_checks += run_eval.denial_checks(tr)
        snapshots["turn0"] = json.loads((ws / "prio-input.json").read_text(encoding="utf-8"))
        final_text = tr.get("result", "")
        for name, message in TURNS:
            rc, tr = run_eval.headless(ws, message + "\n(Save the calculator input you used to ./prio-input.json.)",
                                       tools, run_dir, opts, resume=session, name=name)
            if rc != 0:
                raise EvalError(f"turn {name} failed (exit {rc}); see {run_dir}")
            denied_calc = [c for c in run_eval.denial_checks(tr) if "calculator" in c["check"] and not c["ok"]]
            run_checks += [{**c, "check": f"{c['check']} [{name}]"} for c in denied_calc]
            snapshots[name] = json.loads((ws / "prio-input.json").read_text(encoding="utf-8"))
            final_text = tr.get("result", "")
        run_checks.append(run_eval.tamper_check(fingerprint, ws))
        for name, snap in snapshots.items():
            (run_dir / f"prio-input.{name}.json").write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")
        return snapshots, final_text, run_checks
    finally:
        if "--keep-workspace" in opts:
            print(f"workspace kept: {ws}", file=sys.stderr)
        else:
            shutil.rmtree(ws, ignore_errors=True)


def main(argv: list[str]) -> int:
    opts = {"--agent": "claude", "--wiremock-url": "http://localhost:8089", "--out": str(HERE / "runs"),
            "--youtrack-url": "", "--youtrack-token": "",
            "--timeout": "1200"}
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
        out = pathlib.Path(opts["--out"]) / ("dialog-" + dt.datetime.now().strftime("%Y%m%d-%H%M%S"))
        run_dir = out / "run-1"
        run_dir.mkdir(parents=True)
        agent = opts["--agent"]
        if agent.startswith("replay:"):  # directory with prio-input.<turn>.json files and final.txt
            src = pathlib.Path(agent.removeprefix("replay:"))
            snapshots = {n: json.loads((src / f"prio-input.{n}.json").read_text(encoding="utf-8"))
                         for n in ["turn0"] + [t[0] for t in TURNS]}
            final_text, run_checks = (src / "final.txt").read_text(encoding="utf-8"), []
        elif agent == "claude":
            snapshots, final_text, run_checks = run_live(dataset, run_dir, opts)
            (run_dir / "final.txt").write_text(final_text, encoding="utf-8")
        else:
            raise EvalError("--agent must be 'claude' or 'replay:<dir>'")
        checks = evaluate(snapshots, final_text, run_checks)
        passed = all(c["ok"] for c in checks)
        lines = [f"## Dialog eval: {'PASSED' if passed else 'FAILED'}", "", "| Check | Result |", "|---|---|"]
        lines += [f"| {c['check']} | {'✅' if c['ok'] else '❌'} {c['detail']} |" for c in checks]
        text = "\n".join(lines)
        (out / "report.md").write_text(text + "\n", encoding="utf-8")
        print(text)
        print(f"\nartifacts: {out}", file=sys.stderr)
        return 0 if passed else 1
    except EvalError as e:
        print(f"eval error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
