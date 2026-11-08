# Calculator input (`scripts/priority.py`)

```jsonc
{
  "as_of": "2026-11-05",             // today; required when any triage.due_date is set
  "team": {                          // required: Queueing Penalty is mandatory
    "in_progress": 9,                // count from the tracker (Step 2)
    "capacity": 10,                  // from the user
    "in_progress_truncated": false   // true if the WIP query hit limit=100
    // or: "rho": 0.9
  },
  "tasks": [
    {
      "id": "DEV-1",                       // from the tool, unique
      "summary": "…",                      // from the tool
      "evidence_found_in_text": true,      // from the tool, copied verbatim
      "story_points": 5,                   // from the tool (null allowed)
      "story_points_source": "custom_field", // from the tool
      "impacts": {"scaling": 4, "code_quality": 4, "reliability": 3, "dev_speed": 3},  // your judgment, ints 0..5
      "urgency": 3,                        // your judgment, int 1..5
      "architectural": false,              // your judgment: large architectural change? (Step 4)
      "adr_refs": [],                      // from the tool, copied verbatim
      "adr_by_topic": null,                // optional {"id","status"} copied from adr_list
      "estimate3": {"opt": 3, "real": 5, "pess": 8},  // optional, from the user
      "triage": {                          // from the tool, copied verbatim
        "issue_type": "Task", "priority": "Major", "labels": ["architecture"],
        "components": ["MCP"], "due_date": null, "cvss_score": null
      },
      "critical": false,                   // optional, only when confirmed by the user
      "critical_reason": "…",
      "triage_confirmed_not_critical": false, // user rejected a triage candidate
      "not_critical_reason": "…"           // user dismissed an auto-critical rule (shown in Notes)
    }
  ]
}
```

Omitted impact metrics count as 0. Fields not listed (for example a `confidence`) are ignored:
Confidence is always derived from the evidence flag.

Run `python3 -I scripts/priority.py input.json` for Markdown, add `--json` for machine output.
Full worked example: `scripts/example-input.json`. It shows a critical item, a no-evidence cap,
a time-estimate fallback, a missing estimate, a decomposition refusal, two auto-critical items
(legal deadline, CVSS 9.8) and a triage candidate (Blocker bug due in 7 days).

Rule tests: `python3 -I -m unittest discover -s skills/backlog-prioritization-engine/scripts`
