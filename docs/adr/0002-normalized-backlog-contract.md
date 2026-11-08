---
status: accepted
date: 2026-11-08
decision-makers: Pavel Demyanenko
---
# Expose a normalized backlog contract with structured triage signals, never the raw description

## Context and Problem Statement

`youtrack_query_backlog` and `jira_query_backlog` feed the prioritization agent. Trackers return
polymorphic custom fields (YouTrack) and ADF documents (Jira Cloud). The agent also needs signals
for critical-task triage (P1 incident, CVSS ≥ 9.0, legal deadline).

## Decision Drivers

* Anti-GIGO: the formula must receive exact numbers, not model-parsed text.
* Prompt injection: ticket text is written by anyone with tracker access.
* Spec §8.2 contract (`id, summary, status, story_points, evidence_found_in_text`) must stay stable.

## Considered Options

* Spec fields flat and unchanged, plus additive `story_points_source`, `adr_refs` and a nested
  `triage` object; signals extracted on the server
* Return the raw description and let the agent find the signals
* Do nothing (spec fields only, triage done by asking the user)

## Decision Outcome

Chosen option: "spec fields plus additive, server-extracted signals", because it keeps the spec
contract backward compatible, gives the agent deterministic facts, and keeps untrusted text out of
the agent's context.

### Consequences

* Good, because evidence flag, CVSS, due date etc. are computed by tested code (`CvssExtractor`,
  `AdfText`, `EvidenceDetector`).
* Good, because a malicious description cannot instruct the agent.
* Bad, because the agent cannot read nuances that are only in the description; such cases are
  confirmed with the user.
* Bad, because every new signal needs server code and tests.

### Confirmation

`McpStdioE2EIT` asserts the exact JSON and that `description` is absent. `GoldenDatasetIT` checks
every extracted signal against `evals/golden/dataset.json`.

## More Information

`story_points_source` added at the user's request (step 3 review); `triage` added in step 4.
