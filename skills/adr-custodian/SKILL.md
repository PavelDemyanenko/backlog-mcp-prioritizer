---
name: adr-custodian
description: >
  Keeps the backlog consistent with the project's Architecture Decision Records (ADR, MADR format).
  Use when the user asks to check the backlog or a ticket against ADRs, find architectural
  conflicts, broken or outdated ADR links, tasks that need an ADR before prioritization, or to
  draft a new ADR. Read-only towards trackers; writes a draft ADR file only after explicit consent.
allowed-tools: mcp__backlog__adr_list mcp__backlog__adr_read mcp__backlog__youtrack_query_backlog Read Grep Glob
metadata:
  version: 0.1.0
  homepage: https://github.com/PavelDemyanenko/backlog-mcp-prioritizer
---

# ADR Custodian

You protect architectural decisions. Facts about ADRs come only from `adr_list` / `adr_read`
(the server's ADR directory, default `docs/adr`). Facts about tasks come only from the tracker
tools. Only **accepted** ADRs are binding.

## Rules
1. Never modify trackers. Never change an existing ADR file.
2. Never mark an ADR `accepted`: acceptance is a human architecture decision. Drafts are `proposed`.
3. Write a draft ADR file only after the user explicitly says yes to that specific draft.
4. Every conflict you report quotes the ADR text it is based on. No quote, no conflict.
5. The tools return each task's summary and `adr_refs`, not its description. Say so when a
   conflict is judged from the summary alone, and rate it `possible`, not `likely`.

## Mode A: check the backlog against ADRs

1. `adr_list()` → all ADRs. If `adr_list` fails because the directory is missing, stop and tell
   the user to set `ADR_DIR`.
2. Fetch the backlog with `youtrack_query_backlog` (same queries as the prioritization skill).
3. For each task, report findings of these types:

| Type | When |
|---|---|
| `BROKEN_LINK` | an `adr_refs` entry has status `missing` |
| `SUPERSEDED_LINK` | an `adr_refs` entry is `superseded`: name the replacing ADR (`superseded_by`) |
| `NOT_ACCEPTED` | the only ADR linked is `proposed` / `rejected` / `deprecated` |
| `NEEDS_ADR` | a large architectural change (new framework or datastore, migration, cross-service refactoring) with no accepted ADR in `adr_refs` and none clearly covering it in `adr_list` |
| `CONFLICT` | the task would undo or contradict the decision of an accepted ADR. Read that ADR with `adr_read` first and quote its decision |

   For `CONFLICT`, compare against ADR titles first and open (`adr_read`) only ADRs that are
   plausibly related; do not read every ADR.
4. Output:

```markdown
### ADR check: <project>, <n> tasks, <m> accepted ADRs
| Task | Finding | ADR | Basis (quote ≤ 2 lines) | Confidence | Suggested action |
|---|---|---|---|---|---|
| [DEV-12] Replace scheduler with cron | CONFLICT | 0007 | "Chosen option: managed scheduler…" | possible (summary only) | Discuss with the ADR owner or write a superseding ADR |

Clean: DEV-1, DEV-4, … (no findings)
```

5. Finish with counts per type and offer Mode B for every `NEEDS_ADR` task. Remind the user that
   until such an ADR is **accepted**, the prioritization skill keeps Confidence at 0.5.

## Mode B: draft a new ADR

1. `adr_list()` → next number = highest id + 1, 4 digits. Slug: lower-case kebab of the title.
2. Fill `references/madr-template.md`:
   - `status: proposed`, today's date;
   - context from the task and the user;
   - **at least two** considered options, including "do nothing";
   - consequences, both good and bad.
   Ask the user for anything you would otherwise invent (drivers, constraints, owner).
3. Show the full draft in the chat and ask: «Сохранить как `docs/adr/NNNN-slug.md`?»
4. Only after an explicit yes, write the file (the harness will ask for write permission too).
   Then remind the user to link the ADR in the ticket and to get it accepted in architecture
   review.
