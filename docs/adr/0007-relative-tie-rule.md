---
status: accepted
date: 2026-11-09
decision-makers: Pavel Demyanenko
---
# Treat priorities within 1% as tied (relative), not "equal at 2 decimals"

## Context and Problem Statement

The original tie rule said: if two tasks have equal Priority up to 2 decimal places, the one with
the lower Cost wins. The queueing penalty multiplies every Cost by the same factor (×1.5 or ×3.0), so
every priority shrinks by the same factor. Rounding to 2 decimals then creates ties that do not exist
at a lower load. In the worked example (`docs/example.md`) the order at ranks 6–9 and 14–18 differed
between a team capacity of 3 and 12, although nothing but the load changed.

## Decision Drivers

* The team's load must change absolute priorities and the capacity advice, not the order.
* Keep the intent of the rule: nearly equal priorities → the cheaper task first.
* Deterministic, explainable ties.

## Considered Options

* Relative ties: sort by exact priority; consecutive tasks within 1% of their group's top form a tie
  group, ordered by lower Cost, then id
* Exact comparison only (tie only on identical values)
* Keep rounding to 2 decimals

## Decision Outcome

Chosen option: "relative ties within 1%", because it is invariant to any common factor (penalty, unit
of story points) while keeping "nearly equal → cheaper first". Groups are anchored to their top
priority, so a chain of small differences cannot merge distant tasks.

### Consequences

* Good, because the order is identical for any capacity (tested on the example and the worked input).
* Good, because the displayed 2-decimal value no longer decides anything.
* Bad, because 1% is a convention; tasks 1.1% apart are ordered by priority even if one is far cheaper.

### Confirmation

`TieRule` tests in `scripts/test_priority.py`; `DocsExample` test keeps `docs/example/ranking.md` in sync.
