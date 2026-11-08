---
status: accepted
date: 2026-11-08
decision-makers: Pavel Demyanenko
---
# Run live LLM evaluations on demand only, never automatically in CI

## Context and Problem Statement

ADR-0005 made the live Golden Dataset eval a required check on PRs that touch the skill, evals or
server code, plus a weekly run. Every live run calls an LLM (about $0.60 per agent run at API list
prices). The decision maker chose not to run live LLM tests in CI.

## Decision Drivers

* No automatic spend on API tokens.
* Every check in automatic CI must be deterministic and free.
* Ranking quality must still be measurable before a skill change ships.

## Considered Options

* Live evals on demand only: locally (`run_eval.py --agent claude`) or manual `golden-eval` workflow
* Keep ADR-0005: live eval as a required check on PRs plus weekly
* Do nothing: no live evals at all

## Decision Outcome

Chosen option: "live evals on demand only", because it removes automatic spend while keeping the
same harness, gates and artifacts available whenever someone runs them.

### Consequences

* Good, because automatic CI (`ci.yml`) stays fast, free and deterministic: unit, Testcontainers,
  STDIO E2E, calculator rules, eval pipeline on replays, artifact checks.
* Bad, because a skill change can merge without a live NDCG check; whoever changes the skill must
  run the eval and attach `report.md` to the PR.
* Bad, because drift (ASI) is no longer tracked weekly by default.

### Confirmation

`.github/workflows/golden-eval.yml` has only `workflow_dispatch`; required check on `main` is
`build-and-test` only.

## More Information

Supersedes ADR-0005. Gates themselves (NDCG@10 ≥ 0.90, critical recall = 1.0, compliance) are
unchanged and still apply to every live run.
