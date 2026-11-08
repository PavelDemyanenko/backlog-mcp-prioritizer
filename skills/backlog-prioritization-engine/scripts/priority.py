#!/usr/bin/env python3
"""Deterministic priority calculator for the backlog-prioritization-engine skill.

The LLM judges Impact (0-5 per metric) and Urgency (1-5); this script does ALL arithmetic
and enforces the non-negotiable rules, so rankings are reproducible (anti-drift, NDCG evals):

  V        = (sum(weight_i * impact_i) / 5) * Confidence
  Conf     = 1.0 if evidence_found_in_text else 0.5            (never overridable)
  impact_i <= 3 when evidence_found_in_text is false            (hard cap)
  C        = base_cost * queue_penalty(rho)                     (penalty never skippable)
  base_cost= PERT (opt + 4*real + pess) / 6 if a 3-point estimate is given, else story_points
  Priority = (V * U) / C^0.7 ; ties at 2 decimals -> lower C wins, then id

Critical triage from the tool's `triage` signals (deterministic, relative to input `as_of`):
  auto-CRITICAL: cvss_score >= 9.0 | P1 priority + incident type | legal marker + due in < 30 days
  candidates (user must confirm): other P1 priorities, due < 30 days without legal marker,
  legal marker without due date. Financial risk > 500k RUB is never visible in tracker fields:
  only a user-confirmed `critical: true` covers it.

Usage:  python3 priority.py input.json [--config .backlog-prioritizer.json] [--json]
        (or: ... | python3 priority.py - )
Input schema: see references/calculator.md. Exit code 2 = invalid input (message on stderr).
"""
from __future__ import annotations

import datetime as dt
import json
import sys

DEFAULT_WEIGHTS = {  # globally shared team weights, sum = 1.0 (override: --config, see references/configuration.md)
    "scaling": 0.30,       # Scaling & coverage (how many teams/users benefit)
    "code_quality": 0.20,  # Code / output quality
    "latency": 0.15,
    "reliability": 0.15,   # Reliability & stability
    "performance": 0.10,   # Performance / efficiency
    "dev_speed": 0.05,     # Team dev speed
    "tech_risk": 0.05,     # Tech risk / security
}
WEIGHTS = dict(DEFAULT_WEIGHTS)
NO_EVIDENCE_IMPACT_CAP = 3
COST_EXPONENT = 0.7
UNCERTAINTY_LIMIT = 1.0

DEFAULT_CVSS_CRITICAL = 9.0
DEFAULT_LEGAL_DEADLINE_DAYS = 30
# Tracker priority names that mean P1 (YouTrack default set and common schemes).
DEFAULT_P1_PRIORITIES = frozenset({"highest", "blocker", "show-stopper", "showstopper", "p0", "p1", "urgent"})
DEFAULT_INCIDENT_TYPES = ("incident", "outage")
DEFAULT_LEGAL_MARKERS = ("legal", "compliance", "regulatory", "gdpr", "152-fz", "152fz", "pci", "sox", "law")

CVSS_CRITICAL = DEFAULT_CVSS_CRITICAL
LEGAL_DEADLINE_DAYS = DEFAULT_LEGAL_DEADLINE_DAYS
P1_PRIORITIES = set(DEFAULT_P1_PRIORITIES)
INCIDENT_TYPES = DEFAULT_INCIDENT_TYPES
LEGAL_MARKERS = DEFAULT_LEGAL_MARKERS
# WSJF risk reduction for compliance work: the risk metric counts like the top value metric.
RISK_METRIC = "tech_risk"
COMPLIANCE_RISK_WEIGHT = max(WEIGHTS.values())


