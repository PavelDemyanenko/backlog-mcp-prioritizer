---
status: accepted
date: 2026-11-09
decision-makers: Pavel Demyanenko
---
# Publish as an open-source, YouTrack-only project with per-project configuration

## Context and Problem Statement

The server and skills were built and validated inside an internal project (ADR-0001…0009) with
YouTrack and Jira tools, a Confluence stub and metrics tuned for one platform team. They are now
published for other teams.

## Decision Drivers

* YouTrack is the validated path: real-API contract checks (ADR-0007), interactive pilot, live evals.
* Other teams have their own value metrics and often localized YouTrack values.
* Distribution as simple as possible for MCP hosts.

## Considered Options

* YouTrack only, configurable metrics and triage names, Docker image + jar + skills zip
* Keep Jira and the Confluence stub
* Keep fixed metrics

## Decision Outcome

Chosen option: "YouTrack only with per-project configuration", because it ships only what is
verified and lets each team adapt weights and names without forking.

### Consequences

* Good, because every published feature is covered by tests against a real YouTrack.
* Good, because `.backlog-prioritizer.json` makes metrics and localized triage markers configurable.
* Bad, because Jira users are not served; the Jira client stays in the internal history only.
* Bad, because ADR-0001…0009 still mention Jira and the internal Golden Dataset context; they are kept as decision history.

### Confirmation

No Jira/Confluence code in `src/`; `ProjectConfig` tests in `scripts/test_priority.py`; release workflow.
