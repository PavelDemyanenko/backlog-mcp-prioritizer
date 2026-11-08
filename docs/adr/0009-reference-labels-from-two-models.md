---
status: accepted
date: 2026-11-08
decision-makers: Pavel Demyanenko
---
# Reference labels for evals come from two other models

## Context and Problem Statement

NDCG@10 needs reference relevance labels for the Golden Dataset. ADR-0005/0006 assumed independent
human experts. The decision maker chose labels produced by models instead.

## Decision Drivers

* Get a ranking-quality metric now instead of waiting for expert time.
* Keep the reference independent of the agent as far as possible.
* Be explicit about what the metric measures.

## Considered Options

* Two other models label in isolation (expert materials only), consensus with `--proxy`
* Human experts (`evals/golden/LABELING.md`)
* The agent's own model as labeler

## Decision Outcome

Chosen option: "two other models", because it gives a usable reference immediately while keeping
the agent's model (Opus 5.5) out of the labels.

* Labelers: Sonnet 5.5 and Haiku 5.5, each in an isolated workspace with only `tasks.md`,
  `template.csv`, `LABELING.md` and `scoring-rubric.md` (`evals/golden/proxy_label.sh`).
* `consensus.py --proxy` resolves disagreements automatically (critical: yes if any rater says yes;
  relevance/urgency: mean) and marks the file `"source": "model-proxy"`.
* `gold-standard.model-proxy.json` is the default reference of `run_eval.py`; a human
  `gold-standard.json`, if ever produced, takes precedence.

### Consequences

* Good, because NDCG@10 is available now (first value 0.925; κ relevance 0.744 between labelers).
* Bad, because models of one family reason alike: NDCG measures agreement with other models, not
  with the team. Every report states this in its first line.
* Bad, because tuning the skill to these labels (ADR-0008) can overfit to model preferences.

### Confirmation

`evals/golden/README.md` (baselines), report header of `run_eval.py`, `test_eval.py`
(`test_proxy_mode_auto_resolves_and_marks_source`).
