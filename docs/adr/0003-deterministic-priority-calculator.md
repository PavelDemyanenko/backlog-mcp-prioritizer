---
status: accepted
date: 2026-11-09
decision-makers: Pavel Demyanenko
---
# The model judges, a deterministic script computes priority

## Context and Problem Statement

Priority = V × U / C^0.7 with Evidence Tier caps, a queueing penalty from team utilization, PERT,
tie-breaks and automatic triage. Language models make arithmetic and rule-application errors, and
rankings must be reproducible to be reviewed and evaluated.

## Decision Drivers

* Rules must hold every time (Confidence 0.5 without evidence, penalty never skipped).
* Identical input must give an identical ranking.
* A full math trace in every report.

## Considered Options

* The agent judges Impact/Urgency; `scripts/priority.py` computes and enforces the rules
* The agent computes everything following the skill text
* A Java MCP tool computes priority

## Decision Outcome

Chosen option: "agent judges, Python script computes", because rules are enforced in code (a
`confidence` input is ignored, missing utilization is an error) and the same script is reused by
the evals.

### Consequences

* Good, because evals measure the agent's judgment, not its arithmetic.
* Good, because refusal rules cannot be bypassed by a prompt.
* Bad, because the host must allow running a Python script (also a useful confirmation step).
* Bad, because rules live in Python while the server is Java.

### Confirmation

`scripts/test_priority.py`; the skill forbids computing by hand when the script cannot run.
