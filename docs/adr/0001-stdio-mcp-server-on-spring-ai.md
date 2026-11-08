---
status: accepted
date: 2026-11-09
decision-makers: Pavel Demyanenko
---
# Run the server as a local MCP server over stdio (Java 25, Spring Boot 4, Spring AI 2)

## Context and Problem Statement

AI agents (Claude Code, Cursor, Claude Desktop) need read-only access to a YouTrack backlog through
typed tools instead of composing REST calls themselves, which leads to guessed fields and numbers.

## Decision Drivers

* Local agents start MCP servers as child processes.
* stdout of a stdio server carries only JSON-RPC: one stray byte breaks the session.
* Typed tools with generated JSON schemas, simple configuration, good HTTP client.

## Considered Options

* Spring AI 2 MCP server starter (`@McpTool`) over stdio
* Plain MCP Java SDK without Spring
* A remote HTTP/SSE server
* No server: the agent calls the YouTrack REST API directly

## Decision Outcome

Chosen option: "Spring AI 2 MCP server over stdio", because it gives annotation-based tools with
generated schemas and runs where the agent runs, without ports or a separate auth layer.

### Consequences

* Good, because tools are plain Spring beans, testable without MCP.
* Good, because the token stays on the user's machine; the Docker image opens no ports.
* Bad, because there is one process per agent session (mitigated by an AOT cache: cold start < 1 s).
* Bad, because all logging must go to stderr and be guarded.

### Confirmation

`logback-spring.xml` has a single `System.err` appender; `StdoutHygieneTest` forbids `System.out`;
`McpStdioE2EIT` and `e2e/docker_smoke.py` parse every stdout line as JSON-RPC.
