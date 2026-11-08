package backlogmcp.adr;

import com.fasterxml.jackson.annotation.JsonIgnore;
import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.annotation.JsonPropertyOrder;

/**
 * An architecture decision record found in the ADR directory.
 *
 * @param id           4-digit number from the file name ({@code 0015})
 * @param status       normalized: proposed | accepted | rejected | deprecated | superseded | unknown
 * @param supersededBy id of the replacing ADR when {@code status = superseded}, else null
 * @param file         file name inside the ADR directory
 */
@JsonInclude(JsonInclude.Include.ALWAYS)
@JsonPropertyOrder({"id", "title", "status", "date", "superseded_by", "file"})
public record Adr(
        @JsonProperty("id") String id,
        @JsonProperty("title") String title,
        @JsonProperty("status") String status,
        @JsonProperty("date") String date,
        @JsonProperty("superseded_by") String supersededBy,
        @JsonProperty("file") String file) {

    public static final String ACCEPTED = "accepted";

    @JsonIgnore // helper, not part of the tool contract
    public boolean isAccepted() {
        return ACCEPTED.equals(status);
    }
}
