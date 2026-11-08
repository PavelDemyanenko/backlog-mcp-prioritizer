# AGENTS.md — instructions for AI coding agents

Context and rules for agents (Claude Code, Cursor, Copilot) working on this repository.

## Goal
Evidence-based, reproducible backlog prioritization for YouTrack. The model judges; deterministic
code extracts data and computes. Every number in a ranking must come from YouTrack, the user or
`priority.py`. Decisions and their reasons: [docs/adr](docs/adr).

## Layout
- `src/main/java/backlogmcp/` — Spring Boot 4.1 + Spring AI 2.0 MCP server (stdio).
  - `youtrack/` — read-only client (`/api/issues`), normalizer (`BacklogIssue` contract), Estimation fallback, count.
  - `backlog/` — MCP tools `youtrack_query_backlog`, `youtrack_count_issues`; contract records.
  - `adr/` — ADR repository (MADR/Nygard parser), reference resolver, tools `adr_list`, `adr_read`.
  - `evidence/`, `triage/` — evidence-link and CVSS detection; `http/` — proxy policy; `tool/` — curated tool errors.
- `skills/backlog-prioritization-engine/` — skill + `scripts/priority.py` (all math and rules) + references.
- `skills/adr-custodian/` — ADR consistency skill.
- `e2e/` — WireMock fixtures, ADR fixtures, real YouTrack sandbox (`youtrack-sandbox/`), Docker smoke test.
- `evals/golden/` — Golden Dataset, reference labels, live agent evals (cost LLM tokens, never in CI).

## Rules
1. **stdout belongs to MCP.** Never write to `System.out`; logs go to stderr (`StdoutHygieneTest`).
2. **Read-only.** Only `GET` requests to YouTrack; tests assert the request journal.
3. **Contract changes** (`BacklogIssue`, `TriageSignals`, tool parameters/output) update
   `docs/tools.md` and the exact-JSON assertions in `McpStdioE2EIT` in the same change. Never return
   raw issue descriptions (prompt injection).
4. **Math and rules live in `priority.py`,** not in prompts. A rule change needs tests in
   `scripts/test_priority.py` and an ADR in `docs/adr`.
5. **Tool errors** go through `ToolResults.run` (curated message, no root-cause/HTTP body leak).
6. **Spring beans and `@ConfigurationProperties` records** keep a single constructor (or mark one
   `@Autowired`): two public constructors broke startup twice.
7. **Live LLM evals are on demand only** (ADR-0006); CI stays deterministic.
8. **Before handing over:** `mvn verify`, both Python test suites, `python3 -I evals/golden/build.py --check`.
