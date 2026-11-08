# Worked example: one prioritization, start to finish

A real session from the pilot (2026-11-09): Claude Code with the skill, the MCP server pointed at a
**real YouTrack 2026.2** ([sandbox](../e2e/youtrack-sandbox/README.md)) holding project `GOLD`, the
synthetic 24-issue backlog of the [Golden Dataset](../evals/golden/dataset.json). The ranking was
approved. Issue titles are in Russian in the dataset; they are translated in the tables below. Reproduce the numbers yourself:

```bash
python3 -I skills/backlog-prioritization-engine/scripts/priority.py docs/example/prio-input.json
```

[`example/prio-input.json`](example/prio-input.json) is exactly what the agent passed to the
calculator: YouTrack data copied verbatim from the tools plus the agent's Impact/Urgency judgments.
[`example/ranking.md`](example/ranking.md) is the full output, including the math trace.

## 1. The conversation

> **User:** prioritize the backlog
>
> **Agent** calls `youtrack_query_backlog` → 24 open issues, `youtrack_count_issues("project: GOLD
> State: {In Progress}")` → 9, then asks:
> 1. How many items can the team work on in parallel?
> 2. GOLD-15 has priority *Show-stopper* but type *Bug*: is it an active P1 incident (downtime > 15 min)?
> 3. GOLD-16 is due in 6 days without a legal label: is it a mandatory legal deadline?
> 4. Does any task carry a direct financial risk above the threshold (not visible in YouTrack)?
>
> **User:** the team handles 3 tasks
>
> **Agent** treats the unanswered questions conservatively (GOLD-15/16 stay *non-critical, needs
> confirmation*), checks ADRs for the architectural task GOLD-8 (`adr_list` → no accepted ADR covers
> it), judges Impact/Urgency, runs the calculator once, shows the report and asks **Approve / Reject**.
>
> **User:** Approve

## 2. The result (top of the report)

**Queue:** rho = in_progress / capacity = 9 / 3 = 3.00 → Effort penalty ×3.0

| Rank | Task | Critical? | V (Value) | U | C (Cost) | Priority | Notes / Evidence Tier |
|---|---|---|---|---|---|---|---|
| - | GOLD-3 CVE-2026-40211: RCE in template engine | YES | - | - | - | - | CVSS 9.8 ≥ 9 (auto) |
| - | GOLD-4 Generation service down for teams in zone B | YES | - | - | - | - | P1 incident (Show-stopper Incident) (auto) |
| - | GOLD-5 Remove personal data from audit logs (152-FZ) | YES | - | - | - | - | legal deadline in 16 days (auto) |
| 1 | GOLD-14 Rate limiting for the generation API | NO | 0.27 (Conf:1.0) | 4 | 15.00 (×3.0) | **0.16** | Tier 1 |
| 2 | GOLD-21 Cut p95 generation latency to 2 s | NO | 0.27 (Conf:1.0) | 4 | 24.00 (×3.0) | **0.12** | Tier 1 |
| 3 | GOLD-1 Onboard 12 product teams | NO | 0.33 (Conf:1.0) | 3 | 24.00 (×3.0) | **0.11** | Tier 1 |
| 4 | GOLD-16 Renew the internal API TLS certificate | NO | 0.04 (Conf:0.5) | 5 | 3.00 (×3.0) | **0.09** | Tier 3-4 |
| 5 | GOLD-11 Faster MCP server cold start | NO | 0.18 (Conf:1.0) | 2 | 9.00 (×3.0) | **0.08** | Tier 1 |
| 6 | GOLD-10 Generate unit tests for generated code | NO | 0.22 (Conf:1.0) | 3 | 24.00 (×3.0) | **0.07** | Tier 1 |
| 7 | GOLD-6 Prepare the platform for the PCI DSS audit | NO | 0.24 (Conf:1.0) | 4 | 39.00 (×3.0) | **0.07** | compliance rule applied |
| … | 11 more ranked, see [ranking.md](example/ranking.md) | | | | | | |

Not ranked: GOLD-9 and GOLD-13 (zero value), GOLD-12 (no estimate).
Awaiting confirmation: GOLD-15, GOLD-16.

## 3. How to read it

**The formula.** `Priority = V × U / C^0.7`
- `V` (Value) = Σ weight × Impact / 5 × Confidence, between 0 and 1. Impact is 0–5 per metric,
  Confidence is 1.0 with evidence and 0.5 without.
- `U` (Urgency) is 1–5, the cost of delay.
- `C` (Cost) = story points × queueing penalty. The exponent 0.7 softens the bias against large
  but valuable items.

**GOLD-14, rank 1.** Reliability 4 and tech risk 3 from a linked post-mortem (evidence → Confidence 1.0), Urgency 4:
```
V = (0.30*2 + 0.15*4 + 0.05*3) / 5 * 1.0 = 0.27;  C = 5 * 3.0 = 15;  P = 0.27 * 4 / 15^0.7 = 0.162
```

**GOLD-16, rank 4 with V = 0.04.** No evidence link, so Confidence is 0.5 and Impact is capped at 3. It still ranks high: it is cheap (1 SP) and an expiring certificate takes an API down, which is Urgency 5 ([ADR-0005](adr/0005-compliance-risk-and-operational-deadlines.md)):
```
P = 0.04 * 5 / 3^0.7 = 0.093
```

**GOLD-6, rank 7.** Audit preparation removes a compliance risk (tech_risk 4). With the default weights that is only 5 % of Value (V = 0.07). The compliance rule counts it like the top metric:
```
V = 0.30*4 / 5 * 1.0 = 0.24
```

**GOLD-8, rank 17.** A large architectural rewrite. It has a Confluence link, but no accepted ADR → Confidence 0.5 ([ADR-0004](adr/0004-adr-links-count-only-if-accepted.md)). At 21 SP × 3.0 it is also the most expensive item.

**GOLD-23.** The ticket links `ADR-0031`, which does not exist in the repo (`adr_refs: missing`). Not evidence, and the note in the report says so.

**Critical items** are not scored at all; the calculator decides them from the tool's triage signals:
- GOLD-3: CVSS 9.8.
- GOLD-4: an incident with P1 priority.
- GOLD-5: compliance label and due in 16 days.

**Capacity.** ρ = 9 / 3 = 3.0: three times more work in progress than the team can carry. The report recommends:
- start nothing new;
- swap current work for the three critical items;
- after them, take GOLD-14;
- renew the certificate (1 SP) before its date.

## 4. A known quirk visible here

At ρ = 3.0 every priority shrinks by 3^0.7 ≈ 2.2, so the tie rule ("equal at 2 decimals → lower cost
wins") fires more often:
- GOLD-6 (P = 0.0739) and GOLD-10 (P = 0.0714) both round to 0.07, so the cheaper GOLD-10 ranks
  above GOLD-6.
- GOLD-22 (P = 0.0146) ranks below GOLD-23 (P = 0.0053) only because both round to 0.01.

With a lower load the same tasks do not tie and the order differs at ranks 6–9 and 14–18 (see the
next section). The team's load should scale all priorities equally, not reorder them; this is an
open issue.

## 5. Try it on your project

Change the team capacity in `example/prio-input.json` (`"capacity": 3` → `12`) and re-run the
calculator. The penalty drops from ×3.0 to ×1.0 and the recommendation changes. Because of the tie
rule in section 4, the order also changes at ranks 6–9 and 14–18; the top five stay the same.

To use your own metrics or localized triage names, add `.backlog-prioritizer.json` ([configuration](../skills/backlog-prioritization-engine/references/configuration.md)).
