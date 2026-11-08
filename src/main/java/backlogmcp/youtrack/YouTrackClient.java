package backlogmcp.youtrack;

import java.util.List;

import backlogmcp.http.TrackerHttp;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import org.springframework.core.ParameterizedTypeReference;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestClientResponseException;

/**
 * Read-only YouTrack REST client. Only {@code GET} requests exist in this class by design
 * (AGENTS.md §5: agents have no write access to trackers).
 */
public class YouTrackClient {

    private static final Logger log = LoggerFactory.getLogger(YouTrackClient.class);

    /** Minimal field projection: YouTrack returns only {@code id} and {@code $type} without it. */
    static final String ISSUE_FIELDS =
            "idReadable,summary,description,tags(name),customFields($type,name,value($type,name,login,presentation,minutes))";

    private static final ParameterizedTypeReference<List<YouTrackIssue.IdOnly>> ID_LIST = new ParameterizedTypeReference<>() {
    };
    private static final ParameterizedTypeReference<List<YouTrackIssue>> ISSUE_LIST = new ParameterizedTypeReference<>() {
    };

    private final RestClient restClient;
    private final YouTrackProperties props;

    public YouTrackClient(RestClient restClient, YouTrackProperties props) {
        this.restClient = restClient;
        this.props = props;
    }

    /**
     * {@code GET /api/issues?query=<searchQuery>&fields=...&$top=<limit>}.
     *
     * @param searchQuery YouTrack search query, passed through verbatim (URL-encoded)
     * @param limit       already validated, 1..maxLimit
     */
    public List<YouTrackIssue> searchIssues(String searchQuery, int limit) {
        requireToken();
        log.debug("YouTrack search: query='{}', limit={}", searchQuery, limit);
        try {
            List<YouTrackIssue> issues = restClient.get()
                    .uri(uri -> uri.path("/api/issues")
                            .queryParam("query", "{query}")
                            .queryParam("fields", "{fields}")
                            .queryParam("$top", limit)
                            .build(searchQuery, ISSUE_FIELDS))
                    .retrieve()
                    .body(ISSUE_LIST);
            List<YouTrackIssue> result = issues == null ? List.of() : issues;
            // Defensive: enforce the limit even if the server (or a mock) ignores $top.
            if (result.size() > limit) {
                result = result.subList(0, limit);
            }
            log.info("YouTrack search returned {} issue(s)", result.size());
            return result;
        } catch (RestClientException e) {
            throw translate(e);
        }
    }

    /** Result of {@link #countIssues}: {@code capped} when the safety cap stopped the count. */
    public record Count(int count, boolean capped) {
    }

    static final int COUNT_PAGE = 500;
    static final int COUNT_CAP = 10_000;

    /**
     * Exact number of issues matching {@code searchQuery}: pages through {@code GET /api/issues}
     * requesting only {@code id} (read-only, no 100-item limit). Stops at {@link #COUNT_CAP}.
     * Duplicate-safe: a server that ignores {@code $skip} cannot inflate the count.
     */
    public Count countIssues(String searchQuery) {
        requireToken();
        java.util.Set<String> ids = new java.util.HashSet<>();
        try {
            for (int skip = 0; skip < COUNT_CAP; skip += COUNT_PAGE) {
                final int offset = skip;
                List<YouTrackIssue.IdOnly> page = restClient.get()
                        .uri(uri -> uri.path("/api/issues")
                                .queryParam("query", "{query}")
                                .queryParam("fields", "id,idReadable")
                                .queryParam("$top", COUNT_PAGE)
                                .queryParam("$skip", offset)
                                .build(searchQuery))
                        .retrieve()
                        .body(ID_LIST);
                if (page == null || page.isEmpty()) {
                    break;
                }
                int before = ids.size();
                page.forEach(i -> ids.add(i.key()));
                if (page.size() < COUNT_PAGE || ids.size() == before) {
                    break;
                }
            }
        } catch (RestClientException e) {
            throw translate(e);
        }
        boolean capped = ids.size() >= COUNT_CAP;
        log.info("YouTrack count: {} issue(s){}", ids.size(), capped ? " (capped)" : "");
        return new Count(Math.min(ids.size(), COUNT_CAP), capped);
    }

    private void requireToken() {
        if (!props.hasToken()) {
            throw new YouTrackClientException("YouTrack token is not configured (set YOUTRACK_TOKEN)", 0, null);
        }
    }

    private YouTrackClientException translate(RestClientException ex) {
        if (ex instanceof RestClientResponseException e) {
            int status = e.getStatusCode().value();
            String hint = switch (status) {
                case 400 -> "invalid search query";
                case 401 -> "token is missing, invalid or expired";
                case 403 -> "token lacks read permission for the requested projects";
                case 404 -> "endpoint not found, check youtrack.base-url";
                default -> status >= 500 ? "YouTrack server error" : "unexpected response";
            };
            log.warn("YouTrack responded {} ({})", status, hint);
            return new YouTrackClientException("YouTrack request failed: HTTP " + status + " - " + hint, status, e);
        }
        if (ex instanceof ResourceAccessException e) {
            log.warn("YouTrack unreachable at {}: {}", props.baseUrl(), e.getMessage());
            return new YouTrackClientException(
                    "YouTrack is unreachable at " + props.baseUrl() + ": " + TrackerHttp.rootMessage(e), 0, e);
        }
        log.warn("YouTrack response could not be processed: {}", ex.getMessage());
        return new YouTrackClientException("YouTrack response could not be parsed", 0, ex);
    }
}
