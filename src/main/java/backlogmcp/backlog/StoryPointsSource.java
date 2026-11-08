package backlogmcp.backlog;

import com.fasterxml.jackson.annotation.JsonValue;

/**
 * Where {@code story_points} came from. The Cost term of the priority formula is the
 * denominator ({@code C^0.7}), so the agent and the reviewer must be able to tell a team
 * estimate from a number converted from a developer's time estimate.
 */
public enum StoryPointsSource {

    /** The tracker's story points field (team estimate). */
    CUSTOM_FIELD("custom_field"),

    /** Derived from the original time estimate (YouTrack period field {@code Estimation}). */
    TIME_ESTIMATE_FALLBACK("time_estimate_fallback");

    private final String wireName;

    StoryPointsSource(String wireName) {
        this.wireName = wireName;
    }

    @JsonValue
    public String wireName() {
        return wireName;
    }
}
