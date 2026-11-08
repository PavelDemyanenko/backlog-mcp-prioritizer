# Project configuration: `.backlog-prioritizer.json`

Optional file in the root of the project where the agent runs. Without it the defaults apply
(7 metrics in `scoring-rubric.md`, English triage markers). The agent reads it in Step 0 and passes
it to the calculator: `priority.py input.json --config .backlog-prioritizer.json`.

```jsonc
{
  // Replaces the 7 default Value metrics. ids: letters, digits, "_"; weights > 0, sum = 1.0.
  "metrics": [
    {"id": "revenue",      "label": "Revenue or retention impact",     "weight": 0.35},
    {"id": "reach",        "label": "Users / teams affected",          "weight": 0.25},
    {"id": "reliability",  "label": "Reliability & stability",         "weight": 0.20},
    {"id": "dev_speed",    "label": "Team delivery speed",             "weight": 0.10},
    {"id": "tech_risk",    "label": "Security / compliance risk removed", "weight": 0.10}
  ],
  // Metric used by the compliance rule (WSJF risk reduction): for tasks labelled as legal or
  // compliance work, V = max(V, top_weight * risk / 5 * Confidence). null switches the rule off.
  // Default: "tech_risk" if such a metric exists, otherwise null.
  "risk_metric": "tech_risk",

  // Added to the built-in English names (case-insensitive), e.g. for a localized YouTrack.
  "triage": {
    "p1_priorities":  ["Критичный", "Блокирующий"],        // + highest, blocker, show-stopper, p0, p1, urgent
    "incident_types": ["Инцидент", "Авария"],               // + incident, outage
    "legal_markers":  ["комплаенс", "юридическое", "аудит"], // + legal, compliance, regulatory, gdpr, 152-fz, pci, sox, law
    "cvss_critical": 9.0,          // CVSS score that makes a task CRITICAL
    "legal_deadline_days": 30      // legal/compliance due date closer than this -> CRITICAL
  }
}
```

The calculator rejects an invalid file (unknown keys, weights not summing to 1.0, unknown
`risk_metric`) with exit code 2, so a typo never silently changes the ranking.
A ready-to-edit copy: [`backlog-prioritizer.example.json`](backlog-prioritizer.example.json).