def configure(cfg: dict | None) -> None:
    """Applies a project config (.backlog-prioritizer.json); None restores the defaults.

    {"metrics": [{"id": "reach", "label": "…", "weight": 0.3}, …],   # replaces the 7 default metrics
     "risk_metric": "tech_risk" | null,                                # compliance rule metric (null = off)
     "triage": {"p1_priorities": [...], "incident_types": [...],       # ADDED to the defaults,
                "legal_markers": [...],                                # case-insensitive
                "cvss_critical": 9.0, "legal_deadline_days": 30}}
    """
    global WEIGHTS, CVSS_CRITICAL, LEGAL_DEADLINE_DAYS, P1_PRIORITIES, INCIDENT_TYPES, LEGAL_MARKERS
    global RISK_METRIC, COMPLIANCE_RISK_WEIGHT
    cfg = cfg or {}
    unknown = set(cfg) - {"metrics", "risk_metric", "triage", "$schema", "_comment"}
    if unknown:
        raise InputError(f"config: unknown keys {sorted(unknown)}")
    if "metrics" in cfg:
        metrics = cfg["metrics"]
        if not isinstance(metrics, list) or not metrics:
            raise InputError("config: metrics must be a non-empty list of {id, weight}")
        weights = {}
        for m in metrics:
            mid, w = m.get("id"), m.get("weight")
            if not isinstance(mid, str) or not mid.replace("_", "").isalnum() or mid in weights:
                raise InputError(f"config: invalid or duplicate metric id {mid!r}")
            if not isinstance(w, (int, float)) or w <= 0:
                raise InputError(f"config: metric {mid!r} needs a positive weight")
            weights[mid] = float(w)
        if abs(sum(weights.values()) - 1.0) > 1e-6:
            raise InputError(f"config: metric weights must sum to 1.0, got {sum(weights.values()):g}")
    else:
        weights = dict(DEFAULT_WEIGHTS)
    risk = cfg.get("risk_metric", "tech_risk" if "tech_risk" in weights else None)
    if risk is not None and risk not in weights:
        raise InputError(f"config: risk_metric {risk!r} is not one of the metrics")
    tri = cfg.get("triage") or {}
    extra = lambda key: {str(x).strip().lower() for x in tri.get(key, []) if str(x).strip()}
    WEIGHTS = weights
    RISK_METRIC = risk
    COMPLIANCE_RISK_WEIGHT = max(weights.values())
    P1_PRIORITIES = set(DEFAULT_P1_PRIORITIES) | extra("p1_priorities")
    INCIDENT_TYPES = tuple(DEFAULT_INCIDENT_TYPES) + tuple(sorted(extra("incident_types")))
    LEGAL_MARKERS = tuple(DEFAULT_LEGAL_MARKERS) + tuple(sorted(extra("legal_markers")))
    CVSS_CRITICAL = float(tri.get("cvss_critical", DEFAULT_CVSS_CRITICAL))
    LEGAL_DEADLINE_DAYS = int(tri.get("legal_deadline_days", DEFAULT_LEGAL_DEADLINE_DAYS))


class InputError(ValueError):
    pass


def queue_penalty(rho: float) -> float:
    if rho > 0.95:
        return 3.0
    if rho > 0.85:
        return 1.5
    return 1.0


def resolve_rho(team: dict) -> tuple[float, str]:
    if team is None:
        raise InputError("team is required: Queueing Penalty cannot be skipped (give rho or in_progress+capacity)")
    if "rho" in team:
        rho = float(team["rho"])
        how = f"rho={rho:.2f} (given)"
    elif "in_progress" in team and "capacity" in team:
        wip, cap = int(team["in_progress"]), float(team["capacity"])
        if cap <= 0:
            raise InputError("team.capacity must be > 0")
        rho = wip / cap
        how = f"rho = in_progress / capacity = {wip} / {cap:g} = {rho:.2f}"
        if team.get("in_progress_truncated"):
            how += " (lower bound: tracker query hit its limit)"
    else:
        raise InputError("team needs 'rho' or both 'in_progress' and 'capacity'")
    if rho < 0:
        raise InputError("rho must be >= 0")
    return rho, how


def legal_marker(sig: dict) -> str | None:
    """First label/component/type that marks legal or compliance work (deterministic, from tool signals)."""
    tags = [x.lower() for x in (sig.get("labels") or []) + (sig.get("components") or [])]
    tags.append((sig.get("issue_type") or "").strip().lower())
    return next((x for x in tags if any(m in x for m in LEGAL_MARKERS)), None)


