package backlogmcp;

import static org.assertj.core.api.Assertions.assertThat;

import java.math.BigDecimal;
import java.net.URI;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;

import backlogmcp.backlog.BacklogIssue;
import backlogmcp.evidence.EvidenceDetector;
import backlogmcp.http.LocalBypassProxySelector;
import backlogmcp.support.TestAdr;
import backlogmcp.triage.CvssExtractor;
import backlogmcp.youtrack.YouTrackClient;
import backlogmcp.youtrack.YouTrackClientConfiguration;
import backlogmcp.youtrack.YouTrackIssueNormalizer;
import backlogmcp.youtrack.YouTrackProperties;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

import org.springframework.web.client.RestClient;

/**
 * The Golden Dataset ({@code evals/golden/dataset.json}) declares, per task, what the server must
 * extract (evidence flag, CVSS, triage signals, ADR references). Implementations point the real
 * client + normalizer at a backend: WireMock fixtures ({@link GoldenDatasetIT}) or a real YouTrack
 * seeded with the same data ({@link YouTrackSandboxIT}). The frozen fixtures are trustworthy only
 * if both pass.
 */
abstract class GoldenBacklogContract {

    /** WireMock ignores the sort clause; a real YouTrack needs it for a stable order. */
    static final String BACKLOG_QUERY = "project: GOLD State: Submitted, Open, {To Do} sort by: {issue id} asc";

    static final JsonNode DATASET = JsonMapper.builder().build()
            .readTree(readString(Path.of("evals/golden/dataset.json")));

    private final YouTrackClient client;
    private final YouTrackIssueNormalizer normalizer = new YouTrackIssueNormalizer(
            new EvidenceDetector(), new CvssExtractor(), TestAdr.resolver(TestAdr.GOLDEN_DIR));

    GoldenBacklogContract(String baseUrl, String token) {
        var props = new YouTrackProperties(URI.create(baseUrl), token, Duration.ofSeconds(5), Duration.ofSeconds(30), 100, 480);
        client = new YouTrackClient(YouTrackClientConfiguration.createRestClient(
                RestClient.builder(), props, LocalBypassProxySelector.fromEnvironment(List.of())), props);
    }

    @Test
    void backlogQueryReturnsEveryTaskWithDeclaredSignals() {
        List<BacklogIssue> issues = normalizer.normalize(client.searchIssues(BACKLOG_QUERY, 100));

        List<String> expectedIds = new ArrayList<>();
        DATASET.get("tasks").forEach(t -> expectedIds.add(t.get("id").stringValue()));
        assertThat(issues).extracting(BacklogIssue::id).containsExactlyElementsOf(expectedIds);

        for (int i = 0; i < issues.size(); i++) {
            BacklogIssue issue = issues.get(i);
            JsonNode task = DATASET.get("tasks").get(i);
            JsonNode expected = task.get("expected");
            String ctx = issue.id() + " (" + task.get("scenario").stringValue() + ")";

            assertThat(issue.summary()).as(ctx).isEqualTo(task.get("summary").stringValue());
            assertThat(issue.status()).as(ctx).isEqualTo(task.get("state").stringValue());
            assertThat(issue.evidenceFoundInText()).as(ctx + ": evidence flag")
                    .isEqualTo(expected.get("evidence_found_in_text").booleanValue());
            if (task.get("story_points").isNull()) {
                assertThat(issue.storyPoints()).as(ctx).isNull();
            } else {
                assertThat(issue.storyPoints()).as(ctx).isEqualByComparingTo(task.get("story_points").decimalValue());
            }

            List<String> expectedRefs = new ArrayList<>();
            expected.get("adr_refs").forEach(r -> expectedRefs.add(r.get("id").stringValue() + ":" + r.get("status").stringValue()));
            assertThat(issue.adrRefs()).as(ctx + ": adr_refs")
                    .extracting(r -> r.id() + ":" + r.status()).containsExactlyElementsOf(expectedRefs);

            var triage = issue.triage();
            assertThat(triage.issueType()).as(ctx).isEqualTo(task.get("type").stringValue());
            assertThat(triage.priority()).as(ctx).isEqualTo(task.get("priority").stringValue());
            assertThat(triage.labels()).as(ctx).containsExactlyInAnyOrderElementsOf(strings(task.get("tags")));
            assertThat(triage.components()).as(ctx).containsExactlyInAnyOrderElementsOf(strings(task.get("subsystem")));
            assertThat(triage.dueDate()).as(ctx).isEqualTo(task.get("due_date").isNull() ? null : task.get("due_date").stringValue());
            JsonNode cvss = expected.get("cvss_score");
            if (cvss.isNull()) {
                assertThat(triage.cvssScore()).as(ctx + ": cvss").isNull();
            } else {
                assertThat(triage.cvssScore()).as(ctx + ": cvss").isEqualByComparingTo(new BigDecimal(cvss.asString()));
            }
        }
    }

    @Test
    void countToolCountsWorkInProgressExactly() {
        var count = client.countIssues("project: GOLD State: {In Progress}");
        assertThat(count.count()).isEqualTo(DATASET.get("wip").size());
        assertThat(count.capped()).isFalse();
    }

    @Test
    void inProgressQueryFeedsUtilization() {
        var wip = client.searchIssues("project: GOLD State: {In Progress}", 100);
        assertThat(wip).hasSize(DATASET.get("wip").size());
        assertThat(normalizer.normalize(wip)).allSatisfy(i -> assertThat(i.status()).isEqualTo("In Progress"));
    }

    private static List<String> strings(JsonNode array) {
        List<String> out = new ArrayList<>();
        array.forEach(n -> out.add(n.stringValue()));
        return out;
    }

    private static String readString(Path path) {
        try {
            return Files.readString(path);
        } catch (java.io.IOException e) {
            throw new IllegalStateException(e);
        }
    }
}
