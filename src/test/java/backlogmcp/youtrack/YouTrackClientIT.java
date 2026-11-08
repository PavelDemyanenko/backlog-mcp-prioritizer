package backlogmcp.youtrack;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.math.BigDecimal;
import java.net.URI;
import java.time.Duration;
import java.util.List;

import backlogmcp.backlog.BacklogIssue;
import backlogmcp.backlog.StoryPointsSource;
import backlogmcp.evidence.EvidenceDetector;
import backlogmcp.backlog.TriageSignals;
import backlogmcp.triage.CvssExtractor;
import backlogmcp.http.LocalBypassProxySelector;
import backlogmcp.support.WireMockContainer;
import org.junit.jupiter.api.Test;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

import org.springframework.web.client.RestClient;

/**
 * {@link YouTrackClient} + {@link YouTrackIssueNormalizer} against WireMock running in Docker.
 * Runs with the real process environment, so a configured HTTP_PROXY must be bypassed for
 * the local container; otherwise these requests would fail (502 from the proxy).
 */
@Testcontainers
class YouTrackClientIT {

    @Container
    static final WireMockContainer WIREMOCK = new WireMockContainer();

    private final YouTrackIssueNormalizer normalizer = new YouTrackIssueNormalizer(new EvidenceDetector(), new CvssExtractor(), backlogmcp.support.TestAdr.e2e());

    private YouTrackClient client(String token) {
        return client(WIREMOCK.baseUrl(), token);
    }

    private static YouTrackClient client(String baseUrl, String token) {
        var props = new YouTrackProperties(URI.create(baseUrl), token, Duration.ofSeconds(2), Duration.ofSeconds(5), 100, 480);
        var restClient = YouTrackClientConfiguration.createRestClient(
                RestClient.builder(), props, LocalBypassProxySelector.fromEnvironment(List.of()));
        return new YouTrackClient(restClient, props);
    }

    @Test
    void fetchesAndNormalizesBacklogWithEvidenceTiers() {
        List<BacklogIssue> issues = normalizer.normalize(client("e2e-token").searchIssues("project: DEV #Unresolved", 20));

        assertThat(issues).extracting(BacklogIssue::core).containsExactly(
                new BacklogIssue("DEV-1", "Migrate prioritization service to Spring AI", "To Do", new BigDecimal("5"), StoryPointsSource.CUSTOM_FIELD, true),
                new BacklogIssue("DEV-2", "Add dark mode to settings page", "Open", new BigDecimal("3"), StoryPointsSource.CUSTOM_FIELD, false),
                new BacklogIssue("DEV-3", "GDPR: purge PII from audit logs", "In Progress", new BigDecimal("8"), StoryPointsSource.CUSTOM_FIELD, true),
                new BacklogIssue("DEV-4", "Refactor legacy billing module", "To Do", null, null, false),
                new BacklogIssue("DEV-5", "Tech debt: replace cron scripts with a scheduler", "Open", new BigDecimal("13"), StoryPointsSource.CUSTOM_FIELD, true),
                new BacklogIssue("DEV-6", "Onboarding checklist for new tenants", "To Do", new BigDecimal("2.5"), StoryPointsSource.CUSTOM_FIELD, true),
                new BacklogIssue("DEV-7", "CVE-2026-31337: RCE in template engine", "Open", new BigDecimal("3"), StoryPointsSource.CUSTOM_FIELD, false));

        assertThat(issues.get(0).triage()).isEqualTo(new TriageSignals(
                "Task", "Major", List.of("architecture"), List.of("Prioritization", "MCP"), null, null));
        assertThat(issues.get(2).triage()).isEqualTo(new TriageSignals(
                "Task", "Critical", List.of("compliance", "GDPR"), List.of("Audit"), "2026-11-20", null));
        assertThat(issues.get(1).triage()).isEqualTo(TriageSignals.NONE);
        // vector "CVSS:3.1/..." is not read as score 3.1; the base score 9.8 is
        assertThat(issues.get(6).triage().cvssScore()).isEqualByComparingTo("9.8");
        assertThat(issues.get(6).triage().priority()).isEqualTo("Show-stopper");
    }

    @Test
    void enforcesLimitEvenIfServerIgnoresTop() {
        assertThat(client("e2e-token").searchIssues("project: DEV", 2))
                .extracting(YouTrackIssue::idReadable)
                .containsExactly("DEV-1", "DEV-2");
    }

    @Test
    void sendsReadOnlyGetWithBearerTokenAndEncodedQuery() throws Exception {
        String query = "project: DEV State: {To Do} #Unresolved sort by: created desc";
        client("e2e-token").searchIssues(query, 7);

        var http = java.net.http.HttpClient.newBuilder().proxy(LocalBypassProxySelector.fromEnvironment(List.of())).build();
        var body = http.send(java.net.http.HttpRequest.newBuilder(URI.create(WIREMOCK.baseUrl() + "/__admin/requests")).build(),
                java.net.http.HttpResponse.BodyHandlers.ofString()).body();
        var journal = tools.jackson.databind.json.JsonMapper.builder().build().readTree(body).get("requests");

        var last = journal.get(0).get("request"); // newest first
        assertThat(last.get("method").stringValue()).isEqualTo("GET");
        assertThat(WireMockContainer.header(last, "Authorization")).isEqualTo("Bearer e2e-token");
        var params = last.get("queryParams");
        assertThat(params.get("query").get("values").get(0).stringValue()).isEqualTo(query);
        assertThat(params.get("$top").get("values").get(0).stringValue()).isEqualTo("7");
        assertThat(params.get("fields").get("values").get(0).stringValue()).isEqualTo(YouTrackClient.ISSUE_FIELDS);
        // read-only contract: nothing but GETs ever reached the tracker
        for (var entry : journal) {
            assertThat(entry.get("request").get("method").stringValue()).isEqualTo("GET");
        }
    }

    @Test
    void invalidTokenIsReportedAs401() {
        assertThatThrownBy(() -> client("invalid-token").searchIssues("project: DEV", 5))
                .isInstanceOf(YouTrackClientException.class)
                .hasMessageContaining("HTTP 401")
                .hasMessageNotContaining("invalid-token")
                .extracting(e -> ((YouTrackClientException) e).status()).isEqualTo(401);
    }

    @Test
    void missingTokenFailsFastWithoutCallingYouTrack() {
        assertThatThrownBy(() -> client("  ").searchIssues("project: DEV", 5))
                .isInstanceOf(YouTrackClientException.class)
                .hasMessageContaining("YOUTRACK_TOKEN");
    }

    @Test
    void unreachableHostIsReportedClearly() {
        // port 1 on localhost: connection refused, must not be routed through a proxy
        assertThatThrownBy(() -> client("http://localhost:1", "t").searchIssues("x", 1))
                .isInstanceOf(YouTrackClientException.class)
                .hasMessageContaining("unreachable")
                .extracting(e -> ((YouTrackClientException) e).status()).isEqualTo(0);
    }
}
