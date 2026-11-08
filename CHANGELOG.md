# Changelog

## 0.1.0 — 2026-11-09

First release.

- MCP server (Spring Boot 4.1, Spring AI 2.0, Java 25, stdio) with four read-only tools:
  `youtrack_query_backlog`, `youtrack_count_issues`, `adr_list`, `adr_read`.
- Normalized issue contract: story points (with `Estimation` fallback), evidence flag, ADR references
  resolved against the project's ADR folder, triage signals (type, priority, tags, components, due
  date, CVSS). Raw descriptions are never returned.
- Skills: `backlog-prioritization-engine` (calculator `priority.py`: `V·U/C^0.7`, Evidence Tiers,
  queueing penalty, PERT, auto-triage, compliance risk rule) and `adr-custodian`.
- Project configuration `.backlog-prioritizer.json`: own metrics and weights, localized triage names.
- Verified against a real YouTrack 2026.2 (Docker sandbox) and with live agent evals (NDCG@10 0.96).
- Docker image with AOT cache (cold start < 1 s), jar, skills zip.
