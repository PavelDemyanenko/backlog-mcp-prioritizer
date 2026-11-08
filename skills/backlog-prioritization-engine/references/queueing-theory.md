# Queueing Penalty (spec §1, §8.3)

## Why
For a queue with utilization ρ (M/M/1), the expected time in system is `W = S / (1 − ρ)`, where S
is the pure service time. Delay is not linear in load:

| ρ | W / S |
|---|---|
| 0.50 | 2× |
| 0.80 | 5× |
| 0.85 | 6.7× |
| 0.90 | 10× |
| 0.95 | 20× |
| 0.99 | 100× |

Little's Law (`WIP = throughput × lead time`) gives the same message: at fixed throughput more
work in progress means proportionally longer lead time. A task "worth 5 days" costs far more
calendar time when the team is saturated.

## Rule
`ρ = in_progress / capacity`, measured live through the MCP tools (Step 2 of SKILL.md).

| ρ | Effort multiplier |
|---|---|
| ≤ 0.85 | × 1.0 |
| > 0.85 | × 1.5 |
| > 0.95 | × 3.0 |

## What the penalty changes, and what it does not
All tasks in one backlog share the team's ρ, so the multiplier scales every C equally and
**does not change the order** within that ranking. It changes:
- the absolute Priority values (comparable across teams and over time, e.g. for drift tracking);
- the capacity recommendation: at ρ > 0.85 the right move is to finish work, not start more.

The penalty may never be skipped (refusal rule): hiding saturation is exactly the bias it exists
to prevent.
