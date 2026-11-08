---
status: "superseded by ADR-0006"
date: 2026-11-08
decision-makers: Pavel Demyanenko
---
# Gate merges on a Golden Dataset eval: NDCG@10, critical recall and rule compliance

## Context and Problem Statement

Changes to the skill, prompts or server can silently degrade ranking quality (agent and data drift,
spec §6). AGENTS.md §3 requires blocking a merge when NDCG@k < 0.90.

## Decision Drivers

* Ground truth must come from independent experts (Cohen's kappa), not from the model.
* A missed critical item is never acceptable.
* Live LLM runs cost tokens, so they cannot run on every commit.

## Considered Options

* Live eval on PRs touching skills, evals or server code, weekly and manual. Gates: mean NDCG@10 ≥ 0.90,
  critical recall = 1.0 in every run, all compliance checks pass
* LLM-as-a-judge scoring of the agent's report
* Do nothing (unit and E2E tests only)

## Decision Outcome

Chosen option: "path-filtered live eval with three gates", because it measures ranking quality
against expert labels, catches rule violations deterministically and keeps cost bounded.

### Consequences

* Good, because skill changes cannot merge with worse ranking or missed critical items.
* Bad, because NDCG needs expert labeling first; until then only `--compliance-only` runs.
* Bad, because each run costs roughly $0.60 at API list prices; a 3-run eval about $1.8.

### Confirmation

`.github/workflows/golden-eval.yml` as a required status check on `main`; `evals/golden/test_eval.py`.