def triage(t: dict, as_of: dt.date | None) -> tuple[list[str], list[str]]:
    """Returns (auto-critical reasons, candidate reasons needing user confirmation)."""
    sig = t.get("triage") or {}
    auto, candidates = [], []
    cvss = sig.get("cvss_score")
    if cvss is not None and float(cvss) >= CVSS_CRITICAL:
        auto.append(f"CVSS {float(cvss):g} >= {CVSS_CRITICAL:g}")

    priority = (sig.get("priority") or "").strip().lower()
    issue_type = (sig.get("issue_type") or "").strip().lower()
    is_p1 = priority in P1_PRIORITIES
    if is_p1 and any(k in issue_type for k in INCIDENT_TYPES):
        auto.append(f"P1 incident ({sig.get('priority')} {sig.get('issue_type')})")
    elif is_p1:
        candidates.append(f"P1 priority '{sig.get('priority')}' on a {sig.get('issue_type') or 'task'}: incident/downtime > 15 min?")

    legal = legal_marker(sig)
    due = sig.get("due_date")
    if due:
        if as_of is None:
            raise InputError(f"{t.get('id')}: 'as_of' (yyyy-mm-dd) is required to evaluate due_date")
        try:
            days = (dt.date.fromisoformat(due) - as_of).days
        except ValueError:
            raise InputError(f"{t.get('id')}: triage.due_date must be yyyy-mm-dd, got {due!r}") from None
        if days < LEGAL_DEADLINE_DAYS and legal:
            auto.append(f"legal deadline in {days} days ({legal}, due {due})")
        elif days < LEGAL_DEADLINE_DAYS:
            candidates.append(f"due in {days} days ({due}): is it a mandatory legal deadline?")
    elif legal:
        candidates.append(f"legal marker '{legal}' without due date: legal deadline < 30 days?")
    return auto, candidates


def accepted_adrs(t: dict, notes: list[str]) -> list[str]:
    """Accepted ADR ids backing the task: `adr_refs` from the tool (verbatim) plus an optional
    `adr_by_topic` the agent found via adr_list. Non-accepted references are reported in notes."""
    accepted = []
    for ref in t.get("adr_refs") or []:
        status = ref.get("status")
        if status == "accepted":
            accepted.append(ref["id"])
        elif status == "superseded":
            notes.append(f"ADR {ref['id']} is superseded by {ref.get('superseded_by') or '?'}: link the current ADR")
        else:
            notes.append(f"ADR {ref['id']} is {status}: not evidence")
    topic = t.get("adr_by_topic")
    if topic:
        if topic.get("status") == "accepted":
            accepted.append(topic["id"])
            notes.append(f"ADR {topic['id']} matched by topic, not linked in the ticket: add the link")
        else:
            notes.append(f"ADR {topic.get('id')} matched by topic is {topic.get('status')}: not evidence")
    return accepted


