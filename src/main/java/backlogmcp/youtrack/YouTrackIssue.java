package backlogmcp.youtrack;

import java.util.List;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import tools.jackson.databind.JsonNode;

/**
 * Raw YouTrack issue as returned by {@code GET /api/issues?fields=...}. Internal DTO only:
 * never exposed to the agent (see {@code BacklogIssue}).
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public record YouTrackIssue(
        String idReadable,
        String summary,
        String description,
        List<CustomField> customFields,
        List<Tag> tags) {

    public YouTrackIssue {
        customFields = customFields == null ? List.of() : List.copyOf(customFields);
        tags = tags == null ? List.of() : List.copyOf(tags);
    }

    /** Projection used for counting ({@code fields=id}). */
    @JsonIgnoreProperties(ignoreUnknown = true)
    public record IdOnly(String id, String idReadable) {
        /** Database id when present (real YouTrack always sends it), else the readable id. */
        public String key() {
            return id != null ? id : idReadable;
        }
    }

    /** YouTrack tag (used as a label in triage signals). */
    @JsonIgnoreProperties(ignoreUnknown = true)
    public record Tag(String name) {
    }

    /**
     * A custom field. {@code value} is polymorphic in YouTrack: an object
     * ({@code {"name": "To Do"}}), a number, a string, an array (multi-value) or null.
     */
    @JsonIgnoreProperties(ignoreUnknown = true)
    public record CustomField(
            @JsonProperty("$type") String type,
            String name,
            JsonNode value) {
    }
}
