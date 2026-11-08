---
status: accepted
date: 2026-11-08
decision-makers: Pavel Demyanenko
---
# An ADR link counts as evidence only if the ADR exists and is accepted

## Context and Problem Statement

AGENTS.md gives architectural tasks Tier 1 confidence when they are backed by an approved ADR.
Originally any text matching `docs/adr/NNNN-*.md` set `evidence_found_in_text = true`, so a link to
a missing, proposed or superseded ADR inflated Confidence (Golden task GOLD-23).

## Decision Drivers

* Evidence Tiers must reflect real, approved decisions.
* Deterministic, server-side verification (see ADR-0002).

## Considered Options

* Resolve every ADR reference against `ADR_DIR`; only `accepted` counts
* Count any ADR-looking link (previous behaviour)
* Let the agent check `docs/adr` with Grep

## Decision Outcome

Chosen option: "resolve against `ADR_DIR`, only accepted counts", because it closes the inflation
path and gives the agent `adr_refs` with statuses (missing, superseded, unverified) to act on.

### Consequences

* Good, because Tier 1 for architectural work requires an accepted ADR, checked by code.
* Good, because the ADR Custodian can report broken and superseded links.
* Bad, because without a reachable ADR directory all ADR links are `unverified` and do not count.
* Bad, because changing this rule changed Golden Dataset expectations (version 1.1.0).

### Confirmation

`AdrTest`, `GoldenDatasetIT` (GOLD-23 evidence is false), calculator tests for missing, proposed,
superseded and unverified ADRs.
