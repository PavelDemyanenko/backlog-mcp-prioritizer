#!/usr/bin/env python3
"""Builds every Golden Dataset artifact from the single source of truth `dataset.json`.

  python3 -I evals/golden/build.py           write artifacts
  python3 -I evals/golden/build.py --check   exit 1 if any artifact is stale (CI)

Artifacts:
  e2e/wiremock/__files/golden/backlog.json   YouTrack-shaped backlog (project GOLD)
  e2e/wiremock/__files/golden/wip.json       YouTrack-shaped In Progress items (for rho)
  e2e/wiremock/mappings/golden-youtrack.json WireMock routes for the two queries
  evals/golden/labeling/tasks.md             task cards for experts (no expected outcomes!)
  evals/golden/labeling/template.csv         labeling sheet (UTF-8 BOM, ';' for Excel ru-RU)
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
IMPACTS = ["scaling", "code_quality", "latency", "reliability", "performance", "dev_speed", "tech_risk"]
CSV_COLUMNS = (["task_id", "summary", "critical", "critical_reason"]
               + [f"impact_{m}" for m in IMPACTS]
               + ["urgency", "relevance", "comment"])


def epoch_noon_utc(date: str) -> int:
    d = dt.date.fromisoformat(date)
    return int(dt.datetime(d.year, d.month, d.day, 12, tzinfo=dt.timezone.utc).timestamp() * 1000)


def enum(t: str, name: str) -> dict:
    return {"$type": t, "name": name}


def youtrack_issue(task: dict) -> dict:
    fields = [
        {"$type": "StateIssueCustomField", "name": "State", "value": enum("StateBundleElement", task["state"])},
        {"$type": "SingleEnumIssueCustomField", "name": "Type", "value": enum("EnumBundleElement", task["type"])},
        {"$type": "SingleEnumIssueCustomField", "name": "Priority", "value": enum("EnumBundleElement", task["priority"])},
        {"$type": "MultiOwnedIssueCustomField", "name": "Subsystem",
         "value": [enum("OwnedBundleElement", s) for s in task["subsystem"]]},
        {"$type": "DateIssueCustomField", "name": "Due Date",
         "value": epoch_noon_utc(task["due_date"]) if task["due_date"] else None},
        {"$type": "SimpleIssueCustomField", "name": "Story points", "value": task["story_points"]},
    ]
    return {"$type": "Issue", "idReadable": task["id"], "summary": task["summary"],
            "description": task["description"], "tags": [{"name": t} for t in task["tags"]],
            "customFields": fields}


def wip_issue(item: dict) -> dict:
    return youtrack_issue({**item, "description": "", "state": "In Progress", "type": "Task",
                           "priority": "Normal", "tags": [], "subsystem": [], "due_date": None,
                           "story_points": 3})


def mappings() -> dict:
    auth = {"Authorization": {"matches": "Bearer .+"}}
    return {"mappings": [
        {"name": "Golden: WIP count for rho (project GOLD, In Progress)", "priority": 2,
         "request": {"method": "GET", "urlPath": "/api/issues", "headers": auth,
                     "queryParameters": {"query": {"matches": "(?s).*project:\\s*GOLD\\b.*In Progress.*"}}},
         "response": {"status": 200, "headers": {"Content-Type": "application/json"},
                      "bodyFileName": "golden/wip.json"}},
        {"name": "Golden: backlog (project GOLD)", "priority": 3,
         "request": {"method": "GET", "urlPath": "/api/issues", "headers": auth,
                     "queryParameters": {"query": {"matches": "(?s)(?!.*In Progress).*project:\\s*GOLD\\b.*"}}},
         "response": {"status": 200, "headers": {"Content-Type": "application/json"},
                      "bodyFileName": "golden/backlog.json"}},
    ]}


def cards(ds: dict) -> str:
    uc = ds["user_context"]
    out = [f"# Golden Dataset v{ds['version']}: карточки задач", "",
           f"**Дата оценки:** {ds['as_of']}  ",
           f"**Контекст:** {ds['context']}  ",
           f"**Загрузка команды:** {len(ds['wip'])} задач в работе при ёмкости {uc['capacity']} "
           f"(ρ = {len(ds['wip']) / uc['capacity']:.2f}).", "",
           "Шкалы и правила: `LABELING.md`. Заполняйте `template.csv` (копия на эксперта).", ""]
    for t in ds["tasks"]:
        sp = "не оценено" if t["story_points"] is None else f"{t['story_points']:g} SP"
        out += [f"## {t['id']}. {t['summary']}", "",
                f"- Тип: {t['type']} · Приоритет в трекере: {t['priority']} · Статус: {t['state']}",
                f"- Метки: {', '.join(t['tags']) or '—'} · Подсистема: {', '.join(t['subsystem']) or '—'}",
                f"- Срок: {t['due_date'] or '—'} · Оценка: {sp}"]
        if t["id"] in uc["estimates"]:
            e = uc["estimates"][t["id"]]
            out.append(f"- Трёхточечная оценка от команды: опт. {e['opt']}, реал. {e['real']}, песс. {e['pess']}")
        if t["id"] in uc["triage_answers"]:
            out.append(f"- Дополнительно известно: {uc['triage_answers'][t['id']]['answer']}")
        out += ["", f"> {t['description']}", ""]
    return "\n".join(out)


def template(ds: dict) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\r\n")
    w.writerow(CSV_COLUMNS)
    for t in ds["tasks"]:
        w.writerow([t["id"], t["summary"]] + [""] * (len(CSV_COLUMNS) - 2))
    return "﻿" + buf.getvalue()


def validate(ds: dict) -> None:
    ids = [t["id"] for t in ds["tasks"]]
    assert len(ids) == len(set(ids)), "duplicate task ids"
    for t in ds["tasks"]:
        for k in ("summary", "description", "state", "type", "priority", "tags", "subsystem", "expected"):
            assert k in t, f"{t['id']}: missing {k}"
        assert t["expected"]["triage"] in ("none", "candidate", "auto_critical"), t["id"]
        if t["due_date"]:
            dt.date.fromisoformat(t["due_date"])
    for tid in list(ds["user_context"]["estimates"]) + list(ds["user_context"]["triage_answers"]):
        assert tid in ids, f"user_context references unknown {tid}"


def artifacts(ds: dict) -> dict[pathlib.Path, str]:
    dump = lambda o: json.dumps(o, ensure_ascii=False, indent=2) + "\n"
    return {
        ROOT / "e2e/wiremock/__files/golden/backlog.json": dump([youtrack_issue(t) for t in ds["tasks"]]),
        ROOT / "e2e/wiremock/__files/golden/wip.json": dump([wip_issue(w) for w in ds["wip"]]),
        ROOT / "e2e/wiremock/mappings/golden-youtrack.json": dump(mappings()),
        HERE / "labeling/tasks.md": cards(ds) + "\n",
        HERE / "labeling/template.csv": template(ds),
    }


def main(argv: list[str]) -> int:
    ds = json.loads((HERE / "dataset.json").read_text(encoding="utf-8"))
    validate(ds)
    stale = []
    for path, content in artifacts(ds).items():
        current = path.read_bytes().decode("utf-8") if path.exists() else None  # keep \r\n of the CSV
        if current == content:
            continue
        if "--check" in argv:
            stale.append(path.relative_to(ROOT))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8", newline="")
            print(f"wrote {path.relative_to(ROOT)}", file=sys.stderr)
    if stale:
        print("stale artifacts, run evals/golden/build.py: " + ", ".join(map(str, stale)), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
