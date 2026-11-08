# Security

## Threat model

Backlog MCP Prioritizer runs on a developer machine next to an AI agent that usually has shell and
file-system access, and it holds a YouTrack token.

1. **Untrusted issue content (indirect prompt injection).** Summaries and descriptions are written by
   anyone with access to the tracker.
   - Descriptions are **never** returned to the model. The server extracts typed signals instead
     (evidence flag, ADR references, CVSS score, tags, dates).
   - Summaries are returned (they are needed to rank); the skill treats all tool output as data.
   - Tool errors carry curated messages only, never raw HTTP response bodies.
2. **Token exposure.**
   - Use a permanent token of an account that can only read the relevant projects.
   - Register the server with `claude mcp add -s local` (user config), not in a committed `.mcp.json`.
   - The token is never logged (`YouTrackProperties.toString` masks it).
3. **Write access.** The server only sends `GET` requests. Tests verify the request journal.
4. **Automation bias.** The skill never applies a ranking; a human must Approve or Reject.

The Docker image runs as a non-root user and opens no ports (stdio only).

## Reporting a vulnerability

Please do not open a public issue. Use GitHub's private vulnerability reporting ("Report a
vulnerability" on the Security tab) with steps to reproduce and the affected version.
