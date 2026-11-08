---
status: accepted
date: 2026-11-08
decision-makers: Pavel Demyanenko
---
# Verify tracker fixtures against a local real YouTrack sandbox (synthetic data, outside CI)

## Context and Problem Statement

All tracker tests use WireMock fixtures that were written by hand (AGENTS.md §5: E2E only against a
local WireMock container, never live tracker data). Nothing checked that those fixtures match what
a real YouTrack returns, so a wrong field shape would pass every test and fail in production.

## Decision Drivers

* AGENTS.md §5: no live tracker data in tests.
* Fixtures must reflect the real API (field `$type`s, value shapes, query syntax, auth).
* CI must stay fast and free (ADR-0006).

## Considered Options

* Local YouTrack in docker compose (profile `sandbox`), seeded from the Golden Dataset, running the
  same contract as the WireMock tests; manual, outside CI
* Record fixtures from the company's real YouTrack
* Do nothing (trust hand-written fixtures)

## Decision Outcome

Chosen option: "local YouTrack sandbox with synthetic data", because it checks the fixtures against
the real API without touching live data, and keeps E2E and CI on WireMock as AGENTS.md requires.

### Consequences

* Good, because `GoldenBacklogContract` passes on both WireMock and real YouTrack 2026.2.
* Good, because agents and the MCP server can be tried against a real tracker locally.
* Bad, because the image is ~2 GB and needs ~2 GB RAM; setup relies on undocumented details
  (super-user login `admin`, asynchronous project deletion).
* Bad, because only YouTrack is covered; Jira and Confluence still rely on fixtures only.

### Confirmation

`docker-compose.e2e.yml` profile `sandbox`, `e2e/youtrack-sandbox/seed.py`, `YouTrackSandboxIT`
(skipped unless `YOUTRACK_SANDBOX_TOKEN` is set).

## More Information

Complements AGENTS.md §5 rather than replacing it: E2E stays on WireMock.
