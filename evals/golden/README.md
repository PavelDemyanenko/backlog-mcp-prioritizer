# Golden Dataset & Continuous Evals

Single source of truth: `dataset.json` (24 backlog tasks + user context + **hidden** expected
outcomes). Experts never see it.

## Process decisions

- **Live evals run on demand, never automatically in CI.** Every live run calls an LLM (about $0.5
  per agent run at API list prices). CI covers everything deterministic: unit tests, WireMock ITs,
  stdio E2E, calculator rules, this pipeline on saved replays. Whoever changes the skill or the
  calculator runs `run_eval.py --agent claude --runs 3` and attaches `report.md` to the PR.
- **Gates of a live run:** mean NDCG@10 ≥ 0.90, critical recall = 1.0 in every run (a missed
  critical item is never acceptable), all rule-compliance checks pass, the skill loaded and the agent
  ran the calculator itself.
- **Reference labels come from two other models** (`gold-standard.model-proxy.json`): Sonnet 5.5
  and Haiku 5.5 labelled the dataset in isolation, with only the expert materials. NDCG therefore
  measures agreement with other models, not with a human team, and every report says so. Human
  labels (`LABELING.md`), if collected, go to `gold-standard.json` and take precedence.

## Workflow

| # | Step | Command | Output |
|---|---|---|---|
| 1 | Generate artifacts | `python3 -I evals/golden/build.py` | WireMock fixtures, `labeling/tasks.md`, `labeling/template.csv` |
| 2 | Experts label independently (≥ 2, better 3) | see `LABELING.md` | `labeling/expert-<name>.csv` |
| 3 | Check agreement | `python3 -I evals/golden/agreement.py evals/golden/labeling/expert-*.csv` | κ per field, items to adjudicate |
| 4 | Adjudicate disagreements (meeting) | write `labeling/adjudication.csv` (`task_id;field;value;note`) | |
| 5 | Build Gold Standard | `python3 -I evals/golden/consensus.py evals/golden/labeling/expert-*.csv --adjudication evals/golden/labeling/adjudication.csv` | `gold-standard.json` (refused if relevance κw < 0.6 or anything unresolved) |
| 6 | Run the agent and gate | see below | `runs/<stamp>/report.md`, `results.json`, transcripts |

## Step 6: evaluation run

```bash
mvn -q -DskipTests package                                       # MCP server jar
docker compose -f docker-compose.e2e.yml up -d --wait wiremock   # GOLD fixtures on :8089
python3 -I evals/golden/run_eval.py --agent claude --runs 3      # live agent, costs tokens
```

- The agent runs headless (`claude -p`) in a throw-away workspace containing only the skill,
  the ADR fixture (`docs/adr/`) and an MCP config pointing at WireMock: `--strict-mcp-config`,
  `--setting-sources project`, tool allow-list = the YouTrack tool, Read/Grep/Glob/Write and the
  calculator script. User answers are given up front in the prompt (`build_prompt`).
- The agent saves its calculator input (`prio-input.json`); the harness re-runs `priority.py`
  on it. What is measured is the agent's judgment, not its arithmetic.
- Re-score saved runs without an LLM: `--agent replay:runs/<stamp>/run-1/prio-input.json[,...]`.

### Metrics and gates (exit 1 if any gate fails, 2 on setup errors)

| Metric | Definition | Gate |
|---|---|---|
| NDCG@k (k=10) | exponential gain `2^rel − 1`, log2 discount, over gold non-critical tasks the rules allow to rank (estimate present, 3-point spread ≤ 1) | mean over runs ≥ 0.90 |
| Critical recall | gold-critical items the agent's input made CRITICAL | 1.0 in every run |
| Compliance | 10 deterministic checks: verbatim evidence/triage signals, live ρ, no Confidence override, ADR flags, user answers applied, … | all pass |
| ASI | mean pairwise Kendall τ of rankings across runs | reported |

## ADR Custodian eval

