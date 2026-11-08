package backlogmcp.backlog;

import java.math.BigDecimal;
import java.util.List;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.annotation.JsonPropertyOrder;

/**
 * Facts the agent needs for critical-task triage (P1 incident, CVSS ≥ 9.0, legal deadline),
 * extracted deterministically by the server. The raw description is deliberately NOT exposed:
 * it is large and an injection vector; only these structured signals are.
 *
 * @param issueType  YouTrack "Type" (e.g. Incident, Bug, Task)
 * @param priority   tracker priority name as configured (e.g. Highest, Show-stopper)
 * @param labels     YouTrack tags; never null
 * @param components YouTrack "Subsystem" / "Subsystems" / "Component(s)"; never null
 * @param dueDate    ISO-8601 date ({@code yyyy-MM-dd}) or null
 * @param cvssScore  highest CVSS base score (0.0–10.0) found in summary/description, or null
 */
@JsonInclude(JsonInclude.Include.ALWAYS)
@JsonPropertyOrder({"issue_type", "priority", "labels", "components", "due_date", "cvss_score"})
public record TriageSignals(
        @JsonProperty("issue_type") String issueType,
        @JsonProperty("priority") String priority,
        @JsonProperty("labels") List<String> labels,
        @JsonProperty("components") List<String> components,
        @JsonProperty("due_date") String dueDate,
        @JsonProperty("cvss_score") BigDecimal cvssScore) {

    public static final TriageSignals NONE = new TriageSignals(null, null, List.of(), List.of(), null, null);

    public TriageSignals {
        labels = labels == null ? List.of() : List.copyOf(labels);
        components = components == null ? List.of() : List.copyOf(components);
    }
}
