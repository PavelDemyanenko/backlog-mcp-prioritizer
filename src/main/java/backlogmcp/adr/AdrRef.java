package backlogmcp.adr;

import com.fasterxml.jackson.annotation.JsonIgnore;
import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.annotation.JsonPropertyOrder;

/**
 * An ADR referenced from an issue description, resolved against the ADR directory.
 *
 * @param status ADR status (accepted, proposed, superseded, ...), {@code missing} when no such file
 *               exists, {@code unverified} when the ADR directory is not available
 */
@JsonInclude(JsonInclude.Include.ALWAYS)
@JsonPropertyOrder({"id", "title", "status", "superseded_by"})
public record AdrRef(
        @JsonProperty("id") String id,
        @JsonProperty("title") String title,
        @JsonProperty("status") String status,
        @JsonProperty("superseded_by") String supersededBy) {

    public static final String MISSING = "missing";
    public static final String UNVERIFIED = "unverified";

    @JsonIgnore // helper, not part of the tool contract
    public boolean isAccepted() {
        return Adr.ACCEPTED.equals(status);
    }
}
