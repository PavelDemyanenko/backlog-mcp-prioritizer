---
status: accepted
date: 2026-11-09
decision-makers: Pavel Demyanenko
---
# Return a normalized issue contract with typed signals, never the raw description

## Context and Problem Statement

YouTrack returns polymorphic custom fields, and teams name fields differently. The agent needs
exact numbers for the formula and signals for critical-task triage (P1 incident, CVSS, legal
deadline). Issue descriptions are written by anyone with tracker access.

## Decision Drivers

* The formula must receive exact numbers, not model-parsed text.
* Indirect prompt injection through ticket text.
* A small, stable contract that costs few tokens.

## Considered Options

* Normalized fields plus server-extracted signals (`evidence_found_in_text`, `adr_refs`, `triage`)
* Return the raw description and let the agent find the signals
* Spec fields only; ask the user about everything else

## Decision Outcome

Chosen option: "normalized fields plus server-extracted signals", because it gives the agent
deterministic facts and keeps untrusted text out of its context.

### Consequences

* Good, because evidence, ADR references, CVSS and dates come from tested code.
* Good, because a malicious description cannot instruct the agent.
* Bad, because nuances that live only in the description are invisible; the skill asks the user.
* Bad, because every new signal needs server code and tests.

### Confirmation

`McpStdioE2EIT` asserts the exact JSON and the absence of `description`; `docs/tools.md` documents
the mapping.
