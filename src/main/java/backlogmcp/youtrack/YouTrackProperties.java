package backlogmcp.youtrack;

import java.net.URI;
import java.time.Duration;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.bind.DefaultValue;

/**
 * YouTrack connection (read-only).
 *
 * @param baseUrl        instance root, e.g. {@code https://acme.youtrack.cloud} or
 *                       {@code https://tracker.acme.com/youtrack}; {@code /api/...} is appended
 * @param token          permanent token, sent as {@code Authorization: Bearer <token>}
 * @param maxLimit       hard cap for {@code limit} requested by the agent
 * @param minutesPerStoryPoint fallback when "Story points" is empty: the period field "Estimation"
 *                       (minutes) / this. 480 = one 8h ideal day, YouTrack's default "1d"; 0 disables
 */
@ConfigurationProperties("youtrack")
public record YouTrackProperties(
        @DefaultValue("http://localhost:8089") URI baseUrl,
        String token,
        @DefaultValue("5s") Duration connectTimeout,
        @DefaultValue("30s") Duration readTimeout,
        @DefaultValue("100") int maxLimit,
        @DefaultValue("480") long minutesPerStoryPoint) {
    // Single (canonical) constructor on purpose: a second one breaks Spring Boot's constructor binding.

    public boolean hasToken() {
        return token != null && !token.isBlank();
    }

    @Override
    public String toString() { // never leak the token into logs
        return "YouTrackProperties[baseUrl=" + baseUrl + ", token=" + (hasToken() ? "***" : "<unset>")
                + ", connectTimeout=" + connectTimeout + ", readTimeout=" + readTimeout
                + ", maxLimit=" + maxLimit + ", minutesPerStoryPoint=" + minutesPerStoryPoint + "]";
    }
}
