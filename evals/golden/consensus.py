#!/usr/bin/env python3
"""Builds the Gold Standard from expert sheets (after adjudication).

  python3 -I evals/golden/consensus.py labeling/expert-*.csv [--adjudication labeling/adjudication.csv]
                                       [--min-kappa 0.6] [--out evals/golden/gold-standard.json]

Refuses (exit 1) when
  * a sheet is invalid (same validation as agreement.py),
  * relevance agreement is too low (quadratic-weighted kappa < --min-kappa): the labels are not a
    reliable reference, fix the guide and relabel instead of averaging noise,
  * an item needing adjudication (critical differs, relevance/urgency differ by >= 2) has no
    decision in the adjudication file.

Adjudication CSV (';'): task_id;field;value;note  with field in critical|relevance|urgency.
Consensus: critical = unanimous or adjudicated; relevance/urgency/impacts = mean of experts
(or the adjudicated value).

--proxy  labels come from models, not experts: disagreements are resolved automatically
         (critical = yes if any rater says yes; relevance/urgency = mean) and listed in the output,
         which is marked "source": "model-proxy". Never use proxy labels as the expert reference.
"""
from __future__ import annotations

import csv
import json
import pathlib
import statistics
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import agreement  # noqa: E402


def read_adjudication(path: pathlib.Path | None) -> dict[tuple[str, str], str]:
    if path is None:
        return {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        return {(r["task_id"].strip(), r["field"].strip()): r["value"].strip()
                for r in csv.DictReader(f, delimiter=";")}


def build(sheets: dict, adjudication: dict, min_kappa: float, dataset_version: str,
          proxy: bool = False) -> tuple[dict | None, list[str]]:
    problems, auto_resolved = [], []
    kappa = agreement.mean_kappa(agreement.pairs(sheets, "relevance"), list(range(4)), "quadratic")
    if kappa is None or kappa < min_kappa:
        problems.append(f"relevance weighted kappa {kappa if kappa is None else round(kappa, 3)} < {min_kappa}: "
                        "labels are not reliable enough to be a reference")

    names = list(sheets)
    gold = {}
    for tid in sheets[names[0]]:
        recs = [sheets[n][tid] for n in names]
        crit_votes = {r["critical"] for r in recs}
        if (tid, "critical") in adjudication:
            critical = adjudication[(tid, "critical")].lower() == "yes"
        elif len(crit_votes) == 1:
            critical = crit_votes.pop() == "yes"
        elif proxy:
            critical = True
            auto_resolved.append(f"{tid}: critical differs -> yes (safety-first)")
        else:
            problems.append(f"{tid}: critical differs, needs adjudication")
            continue
        entry = {"critical": critical}
        if not critical:
            for field in ["relevance", "urgency"] + [f"impact_{m}" for m in agreement.IMPACTS]:
                values = [r[field] for r in recs if field in r]
                if (tid, field) in adjudication:
                    entry[field] = float(adjudication[(tid, field)])
                elif not values:
                    problems.append(f"{tid}: no expert scored {field} (all marked it critical?)")
                    break
                elif field in ("relevance", "urgency") and max(values) - min(values) >= 2 and not proxy:
                    problems.append(f"{tid}: {field} {values} differ by >= 2, needs adjudication")
                    break
                else:
                    if field in ("relevance", "urgency") and max(values) - min(values) >= 2:
                        auto_resolved.append(f"{tid}: {field} {values} -> mean")
                    entry[field] = round(statistics.mean(values), 3)
        gold[tid] = entry
    if problems:
        return None, problems
    out = {"dataset_version": dataset_version, "source": "model-proxy" if proxy else "experts",
           "experts": names, "relevance_kappa": round(kappa, 4), "tasks": gold}
    if proxy:
        out["auto_resolved"] = auto_resolved
    return out, []


def main(argv: list[str]) -> int:
    args, opts, it = [], {}, iter(argv[1:])
    for a in it:
        if a == "--proxy":
            opts[a] = "1"
        elif a.startswith("--"):
            opts[a] = next(it)
        else:
            args.append(pathlib.Path(a))
    if len(args) < 2:
        print(__doc__, file=sys.stderr)
        return 1
    ids = agreement.load_ids()
    sheets, errors = {}, []
    for f in args:
        rows, errs = agreement.read_sheet(f, ids)
        sheets[f.stem.removeprefix("expert-")] = rows
        errors += errs
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    adj = opts.get("--adjudication")
    dataset = json.loads((HERE / "dataset.json").read_text(encoding="utf-8"))
    gold, problems = build(sheets, read_adjudication(pathlib.Path(adj) if adj else None),
                           float(opts.get("--min-kappa", 0.6)), dataset["version"], proxy="--proxy" in opts)
    if problems:
        print("Gold standard NOT written:\n" + "\n".join(f"- {p}" for p in problems), file=sys.stderr)
        return 1
    out = pathlib.Path(opts.get("--out", HERE / "gold-standard.json"))
    out.write_text(json.dumps(gold, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out} ({len(gold['tasks'])} tasks, experts: {', '.join(gold['experts'])}, "
          f"relevance kappa {gold['relevance_kappa']})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
