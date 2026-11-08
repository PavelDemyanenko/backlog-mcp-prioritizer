---
status: accepted
date: 2026-11-09
decision-makers: Pavel Demyanenko
---
# Compliance risk counts like the top value metric; operational deadlines are ranked at U5

## Context and Problem Statement

With the default weights a compliance task (e.g. audit preparation) scored very low Value, because
the risk it removes is one small metric (5 %); it sank to the bottom although reviewers ranked it near
the top. Tasks with an operational deadline (an expiring certificate that takes an API down) were
scored below the urgency reviewers gave them.

## Decision Drivers

* WSJF treats risk reduction as part of the cost of delay.
* Weights stay global for the team; no per-request re-weighting.
* CRITICAL stays reserved for a short, explicit list of thresholds.

## Considered Options

* A calculator rule for compliance work keyed on triage labels, plus a rubric rule for operational deadlines
* Raise the global risk weight for every task
* A new CRITICAL threshold for operational deadlines

## Decision Outcome

Chosen option: "calculator rule plus rubric rule".

* Compliance work (labels, components or type matching compliance, legal, regulatory, GDPR, 152-FZ,
  PCI, SOX or configured markers): `V = max(V, top_weight × risk / 5 × Confidence)`. The risk metric is
  `tech_risk` by default and configurable (`risk_metric`). Evidence caps and Confidence still apply.
* An operational deadline whose miss takes a key system down is Urgency 5; such tasks are ranked, not CRITICAL.

### Consequences

* Good, because measured ranking quality improved (NDCG@10 against reference labels 0.925 → 0.97).
* Bad, because the rule was calibrated on a small dataset; re-check it with your own data.

### Confirmation

`ComplianceRisk` tests in `scripts/test_priority.py`; `references/scoring-rubric.md`.
