---
status: accepted
date: 2026-11-08
decision-makers: Pavel Demyanenko
---
# The LLM judges, a deterministic script computes priority

## Context and Problem Statement

Priority = (V × U) / C^0.7 with Evidence Tier caps, a queueing penalty from ρ, PERT, tie-breaks and
auto-triage. LLMs make arithmetic and rule-application errors, and rankings must be reproducible
for NDCG evals and drift tracking.

## Decision Drivers

* Spec §4, §8.3 rules must hold every time (Confidence 0.5 without evidence, penalty never skipped).
* Reproducibility for Golden Dataset evals.
* A full mathematical trace in the report.

## Considered Options

* Agent judges Impact/Urgency/architectural; `skills/backlog-prioritization-engine/scripts/priority.py`
  computes and enforces rules
* Agent computes everything following the skill text
* MCP tool in Java that computes priority

## Decision Outcome

Chosen option: "agent judges, Python script computes", because rules are enforced in code (inputs
like `confidence` are ignored, missing ρ is an error) and the same script is reused by the eval
harness.

### Consequences

* Good, because identical input gives identical ranking; evals measure judgment, not arithmetic.
* Good, because refusal rules cannot be bypassed by prompt.
* Bad, because the agent needs permission to run a script (cognitive friction, accepted).
* Bad, because rules live in Python while the server is Java.

### Confirmation

`scripts/test_priority.py` (rule tests); `evals/golden/run_eval.py` re-runs `priority.py` on the
agent's saved input.