def score_task(t: dict, penalty: float, as_of: dt.date | None = None) -> dict:
    tid = t.get("id") or "?"
    out = {"id": tid, "summary": t.get("summary", ""), "notes": []}

    auto, candidates = triage(t, as_of)
    dismissed = t.get("not_critical_reason")
    if auto and dismissed:
        out["notes"].append(f"auto-critical dismissed by user ({'; '.join(auto)}): {dismissed}")
        auto = []
    if t.get("critical") or auto:
        out["status"] = "CRITICAL"
        reasons = ([f"{t.get('critical_reason', 'threshold met')} (confirmed by user)"] if t.get("critical") else []) \
            + [f"{r} (auto)" for r in auto]
        out["notes"].append("CRITICAL: " + "; ".join(reasons))
        return out
    if candidates and not t.get("triage_confirmed_not_critical"):
        out["triage_candidates"] = candidates

    flag = t.get("evidence_found_in_text")
    if not isinstance(flag, bool):
        raise InputError(f"{tid}: evidence_found_in_text (bool, from the MCP tool) is required")
    if "architectural_without_adr" in t:
        raise InputError(f"{tid}: 'architectural_without_adr' was replaced by 'architectural' + verbatim 'adr_refs'")
    adr_missing = bool(t.get("architectural")) and not accepted_adrs(t, out["notes"])
    confidence = 1.0 if (flag and not adr_missing) else 0.5
    tier = "Tier 1" if confidence == 1.0 else "Tier 3-4"
    if adr_missing:
        out["notes"].append("architectural change without accepted ADR -> Confidence 0.5")

    impacts = t.get("impacts") or {}
    unknown = set(impacts) - set(WEIGHTS)
    if unknown:
        raise InputError(f"{tid}: unknown impact metrics {sorted(unknown)}; allowed {sorted(WEIGHTS)}")
    weighted, terms, risk_imp = 0.0, [], 0
    for metric, weight in WEIGHTS.items():
        raw = impacts.get(metric, 0)
        if not isinstance(raw, int) or not 0 <= raw <= 5:
            raise InputError(f"{tid}: impact '{metric}' must be an integer 0..5, got {raw!r}")
        imp = raw
        if not flag and imp > NO_EVIDENCE_IMPACT_CAP:
            imp = NO_EVIDENCE_IMPACT_CAP
            out["notes"].append(f"{metric} impact {raw}->{imp} (no evidence cap)")
        weighted += weight * imp
        if metric == RISK_METRIC:
            risk_imp = imp
        if imp:
            terms.append(f"{weight:.2f}*{imp}")
    value = weighted / 5 * confidence
    out["value_trace"] = f"V = ({' + '.join(terms) or '0'}) / 5 * {confidence} = {value:.4f}"
    marker = legal_marker(t.get("triage") or {})
    risk_value = COMPLIANCE_RISK_WEIGHT * risk_imp / 5 * confidence
    if marker and RISK_METRIC and risk_value > value:
        out["value_trace"] += (f"; compliance ({marker}): risk weighted as top metric, "
                               f"V = {COMPLIANCE_RISK_WEIGHT:.2f}*{risk_imp} / 5 * {confidence} = {risk_value:.4f}")
        out["notes"].append(f"compliance work ({marker}): WSJF risk reduction applied")
        value = risk_value

    urgency = t.get("urgency")
    if not isinstance(urgency, int) or not 1 <= urgency <= 5:
        raise InputError(f"{tid}: urgency must be an integer 1..5, got {urgency!r}")

    out.update(value=round(value, 4), confidence=confidence, tier=tier, urgency=urgency)

    est = t.get("estimate3")
    if est:
        opt, real, pess = (float(est[k]) for k in ("opt", "real", "pess"))
        if real <= 0 or opt < 0 or pess < opt:
            raise InputError(f"{tid}: estimate3 must satisfy 0 <= opt <= pess and real > 0")
        spread = (pess - opt) / real
        if spread > UNCERTAINTY_LIMIT:
            out["status"] = "NEEDS_DECOMPOSITION"
            out["notes"].append(f"(pess-opt)/real = ({pess:g}-{opt:g})/{real:g} = {spread:.2f} > {UNCERTAINTY_LIMIT}")
            return out
        base = (opt + 4 * real + pess) / 6
        out["cost_trace"] = f"C0 = ({opt:g} + 4*{real:g} + {pess:g}) / 6 = {base:.2f} (PERT)"
    else:
        sp = t.get("story_points")
        if sp is None or float(sp) <= 0:
            out["status"] = "NEEDS_ESTIMATE"
            out["notes"].append("no story_points and no 3-point estimate")
            return out
        base = float(sp)
        src = t.get("story_points_source") or "custom_field"
        out["cost_trace"] = f"C0 = story_points = {base:g} ({src})"
        if src == "time_estimate_fallback":
            out["notes"].append("SP derived from time estimate (1 SP = 8h): confirm with team")

    if value == 0:
        out["status"] = "ZERO_VALUE"
        out["notes"].append("V = 0: never executed regardless of urgency")
        return out

    cost = base * penalty
    priority = value * urgency / cost ** COST_EXPONENT
    out.update(status="RANKED", base_cost=round(base, 2), cost=round(cost, 2), penalty=penalty,
               priority=priority, priority_2dp=round(priority, 2))
    out["cost_trace"] += f"; C = {base:.2f} * {penalty} = {cost:.2f}"
    out["priority_trace"] = f"P = {value:.4f} * {urgency} / {cost:.2f}^{COST_EXPONENT} = {priority:.4f}"
    out["notes"].append(f"Evidence: {tier} (flag {'TRUE' if flag else 'FALSE'})")
    return out


