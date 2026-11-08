---
status: accepted
date: 2026-11-09
decision-makers: Pavel Demyanenko
---
# Ship YouTrack only, with per-project configuration of metrics and triage names

## Context and Problem Statement

The project is published for other teams. Teams value different things and often use localized
YouTrack values (priority, issue type and tag names).

## Decision Drivers

* Ship only what is verified against a real YouTrack.
* Let each team adapt weights and names without forking.
* Simple distribution for MCP hosts.

## Considered Options

* YouTrack only; `.backlog-prioritizer.json` for metrics, weights and extra triage names
* Support more trackers from the start
* Fixed metrics and English names only

## Decision Outcome

Chosen option: "YouTrack only with per-project configuration".

### Consequences

* Good, because every published feature is covered by tests against a real YouTrack (Docker sandbox).
* Good, because metrics, weights and localized triage markers are configurable; invalid files are rejected.
* Bad, because other trackers are not supported.

### Confirmation

`ProjectConfig` tests in `scripts/test_priority.py`; `references/configuration.md`.
