<p align="center">
  <img src="docs/assets/logo-128.png" width="96" height="96" alt="Backlog MCP Prioritizer logo">
</p>

<h1 align="center">Backlog MCP Prioritizer</h1>

<p align="center">
  Evidence-based backlog prioritization for <b>YouTrack</b>, run by your AI agent<br>
  (Claude Code, Cursor, Claude Desktop): the agent judges, a deterministic calculator computes,<br>
  and nothing is applied until a human says <b>Approve</b>.
</p>

<p align="center">
  <a href="https://github.com/PavelDemyanenko/backlog-mcp-prioritizer/actions/workflows/ci.yml"><img src="https://github.com/PavelDemyanenko/backlog-mcp-prioritizer/actions/workflows/ci.yml/badge.svg?branch=main" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT license"></a>
</p>

<p align="center"><a href="README.ru.md">Русская версия</a></p>

---

## Why

Asking an LLM to "prioritize the backlog" usually gives a confident list built on guessed numbers.
This project splits the job:

- An **MCP server** reads YouTrack (read-only) and returns a compact, normalized view of each issue:
  story points, state, an evidence flag, ADR links checked against your repo, and triage signals
  (priority, type, tags, due date, CVSS). Raw descriptions never reach the model.
- A **skill** tells the agent what to judge (Impact per metric, Urgency) and what it may not do
  (raise Confidence without evidence, skip the queueing penalty, apply anything without approval).
- A **calculator** (`priority.py`) does all the math: WSJF/RICE-style `Priority = V·U / C^0.7`,
  Evidence Tiers, a queueing penalty from live team utilization, PERT estimates, automatic triage
  of critical items, and a full math trace.

```text
| Rank | Task | Critical? | V (Value) | U | C (Cost) | Priority | Notes / Evidence Tier |
| -    | [DEV-3] CVE-2026-40211: RCE in template engine | YES | - | - | - | - | CVSS 9.8 >= 9 (auto) |
| 1    | [DEV-14] Rate limiting for the generation API  | NO  | 0.27 (Conf:1.0) | 4 | 15.00 (Penalty: 3.0) | 0.16 | Evidence: Tier 1 |
```

## How it works

```text
MCP host (Claude Code, Cursor, …) ──stdio──▶ backlog-mcp-prioritizer ──HTTPS GET──▶ YouTrack REST API
   │  skill: backlog-prioritization-engine        (Spring AI MCP server,           (read-only token)
   │  skill: adr-custodian                          Java 25)  ──reads──▶ docs/adr/*.md of your repo
   └──▶ python3 priority.py  (all arithmetic, rules, triage)
```

## Tools

| Tool | Parameters | Returns |
|---|---|---|
| `youtrack_query_backlog` | `search_query`, `limit=20` (max 100) | `[{id, summary, status, story_points, story_points_source, evidence_found_in_text, adr_refs, triage}]` |
| `youtrack_count_issues` | `search_query` | `{count, capped}`: exact count without the 100-issue limit (team WIP for ρ) |
| `adr_list` | `status?` | ADRs from your repo: `{id, title, status, date, superseded_by, file}` |
| `adr_read` | `id` | Markdown of one ADR (by number only, no paths) |

Field mapping, evidence rules and output details: [docs/tools.md](docs/tools.md).

## Quick start

