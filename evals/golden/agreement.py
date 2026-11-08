#!/usr/bin/env python3
"""Inter-rater reliability for the Golden Dataset (spec §5: Cohen's kappa, weighted kappa).

  python3 -I evals/golden/agreement.py --validate labeling/expert-a.csv
  python3 -I evals/golden/agreement.py labeling/expert-a.csv labeling/expert-b.csv [...]

For every pair of experts:
  critical             Cohen's kappa (nominal)
  urgency, relevance   quadratic-weighted kappa (ordinal)
  impacts              quadratic-weighted kappa, all 7 metrics pooled, plus per metric
With > 2 experts the pairwise values are averaged (Light's kappa). Items left empty by either
rater are skipped pairwise. Also lists items needing adjudication.
Exit code: 0 ok, 1 validation errors.
"""
from __future__ import annotations

import csv
import itertools
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
IMPACTS = ["scaling", "code_quality", "latency", "reliability", "performance", "dev_speed", "tech_risk"]
ORDINAL = {"urgency": range(1, 6), "relevance": range(0, 4), **{f"impact_{m}": range(0, 6) for m in IMPACTS}}


def cohen_kappa(a: list, b: list, categories: list, weights: str | None = None) -> float | None:
    """Cohen's kappa; weights=None (nominal) or 'quadratic' (ordinal, categories in order)."""
    n = len(a)
    if n == 0:
        return None
    k = len(categories)
    idx = {c: i for i, c in enumerate(categories)}
    observed = [[0.0] * k for _ in range(k)]
    for x, y in zip(a, b):
        observed[idx[x]][idx[y]] += 1
    row = [sum(r) for r in observed]
    col = [sum(observed[i][j] for i in range(k)) for j in range(k)]

    def w(i: int, j: int) -> float:  # disagreement weight
        if weights == "quadratic":
            return ((i - j) / (k - 1)) ** 2 if k > 1 else 0.0
        return 0.0 if i == j else 1.0

    obs = sum(w(i, j) * observed[i][j] for i in range(k) for j in range(k)) / n
    exp = sum(w(i, j) * row[i] * col[j] for i in range(k) for j in range(k)) / (n * n)
    if exp == 0:
        return 1.0 if obs == 0 else 0.0
    return 1 - obs / exp


def interpret(kappa: float | None) -> str:  # Landis & Koch (1977)
    if kappa is None:
        return "n/a"
    for bound, label in ((0.0, "poor"), (0.2, "slight"), (0.4, "fair"), (0.6, "moderate"), (0.8, "substantial")):
        if kappa <= bound:
            return label
    return "almost perfect"


def load_ids() -> list[str]:
    return [t["id"] for t in json.loads((HERE / "dataset.json").read_text(encoding="utf-8"))["tasks"]]


def read_sheet(path: pathlib.Path, ids: list[str]) -> tuple[dict, list[str]]:
    errors, rows = [], {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        sample = f.read(2048)
        f.seek(0)
        reader = csv.DictReader(f, delimiter=";" if sample.count(";") >= sample.count(",") else ",")
        for line, r in enumerate(reader, start=2):
            tid = (r.get("task_id") or "").strip()
            if tid not in ids:
                errors.append(f"{path.name}:{line}: unknown task_id {tid!r}")
                continue
            crit = (r.get("critical") or "").strip().lower()
            if crit not in ("yes", "no"):
                errors.append(f"{path.name}:{line} {tid}: critical must be yes/no, got {crit!r}")
                continue
            rec = {"critical": crit}
            if crit == "yes" and not (r.get("critical_reason") or "").strip():
                errors.append(f"{path.name}:{line} {tid}: critical_reason is required when critical=yes")
            for field, allowed in ORDINAL.items():
                raw = (r.get(field) or "").strip()
                if raw == "":
                    if crit == "no":
                        errors.append(f"{path.name}:{line} {tid}: {field} is empty")
                    continue
                try:
                    value = int(raw)
                except ValueError:
                    errors.append(f"{path.name}:{line} {tid}: {field} must be an integer, got {raw!r}")
                    continue
                if value not in allowed:
                    errors.append(f"{path.name}:{line} {tid}: {field}={value} outside {allowed.start}..{allowed.stop - 1}")
                    continue
                rec[field] = value
            rows[tid] = rec
    missing = [t for t in ids if t not in rows]
    if missing:
        errors.append(f"{path.name}: missing tasks {', '.join(missing)}")
    return rows, errors


def pairs(sheets: dict, field: str) -> list[tuple[list, list]]:
    out = []
    for (_, a), (_, b) in itertools.combinations(sheets.items(), 2):
        common = [t for t in a if t in b and field in a[t] and field in b[t]]
        out.append(([a[t][field] for t in common], [b[t][field] for t in common]))
    return out


def mean_kappa(pair_values: list, categories: list, weights: str | None) -> float | None:
    values = [cohen_kappa(x, y, categories, weights) for x, y in pair_values]
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def report(sheets: dict) -> str:
    lines = ["| Field | κ | Agreement | Type |", "|---|---|---|---|"]

    def add(name: str, kappa: float | None, kind: str) -> None:
        lines.append(f"| {name} | {'n/a' if kappa is None else f'{kappa:.3f}'} | {interpret(kappa)} | {kind} |")

    add("critical", mean_kappa(pairs(sheets, "critical"), ["no", "yes"], None), "Cohen")
    add("urgency", mean_kappa(pairs(sheets, "urgency"), list(range(1, 6)), "quadratic"), "weighted")
    add("relevance", mean_kappa(pairs(sheets, "relevance"), list(range(0, 4)), "quadratic"), "weighted")
    pooled = []
    for i in range(len(pairs(sheets, "urgency"))):
        xs, ys = [], []
        for m in IMPACTS:
            x, y = pairs(sheets, f"impact_{m}")[i]
            xs += x
            ys += y
        pooled.append((xs, ys))
    add("impacts (pooled)", mean_kappa(pooled, list(range(0, 6)), "quadratic"), "weighted")
    for m in IMPACTS:
        add(f"  impact_{m}", mean_kappa(pairs(sheets, f"impact_{m}"), list(range(0, 6)), "quadratic"), "weighted")

    names = list(sheets)
    disagreements = []
    for tid in sheets[names[0]]:
        recs = {n: sheets[n].get(tid, {}) for n in names}
        crit = {r.get("critical") for r in recs.values()}
        if len(crit) > 1:
            pairs_txt = ", ".join(f"{n}={r.get('critical')}" for n, r in recs.items())
            disagreements.append(f"- {tid}: critical differs ({pairs_txt})")
            continue
        for field in ("relevance", "urgency"):
            vals = {n: r[field] for n, r in recs.items() if field in r}
            if len(vals) > 1 and max(vals.values()) - min(vals.values()) >= 2:
                disagreements.append(f"- {tid}: {field} " + ", ".join(f"{n}={v}" for n, v in vals.items()))
    lines += ["", f"Experts: {', '.join(names)}", "", "### Needs adjudication"]
    lines += disagreements or ["- none"]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    validate_only = "--validate" in argv
    files = [pathlib.Path(a) for a in argv[1:] if not a.startswith("--")]
    if not files or (not validate_only and len(files) < 2):
        print(__doc__, file=sys.stderr)
        return 1
    ids = load_ids()
    sheets, errors = {}, []
    for f in files:
        rows, errs = read_sheet(f, ids)
        sheets[f.stem.removeprefix("expert-")] = rows
        errors += errs
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    if validate_only:
        print(f"OK: {', '.join(str(f) for f in files)}")
        return 0
    print(report(sheets))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
