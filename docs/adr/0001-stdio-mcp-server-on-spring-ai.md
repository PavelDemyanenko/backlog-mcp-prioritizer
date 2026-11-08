---
status: accepted
date: 2026-11-08
decision-makers: Pavel Demyanenko
---
# Run the backlog MCP server over STDIO on Java 25, Spring Boot 4 and Spring AI 2

## Context and Problem Statement

Local agents (Claude Code, Cursor) need read-only access to YouTrack/Jira backlogs through typed
tools instead of generating REST calls themselves (spec §7, anti-GIGO). We need a server stack and
a transport.

## Decision Drivers

* Spec §2: Java 25, Spring Boot 4, Spring AI.
* Local CLI agents start MCP servers as child processes.
* stdout must carry only JSON-RPC (spec §8.1): any stray byte breaks the session.

## Considered Options

* Spring AI 2 MCP server starter (`@McpTool`), STDIO transport
* Embabel agent framework on top of Spring AI
* Plain MCP Java SDK without Spring
* Do nothing (agents call tracker REST APIs directly)

## Decision Outcome

Chosen option: "Spring AI 2 MCP server starter over STDIO", because it is the spec stack, gives
annotation-based tools with generated JSON schemas, and STDIO is what local agents launch.

### Consequences

* Good, because tools are plain Spring beans, testable without MCP.
* Good, because no ports, no auth layer for local use.
* Bad, because one process per agent session; no shared remote server (SSE not implemented).
* Bad, because all logging must be forced to stderr and guarded.

### Confirmation

`logback-spring.xml` has a single `System.err` appender. `StdoutHygieneTest` forbids `System.out`
in production code. `McpStdioE2EIT` starts the packaged jar and parses every stdout line as JSON-RPC.

## Pros and Cons of the Options

### Embabel

* Bad, because at decision time (2026-11-05) Spring Boot 4 / Spring AI 2 compatibility was not
  confirmed, and it duplicates what the Spring AI MCP starter already provides.

### Plain MCP Java SDK

* Good, because fewer dependencies.
* Bad, because tool schemas, config binding and RestClient wiring would be hand-written.

## More Information

spec.txt §2, §8.1. SSE transport can be added later as a separate ADR.
