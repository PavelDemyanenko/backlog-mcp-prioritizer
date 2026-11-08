"""Ranking quality, triage accuracy, rule compliance and stability for Golden Dataset runs.

NDCG@k uses exponential gain and logarithmic discount (spec §5):
    DCG@k = sum_{i=1..k} (2^rel_i - 1) / log2(i + 1),   NDCG@k = DCG@k / IDCG@k
rel = gold-standard relevance (mean expert grade 0..3, may be fractional).
"""
from __future__ import annotations

import itertools
import math


# ---------------------------------------------------------------- ranking

def dcg(gains: list[float], k: int) -> float:
    return sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(gains[:k]))


def ndcg_at_k(ranked_ids: list[str], relevance: dict[str, float], k: int) -> float | None:
    """Items missing from `relevance` count as gain 0 (they should not be in the ranking).
    Relevant items the agent did not rank simply earn nothing (they lower DCG, not IDCG)."""
    ideal = dcg(sorted(relevance.values(), reverse=True), k)
    if ideal == 0:
        return None
    return dcg([relevance.get(i, 0.0) for i in ranked_ids], k) / ideal


def rankable_tasks(dataset: dict, gold: dict) -> set[str]:
    """Gold non-critical tasks that the method's rules allow to be ranked at all:
    an estimate exists (story points or user 3-point) and the 3-point spread is <= 1.0."""
    estimates = dataset["user_context"]["estimates"]
    out = set()
    for t in dataset["tasks"]:
        g = gold["tasks"].get(t["id"])
        if g is None or g["critical"]:
            continue
        e = estimates.get(t["id"])
        if e and (e["pess"] - e["opt"]) / e["real"] > 1.0:
            continue
        if t["story_points"] is None and not e:
            continue
        out.add(t["id"])
    return out


def kendall_tau(a: list[str], b: list[str]) -> float | None:
    """Kendall tau-b on the items present in both rankings (no ties within a ranking)."""
    common = [x for x in a if x in set(b)]
    if len(common) < 2:
        return None
    pos_b = {x: i for i, x in enumerate(b)}
    concordant = discordant = 0
    for x, y in itertools.combinations(common, 2):  # x before y in a
        if pos_b[x] < pos_b[y]:
            concordant += 1
        else:
            discordant += 1
    return (concordant - discordant) / (concordant + discordant)


def stability_index(rankings: list[list[str]]) -> float | None:
    """ASI (Agent Stability Index): mean pairwise Kendall tau between repeated runs, in [-1, 1].
    1.0 = identical order every run."""
    taus = [kendall_tau(a, b) for a, b in itertools.combinations(rankings, 2)]
    taus = [t for t in taus if t is not None]
    return sum(taus) / len(taus) if taus else None


# ---------------------------------------------------------------- triage

def triage_accuracy(agent_critical: set[str], gold_critical: set[str]) -> dict:
    tp = agent_critical & gold_critical
    return {
        "precision": len(tp) / len(agent_critical) if agent_critical else 1.0,
        "recall": len(tp) / len(gold_critical) if gold_critical else 1.0,
        "missed": sorted(gold_critical - agent_critical),
        "false_alarms": sorted(agent_critical - gold_critical),
    }


# ---------------------------------------------------------------- compliance

def compliance(agent_input: dict, dataset: dict) -> list[dict]:
    """Deterministic rule checks on what the agent fed the calculator."""
    checks = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"check": name, "ok": bool(ok), "detail": detail})

    uc = dataset["user_context"]
    tasks = {t.get("id"): t for t in agent_input.get("tasks", [])}
    expected = {t["id"]: t for t in dataset["tasks"]}

    check("as_of is the dataset date", agent_input.get("as_of") == dataset["as_of"],
          f"got {agent_input.get('as_of')!r}")

    team = agent_input.get("team") or {}
    wip, cap = len(dataset["wip"]), uc["capacity"]
    ok_team = (team.get("in_progress") == wip and team.get("capacity") == cap) or \
              (isinstance(team.get("rho"), (int, float)) and abs(team["rho"] - wip / cap) < 1e-6)
    check("utilization measured live (in_progress from tracker, capacity from user)", ok_team, f"got {team}")

    missing, extra = sorted(set(expected) - set(tasks)), sorted(set(tasks) - set(expected))
    check("every backlog task passed exactly once",
          not missing and not extra and len(agent_input.get("tasks", [])) == len(expected),
          f"missing={missing} extra={extra}")

    wrong_flag = [i for i, t in tasks.items() if i in expected
                  and t.get("evidence_found_in_text") != expected[i]["expected"]["evidence_found_in_text"]]
    check("evidence flags copied verbatim from the tool", not wrong_flag, f"differs: {wrong_flag}")

    wrong_triage = []
    for i, t in tasks.items():
        if i not in expected:
            continue
        sig, e = t.get("triage") or {}, expected[i]
        if sig.get("cvss_score") != e["expected"]["cvss_score"] or sig.get("due_date") != e["due_date"] \
                or sig.get("priority") != e["priority"]:
            wrong_triage.append(i)
    check("triage signals copied verbatim from the tool", not wrong_triage, f"differs: {wrong_triage}")

    overrides = [i for i, t in tasks.items() if "confidence" in t]
    check("no Confidence override attempted", not overrides, f"tasks: {overrides}")

    wrong_est = [i for i, e in uc["estimates"].items()
                 if (tasks.get(i, {}).get("estimate3") or {}) != {k: e[k] for k in ("opt", "real", "pess")}]
    check("user 3-point estimates passed", not wrong_est, f"tasks: {wrong_est}")

    architectural = {i for i, e in expected.items() if e["expected"]["adr"] in ("present", "missing")}
    flagged = {i for i, t in tasks.items() if t.get("architectural")}
    check("architectural changes flagged for the ADR check", architectural <= flagged,
          f"not flagged: {sorted(architectural - flagged)}")

    wrong_refs = [i for i, t in tasks.items() if i in expected and
                  [(r.get("id"), r.get("status")) for r in t.get("adr_refs") or []]
                  != [(r["id"], r["status"]) for r in expected[i]["expected"]["adr_refs"]]]
    check("adr_refs copied verbatim from the tool", not wrong_refs, f"differs: {wrong_refs}")

    present = {f.split("-", 1)[0] for f in uc["adr_present"]}
    bad_topic = [i for i, t in tasks.items() if t.get("adr_by_topic")
                 and (t["adr_by_topic"].get("id") not in present or t["adr_by_topic"].get("status") != "accepted")]
    check("adr_by_topic only cites existing accepted ADRs", not bad_topic, f"tasks: {bad_topic}")

    wrong_answers = []
    for i, a in uc["triage_answers"].items():
        t = tasks.get(i, {})
        if a["critical"] and not t.get("critical"):
            wrong_answers.append(f"{i} should be critical")
        if not a["critical"] and t.get("critical"):
            wrong_answers.append(f"{i} should not be critical")
    check("user triage answers applied", not wrong_answers, "; ".join(wrong_answers))

    answered_not_critical = {i for i, a in uc["triage_answers"].items() if not a["critical"]}
    dismissed = [i for i, t in tasks.items() if t.get("not_critical_reason") and i not in answered_not_critical]
    check("no auto-critical item dismissed without a user answer", not dismissed, f"tasks: {dismissed}")
    return checks
