---
status: accepted
date: 2026-11-08
decision-makers: Pavel Demyanenko
---
# Compliance risk counts as the top value metric; operational deadlines are ranked at U5, not critical

## Context and Problem Statement

Comparing the agent with the reference labels (ADR-0009) showed two gaps:

* GOLD-6 (PCI DSS audit preparation): the agent's judgments matched the labelers (U4, tech_risk 4),
  but `tech_risk` weighs only 5% of Value, so the task ranked about 11th while labelers put it near
  the top. Spec §4 requires WSJF treatment of compliance risk, which the formula did not express.
* GOLD-16 (expiring TLS certificate): labelers gave Urgency 5, the agent mostly 4.

## Decision Drivers

* Spec §4: WSJF for tasks with hard deadlines or compliance risk.
* Team weights stay global (skill rule 5); no per-request re-weighting.
* Deterministic rules in the calculator (ADR-0003), not in the prompt.

## Considered Options

* Calculator rule for compliance work keyed on triage labels, plus a rubric rule for operational deadlines
* Raise the global `tech_risk` weight for every task
* New CRITICAL threshold "key system outage expected within 30 days"
* Do nothing

## Decision Outcome

Chosen option: "calculator rule plus rubric rule", because it fixes the measured gaps without
changing global weights or the CRITICAL thresholds.

* Compliance work (labels, components or type containing compliance, legal, regulatory, GDPR,
  152-FZ, PCI, SOX): `V = max(V, 0.30 × tech_risk / 5 × Confidence)`, applied by `priority.py` from
  the tool's triage signals. Evidence caps and Confidence still apply.
* An operational deadline whose miss takes a key system down (certificate, licence, quota) is
  Urgency 5. Such tasks are ranked, not CRITICAL (owner decision 1b).

### Consequences

* Good, because offline replay of 5 saved runs moved NDCG@10 from 0.925 to 0.952 (0.958 with U5).
* Good, because the rule is deterministic and cannot be toggled by the agent.
* Bad, because it was derived from one compliance example in a 24-task dataset; re-check when the
  dataset or the reference labels change.

### Confirmation

`scripts/test_priority.py` (`ComplianceRisk`), `references/scoring-rubric.md`, Golden eval NDCG.
