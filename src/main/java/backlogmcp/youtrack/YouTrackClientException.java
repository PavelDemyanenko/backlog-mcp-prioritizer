package backlogmcp.youtrack;

/** Failure talking to YouTrack. Message is safe to show to the agent (no secrets). */
public class YouTrackClientException extends RuntimeException {

    private final int status; // HTTP status, or 0 when no response was received

    public YouTrackClientException(String message, int status, Throwable cause) {
        super(message, cause);
        this.status = status;
    }

    public int status() {
        return status;
    }
}