You need: a YouTrack instance (Cloud or Server), an MCP host, **Docker** (or Java 25 instead),
and **Python 3.10+** for the calculator. Everything is prebuilt in the
[latest release](https://github.com/PavelDemyanenko/backlog-mcp-prioritizer/releases/latest).

1. **Create a read-only token.** YouTrack → your avatar → Profile → Account Security → Tokens →
   *New token…*, scope **YouTrack**. Use an account that can only *read* the projects to prioritize.

2. **Register the server in your project** (run inside the project folder, so ADRs and the token
   stay per project). Claude Code:
   ```bash
   claude mcp add -s local backlog \
     -e YOUTRACK_BASE_URL=https://yourcompany.youtrack.cloud -e YOUTRACK_TOKEN=perm:xxxx \
     -- docker run -i --rm -e YOUTRACK_BASE_URL -e YOUTRACK_TOKEN \
        -v "$PWD/docs/adr:/adr:ro" ghcr.io/paveldemyanenko/backlog-mcp-prioritizer:latest
   ```
   `-s local` keeps the token in your user config (`~/.claude.json`), not in the repository.
   Never put the token into a committed `.mcp.json`. No ADRs in the project? Drop the `-v …` part:
   Docker would otherwise create an empty root-owned `docs/adr` folder.

   <details><summary>Cursor / Claude Desktop</summary>

   `.cursor/mcp.json` (git-ignore it) or `claude_desktop_config.json`:
   ```json
   { "mcpServers": { "backlog": {
       "command": "docker",
       "args": ["run", "-i", "--rm", "-e", "YOUTRACK_BASE_URL", "-e", "YOUTRACK_TOKEN",
                "-v", "/ABS/PATH/TO/PROJECT/docs/adr:/adr:ro",
                "ghcr.io/paveldemyanenko/backlog-mcp-prioritizer:latest"],
       "env": { "YOUTRACK_BASE_URL": "https://yourcompany.youtrack.cloud", "YOUTRACK_TOKEN": "perm:xxxx" } } } }
   ```
   The skills below are a Claude Code feature; in other hosts use `SKILL.md` as a rule/prompt.
   </details>

   <details><summary>Without Docker (Java 25)</summary>

   Download `backlog-mcp-server-<version>.jar` from the release:
   ```bash
   claude mcp add -s local backlog \
     -e YOUTRACK_BASE_URL=https://yourcompany.youtrack.cloud -e YOUTRACK_TOKEN=perm:xxxx \
     -- java -jar /ABS/PATH/backlog-mcp-server-<version>.jar
   ```
   ADRs are read from `docs/adr` relative to the folder the host is started in (`ADR_DIR` to change).
   </details>

3. **Install the skills.** Unzip `backlog-mcp-prioritizer-skills-<version>.zip` from the release into
   your project's `.claude/skills/` (or `~/.claude/skills/` for all projects):
   ```bash
   mkdir -p .claude/skills && unzip backlog-mcp-prioritizer-skills-<version>.zip -d .claude/skills/
   ```

4. **Optional: adapt it to your team** with `.backlog-prioritizer.json` in the project root: your own
   value metrics and weights, and your priority / issue-type / tag names (e.g. a localized
   YouTrack). See [configuration](skills/backlog-prioritization-engine/references/configuration.md).

5. **Restart the MCP host** (or `/mcp` in Claude Code) and ask:
   *"Prioritize the YouTrack backlog of project DEV."* The agent counts work in progress, asks for
   your team's capacity and unclear critical items, shows the ranked table with a math trace and
   waits for **Approve / Reject**.

Behind a proxy or with YouTrack on `localhost`: see [docs/tools.md](docs/tools.md#network).

## What it reads from YouTrack

| Signal | Source in YouTrack |
|---|---|
| status | `State` field |
| story_points | `Story points` field; if empty, `Estimation` (period) ÷ 8 h, marked `time_estimate_fallback` |
| evidence_found_in_text | description links to Confluence / Google Docs, the word "evidence", or a link to an **accepted** ADR in your repo |
| adr_refs | `docs/adr/NNNN-*.md` / `ADR-15` mentions, resolved against your ADR folder (accepted, proposed, superseded, missing) |
| triage | `Type`, `Priority`, tags, `Subsystem(s)`, `Due Date`, highest CVSS score in summary/description |

## Security

- **Read-only:** the server only sends `GET` requests; use a token of an account that cannot write.
- **Prompt injection:** issue descriptions are written by anyone with tracker access, so they are
  never returned to the model; only extracted, typed signals are.
- **Human in the loop:** the skill never applies a ranking; it ends every report with Approve / Reject.
- **stdout is the MCP channel:** all logs go to stderr.

Details and reporting: [SECURITY.md](SECURITY.md).

## Development

Java 25 + Maven, Python 3.10+, Docker.

```bash
mvn verify                                                     # unit, WireMock ITs (Testcontainers), STDIO E2E
python3 -I -m unittest discover -s skills/backlog-prioritization-engine/scripts
python3 -I -m unittest discover -s evals/golden                # golden-dataset eval pipeline (no LLM)
docker build -t backlog-mcp-prioritizer . && python3 e2e/docker_smoke.py backlog-mcp-prioritizer
```

A real YouTrack in Docker for contract checks: [e2e/youtrack-sandbox](e2e/youtrack-sandbox/README.md).
Live agent evals (NDCG@10, rule compliance, refusals, Reject branch; they cost LLM tokens):
[evals/golden](evals/golden/README.md). Design decisions: [docs/adr](docs/adr).
Pushing a `v*` tag publishes a release (jar, skills zip, checksums) and a multi-arch image to ghcr.io.
See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