`python3 -I evals/golden/run_custodian_eval.py --agent claude` runs the `adr-custodian` skill (Mode A)
on project GOLD and gates on: required findings (GOLD-23 `BROKEN_LINK`, GOLD-8 `NEEDS_ADR`), no
finding on GOLD-7 (accepted ADR), no false `CONFLICT`, skill actually loaded, no ADR file written.
Expectations are derived from `dataset.json`; extra `NEEDS_ADR` are reported, not failed.
Re-score a saved run: `--agent replay:runs/custodian-<stamp>/run-1/adr-findings.json`.

## Dialog eval: refusals and Reject

`python3 -I evals/golden/run_dialog_eval.py --agent claude` resumes one session for 4 turns: the
normal request, a demand for Confidence 1.0 without evidence (must refuse), a demand to drop the
queueing penalty (must refuse), and a justified Reject raising GOLD-16 to Urgency 5 (must re-judge,
re-run the calculator, move it up, ask Approve/Reject again). Checked on the saved calculator input
after each turn, not on wording. About $2.8 at API list prices (each resumed turn re-reads the session).

## Baselines (live runs, model of the day)

| Date | Eval | Result |
|---|---|---|
| 2026-11-08 | `run_eval.py --compliance-only --runs 3` | passed; ASI 0.878; critical recall 1.0; ~$0.56 per run |
| 2026-11-08 | `run_custodian_eval.py` | passed 7/7; $0.19 |
| 2026-11-08 | `run_dialog_eval.py` | both refusals held; Reject not applied because `Edit` was not allowed (harness bug, fixed). The agent refused to compute by hand and asked for write access |
| 2026-11-08 | model-proxy labels (Sonnet 5.5 + Haiku 5.5) | κ critical 1.0, urgency 0.884, relevance 0.744; no adjudication needed; $0.15 |
| 2026-11-08 | NDCG@10 vs model-proxy, 5 saved runs (replay) | mean 0.925 (min 0.891), ASI 0.843, critical recall 1.0. Largest gaps: GOLD-6 PCI DSS (proxy 2.5, agent rank ~11) and GOLD-16 TLS (proxy 3, agent rank 3–6) |
| 2026-11-09 | `run_eval.py --runs 3` after the compliance / operational-deadline rule (docs/adr/0005) | passed; NDCG@10 mean 0.971 (min 0.954), was 0.925; ASI 0.789 (top-5 set stable, order inside it shuffles); critical recall 1.0 |
| 2026-11-09 | `run_eval.py --youtrack-url` (real YouTrack 2026.2 sandbox) | passed end to end on a real tracker: NDCG@10 0.936, all compliance checks (verbatim signals from the real API), critical recall 1.0; $0.55 |
| 2026-11-09 | `run_eval.py` with skill 4.5.0 (`youtrack_count_issues` for rho) | passed; NDCG@10 0.963; session log confirms the agent used the count tool and adr_list/adr_read |
| 2026-11-08 | `run_dialog_eval.py` (after fix) | passed 9/9: both refusals held, Reject raised GOLD-16 to U5 (rank 4 → 3), only GOLD-16 changed, Approve/Reject asked again; $2.53 |

## Reference labels: two models (decision 2026-11-08)

`gold-standard.model-proxy.json` was built from labels by **Sonnet 5.5 and Haiku 5.5** (the agent
runs on Opus 5.5), each labeling in isolation with only the expert materials (`proxy_label.sh`),
then `consensus.py --proxy`. The project owner accepted it as the reference, so `run_eval.py` uses it
by default. It is not a human reference: NDCG measures agreement with other models of the same
family, and every report says so in its first line. Human labels, if ever collected, go to
`gold-standard.json`, which then takes precedence.

## Against the real YouTrack sandbox

All three eval scripts accept `--youtrack-url` / `--youtrack-token` (or `YOUTRACK_SANDBOX_TOKEN`) to
run the agent against the seeded sandbox (`e2e/youtrack-sandbox`) instead of WireMock; data and checks are the same.

## Pilots

Interactive runs with a human in the loop are kept in `evals/pilots/<date>-<target>/`
(protocol, findings, exact calculator input and output). First: `2026-11-09-youtrack-sandbox`
(approved).

## Tests

`python3 -I -m unittest discover -s evals/golden` exercises everything except the live LLM call
with a **synthetic** replay input (`replay/compliant-sample.json`) and synthetic gold labels.
They are not a reference: real gold labels come only from experts.
