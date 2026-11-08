package backlogmcp.backlog;

import java.math.BigDecimal;
import java.util.List;

import backlogmcp.adr.AdrRef;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.annotation.JsonPropertyOrder;

/**
 * Normalized, tracker-agnostic issue: the public contract of the {@code *_query_backlog} tools.
 * The spec §8.2 fields stay flat and unchanged; {@code story_points_source} and the nested
 * {@code triage} object are additive extensions. Nulls are kept explicit so the agent can tell
 * "unknown" from "absent".
 *
 * @param storyPointsSource null exactly when {@code storyPoints} is null
 * @param adrRefs           ADRs referenced in the description, resolved against the ADR directory; never null
 * @param triage            never null ({@link TriageSignals#NONE} when nothing is known)
 */
@JsonInclude(JsonInclude.Include.ALWAYS)
@JsonPropertyOrder({"id", "summary", "status", "story_points", "story_points_source", "evidence_found_in_text", "adr_refs", "triage"})
public record BacklogIssue(
        @JsonProperty("id") String id,
        @JsonProperty("summary") String summary,
        @JsonProperty("status") String status,
        @JsonProperty("story_points") BigDecimal storyPoints,
        @JsonProperty("story_points_source") StoryPointsSource storyPointsSource,
        @JsonProperty("evidence_found_in_text") boolean evidenceFoundInText,
        @JsonProperty("adr_refs") List<AdrRef> adrRefs,
        @JsonProperty("triage") TriageSignals triage) {

    public BacklogIssue {
        if ((storyPoints == null) != (storyPointsSource == null)) {
            throw new IllegalArgumentException("story_points and story_points_source must be both set or both null");
        }
        adrRefs = adrRefs == null ? List.of() : List.copyOf(adrRefs);
        triage = triage == null ? TriageSignals.NONE : triage;
    }

    /** Without ADR references (trackers/tests that do not resolve them). */
    public BacklogIssue(String id, String summary, String status, BigDecimal storyPoints,
                        StoryPointsSource storyPointsSource, boolean evidenceFoundInText, TriageSignals triage) {
        this(id, summary, status, storyPoints, storyPointsSource, evidenceFoundInText, List.of(), triage);
    }

    /** Core fields only (no triage signals), e.g. for tests and trackers without such data. */
    public BacklogIssue(String id, String summary, String status, BigDecimal storyPoints,
                        StoryPointsSource storyPointsSource, boolean evidenceFoundInText) {
        this(id, summary, status, storyPoints, storyPointsSource, evidenceFoundInText, List.of(), TriageSignals.NONE);
    }

    /** Same issue without triage signals: lets tests compare the core contract separately. */
    public BacklogIssue core() {
        return new BacklogIssue(id, summary, status, storyPoints, storyPointsSource, evidenceFoundInText);
    }
}
