# Tools, data mapping and configuration

## `youtrack_query_backlog`

Parameters: `search_query` (YouTrack query syntax, required), `limit` (default 20, max 100).
`GET /api/issues?query=…&fields=…&$top=…`. Returns a JSON array:

```json
[{"id": "DEV-7", "summary": "CVE-2026-31337: RCE in template engine", "status": "Open",
  "story_points": 3, "story_points_source": "custom_field", "evidence_found_in_text": false,
  "adr_refs": [],
  "triage": {"issue_type": "Bug", "priority": "Show-stopper", "labels": ["security"],
             "components": [], "due_date": null, "cvss_score": 9.8}}]
```

| Field | How it is computed |
|---|---|
| `status` | the `StateIssueCustomField`, else a field named State / Status / Stage |
| `story_points` | field named "Story points" (also `story_points`, `StoryPoints`, `SP`; number, numeric text or numeric enum value). If empty: period field `Estimation` (also "Original estimation") in minutes ÷ `YOUTRACK_MINUTES_PER_STORY_POINT` (480 = 8 h, YouTrack's `1d`), rounded to 0.1 |
| `story_points_source` | `custom_field`, `time_estimate_fallback` or `null` (null exactly when `story_points` is null) |
| `evidence_found_in_text` | the description contains a Confluence link (`*.atlassian.net/wiki`, `confluence.*`, `/display/…`), a Google Docs/Drive link, the whole word "evidence", or a link to an ADR that exists **and is accepted** |
| `adr_refs` | every `docs/adr/NNNN-slug.md`, `adr/N-slug.md`, `ADR-15`, `ADR 15`, `ADR #15` in the description, resolved against `ADR_DIR`: the ADR's status, `missing` (no such file) or `unverified` (folder not available) |
| `triage.issue_type`, `triage.priority` | fields named Type / Issue Type and Priority |
| `triage.labels` | issue tags visible to the token's account |
| `triage.components` | fields named Subsystem(s) / Component(s), single or multi value |
| `triage.due_date` | field named Due Date / Deadline (date field), `yyyy-MM-dd` in UTC |
| `triage.cvss_score` | highest CVSS base score in summary + description (`CVSS 9.8`, `CVSS 3.x base score: 9.8`, `CVSS v3.1 9.1`; vectors such as `CVSS:3.1/AV:N/…` are not mistaken for scores) |

The description itself is never returned (prompt-injection guard). Errors come back as tool
results with `isError: true` and a short message (`HTTP 401 - token is missing, invalid or expired`).

## `youtrack_count_issues`

Parameter: `search_query`. Pages `GET /api/issues?fields=id,idReadable&$top=500&$skip=…` and returns
`{"count": n, "capped": false}`; `capped` is true above 10 000 issues. Used for work in progress.

## `adr_list`, `adr_read`

Read `*.md` files named `NNNN-slug.md` in `ADR_DIR`. Supported layouts: MADR 2 list items
(`* Status: accepted`), MADR 3/4 YAML front matter (`status: accepted`), Nygard (`## Status`
section). `superseded by ADR-0020` sets `superseded_by`. Statuses are normalized to
proposed / accepted / rejected / deprecated / superseded / unknown. `adr_read` takes a number only.

## Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `YOUTRACK_BASE_URL` | `http://localhost:8089` | Instance root, e.g. `https://acme.youtrack.cloud` or `https://tracker.acme.com/youtrack` |
| `YOUTRACK_TOKEN` | — | Permanent token, sent as `Authorization: Bearer` |
| `YOUTRACK_MINUTES_PER_STORY_POINT` | `480` | Estimation fallback divisor; `0` disables the fallback |
| `ADR_DIR` | `docs/adr` (`/adr` in the image) | ADR folder; relative paths resolve against the server's working directory |

## Network

- Proxies: `HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY` and `-Dhttp(s).proxyHost` are honoured. `localhost`,
  `127.*`, `::1`, `*.localhost` and `host.docker.internal` are always reached directly. With Docker
  pass them through: `docker run -e HTTPS_PROXY -e NO_PROXY …`.
- YouTrack running on your own machine, server in Docker: use
  `YOUTRACK_BASE_URL=http://host.docker.internal:8080` and on Linux add
  `--add-host=host.docker.internal:host-gateway` to `docker run`.

## Calculator configuration

`.backlog-prioritizer.json` (metrics, weights, localized triage names):
[skills/backlog-prioritization-engine/references/configuration.md](../skills/backlog-prioritization-engine/references/configuration.md).
