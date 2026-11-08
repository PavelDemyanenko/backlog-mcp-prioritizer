# 0015. Use Spring AI for the generation service

> **Eval fixture.** This ADR exists only for the Golden Dataset. The eval harness copies
> `evals/golden/adr/` to `docs/adr/` in the workspace where the agent runs, so the skill's ADR
> check finds it for GOLD-7 and finds no ADR for GOLD-8 / GOLD-23.

- Status: accepted
- Date: 2026-09-14

## Context and Problem Statement
The generation service uses a hand-written LLM client without MCP or streaming support.

## Decision Outcome
Chosen option: migrate to Spring AI 2.x (MCP client/server, streaming, observability).

### Consequences
- Good: MCP tools, streaming, standard observability.
- Bad: migration effort of about 13 SP.