def run(data: dict) -> dict:
    as_of = None
    if data.get("as_of"):
        try:
            as_of = dt.date.fromisoformat(data["as_of"])
        except ValueError:
            raise InputError(f"as_of must be yyyy-mm-dd, got {data['as_of']!r}") from None
    rho, rho_trace = resolve_rho(data.get("team"))
    penalty = queue_penalty(rho)
    tasks = data.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise InputError("tasks must be a non-empty list")
    ids = [t.get("id") for t in tasks]
    if len(set(ids)) != len(ids):
        raise InputError("task ids must be unique")

    scored = [score_task(t, penalty, as_of) for t in tasks]
    ranked = sorted((s for s in scored if s["status"] == "RANKED"),
                    key=lambda s: (-s["priority_2dp"], s["cost"], s["id"]))
    for rank, s in enumerate(ranked, 1):
        s["rank"] = rank
    for a, b in zip(ranked, ranked[1:]):
        if a["priority_2dp"] == b["priority_2dp"]:
            b["notes"].append(f"tie with {a['id']} at {a['priority_2dp']:.2f}: lower C wins")
    return {
        "queue": {"rho": round(rho, 4), "penalty": penalty, "trace": rho_trace},
        "critical": [s for s in scored if s["status"] == "CRITICAL"],
        "ranked": ranked,
        "refused": [s for s in scored if s["status"] in ("NEEDS_DECOMPOSITION", "NEEDS_ESTIMATE", "ZERO_VALUE")],
        "triage_candidates": [{"id": s["id"], "reasons": s["triage_candidates"]}
                              for s in scored if s.get("triage_candidates")],
    }


def to_markdown(r: dict) -> str:
    q = r["queue"]
    lines = [f"**Queue:** {q['trace']} -> Effort penalty x{q['penalty']}", "", "### Ranking Table",
             "| Rank | Task | Critical? | V (Value) | U (Urgency) | C (Cost) | Priority | Notes / Evidence Tier |",
             "|---|---|---|---|---|---|---|---|"]
    for s in r["critical"]:
        lines.append(f"| - | [{s['id']}] {s['summary']} | YES | - | - | - | - | {'; '.join(s['notes'])} — executed out of ranking |")
    for s in r["ranked"]:
        lines.append(
            f"| {s['rank']} | [{s['id']}] {s['summary']} | NO | {s['value']:.2f} (Conf:{s['confidence']}) | {s['urgency']} "
            f"| {s['cost']:.2f} (Penalty: {s['penalty']}) | **{s['priority_2dp']:.2f}** | {'; '.join(s['notes'])} |")
    if r["refused"]:
        lines += ["", "### Refused / Needs Decomposition"]
        for s in r["refused"]:
            lines.append(f"- [{s['id']}] {s['status']}: {'; '.join(s['notes'])}")
    if r["triage_candidates"]:
        lines += ["", "### Triage: needs your confirmation (scored as non-critical until confirmed)"]
        for c in r["triage_candidates"]:
            lines.append(f"- [{c['id']}] " + "; ".join(c["reasons"]))
    lines += ["", "### Math trace"]
    for s in r["ranked"]:
        lines.append(f"- {s['id']}: {s['value_trace']}; {s['cost_trace']}; {s['priority_trace']}")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    args, config_path, it = [], None, iter(argv[1:])
    for a in it:
        if a == "--config":
            config_path = next(it, None)
        elif not a.startswith("--"):
            args.append(a)
    if len(args) != 1 or ("--config" in argv and not config_path):
        print(__doc__, file=sys.stderr)
        return 2
    try:
        configure(json.loads(open(config_path, encoding="utf-8").read()) if config_path else None)
        raw = sys.stdin.read() if args[0] == "-" else open(args[0], encoding="utf-8").read()
        result = run(json.loads(raw))
    except (InputError, json.JSONDecodeError, KeyError, TypeError, ValueError, OSError) as e:
        print(f"invalid input: {e}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2) if "--json" in argv else to_markdown(result))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
