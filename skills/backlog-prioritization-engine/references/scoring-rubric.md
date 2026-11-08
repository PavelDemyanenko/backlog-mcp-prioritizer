# Scoring rubric

## Value weights (defaults, global, sum = 100%)

These defaults suit a platform/engineering team. A project can replace them with its own metrics
and weights in `.backlog-prioritizer.json` (see `configuration.md`).

| Key | Metric | Weight |
|---|---|---|
| `scaling` | Scaling & coverage: how many teams/users benefit | 30% |
| `code_quality` | Code / output quality | 20% |
| `latency` | Latency | 15% |
| `reliability` | Reliability & stability | 15% |
| `performance` | Performance / efficiency | 10% |
| `dev_speed` | Team dev speed | 5% |
| `tech_risk` | Tech risk / security | 5% |

`V = (Σ weight × impact) / 5 × Confidence`, so V ∈ [0, 1].

**Compliance work (WSJF risk reduction, spec §4).** When a task's labels, components or type mark
it as legal/compliance work (compliance, legal, regulatory, GDPR, 152-FZ, PCI, SOX), its
`tech_risk` impact counts like the top metric: `V = max(V, 0.30 × tech_risk / 5 × Confidence)`.
The calculator applies this from the tool's triage signals; you only score `tech_risk` honestly
(the risk the task removes). Evidence caps and Confidence still apply.

## Impact scale (0–5) and Evidence Tiers

| Impact | Meaning | Requires |
|---|---|---|
| 5 | Transformational | `evidence_found_in_text = true` |
| 4 | High | `evidence_found_in_text = true` |
| 3 | Substantial | documented user interviews, metrics or an ADR. With the flag `false`, only if the user points you to that documentation; otherwise ≤ 2 |
| 2 | Small | anecdotal signal |
| 1 | Minimal | hypothesis |
| 0 | None / unknown | — |

The calculator hard-caps every Impact at 3 when the flag is `false`.

| Tier | Condition | Confidence |
|---|---|---|
| Tier 1 (High) | flag `true` (Confluence / Google Docs link, "evidence" in the description, or a link to an **accepted** ADR) and, for architectural changes, an accepted ADR in `adr_refs` or `adr_by_topic` | 1.0 |
| Tier 3–4 (Low) | flag `false`, or architectural change without an accepted ADR | 0.5 |

A link to an ADR that is missing, proposed, superseded or unverified (ADR directory not available)
is not evidence. The server resolves every reference against `ADR_DIR` (default `docs/adr`).

## Urgency (Cost of Delay), 1–5

| U | Condition |
|---|---|
| 1 | No deadline; delay costs nothing measurable |
| 2 | Soft preference, no quantified loss |
| 3 | Delay > 3 months causes quantifiable value loss |
| 4 | Committed date with a named stakeholder; measurable loss within a quarter |
| 5 | Hard external deadline; severe business consequence if missed |

Judge by consequence of delay, never by the requester's tone or seniority.

**Operational deadlines** (expiring TLS certificate, licence, vendor quota, end-of-support date):
if missing the date takes a key system down or blocks teams, that is a hard deadline with a severe
consequence → **U = 5**, even though it is not a legal deadline. Such tasks are ranked, not
CRITICAL: only the four thresholds below skip the ranking.

## How this relates to WSJF and RICE (spec §4)

One comparable score is used for the whole backlog; mixing two scales would make the ranking
meaningless. The formula embeds both methods:
- **WSJF:** Cost of Delay ≈ V × U, Job Size = C → Priority = CoD / C^0.7. Deadline and compliance
  items are driven by U.
- **RICE:** Reach ≈ `scaling`, Impact = the other metrics, Confidence = the Evidence Tier,
  Effort = C. Standard product features are driven by V.

`C^0.7` (instead of C) softens the bias against large but valuable items that a linear
denominator would always push to the bottom.

## Critical thresholds (skip scoring)

- Active P1 incident / key system downtime > 15 min
- CVSS ≥ 9.0 vulnerability
- Mandatory legal deadline < 30 days
- Direct financial risk > 500 000 RUB

CVSS, P1 incident and legal deadline are evaluated automatically from the tools' `triage`
signals (see SKILL.md Step 3); financial risk and ambiguous cases must be confirmed by the user.
