---
status: accepted
date: 2026-11-09
decision-makers: Pavel Demyanenko
---
# An ADR link counts as evidence only if the ADR exists and is accepted

## Context and Problem Statement

Architectural tasks get high confidence when an approved architecture decision backs them. A plain
text match on `docs/adr/NNNN-*.md` would also reward links to missing, proposed or superseded ADRs.

## Decision Drivers

* Evidence must reflect real, approved decisions.
* Verification must be deterministic and server-side (ADR-0002).

## Considered Options

* Resolve every ADR reference against the project's ADR folder; only `accepted` counts
* Count any ADR-looking link
* Let the agent search the ADR folder itself

## Decision Outcome

Chosen option: "resolve against `ADR_DIR`, only accepted counts". The tools return `adr_refs` with
the status (accepted, proposed, superseded, `missing`, `unverified`), and the calculator gives an
architectural task Confidence 1.0 only with an accepted ADR.

### Consequences

* Good, because broken and outdated links become visible (the adr-custodian skill reports them).
* Bad, because without a reachable ADR folder all ADR links are `unverified` and do not count.

### Confirmation

`AdrTest`, `YouTrackIssueNormalizerTest`, calculator tests for missing/proposed/superseded ADRs.
