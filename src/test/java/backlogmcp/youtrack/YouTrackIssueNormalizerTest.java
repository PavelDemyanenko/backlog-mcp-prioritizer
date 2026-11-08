package backlogmcp.youtrack;

import static org.assertj.core.api.Assertions.assertThat;

import java.math.BigDecimal;
import java.util.List;

import backlogmcp.backlog.BacklogIssue;
import backlogmcp.backlog.StoryPointsSource;
import backlogmcp.evidence.EvidenceDetector;
import backlogmcp.backlog.TriageSignals;
import backlogmcp.triage.CvssExtractor;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.json.JsonMapper;

class YouTrackIssueNormalizerTest {

    private final JsonMapper json = JsonMapper.builder().build();
    private final YouTrackIssueNormalizer normalizer = new YouTrackIssueNormalizer(new EvidenceDetector(), new CvssExtractor(), backlogmcp.support.TestAdr.e2e());

    private YouTrackIssue issue(String customFieldsJson, String description) {
        String body = """
                {"idReadable":"DEV-9","summary":"S","description":%s,"customFields":%s,"unknownField":1}
                """.formatted(description == null ? "null" : json.writeValueAsString(description), customFieldsJson);
        return json.readValue(body, YouTrackIssue.class);
    }

    @Test
    void mapsTypedStateAndNumericStoryPoints() {
        BacklogIssue result = normalizer.normalize(issue("""
                [{"$type":"StateIssueCustomField","name":"State","value":{"name":"In Progress"}},
                 {"$type":"SimpleIssueCustomField","name":"Story points","value":8}]""",
                "PRD https://docs.google.com/document/d/1"));

        assertThat(result).isEqualTo(new BacklogIssue("DEV-9", "S", "In Progress", new BigDecimal("8"), StoryPointsSource.CUSTOM_FIELD, true));
    }

    @Test
    void stateFieldFoundByTypeEvenWhenRenamed() {
        var result = normalizer.normalize(issue("""
                [{"$type":"StateIssueCustomField","name":"Workflow stage","value":{"name":"Done"}}]""", null));
        assertThat(result.status()).isEqualTo("Done");
    }

    @Test
    void statusFallsBackToFieldNameForEnumWorkflows() {
        var result = normalizer.normalize(issue("""
                [{"$type":"SingleEnumIssueCustomField","name":"Status","value":{"name":"Backlog"}}]""", null));
        assertThat(result.status()).isEqualTo("Backlog");
    }

    @Test
    void storyPointsFromEnumNameOrStringAndNameVariants() {
        assertThat(normalizer.normalize(issue("""
                [{"$type":"SingleEnumIssueCustomField","name":"Story Points","value":{"name":"13"}}]""", null))
                .storyPoints()).isEqualByComparingTo("13");
        assertThat(normalizer.normalize(issue("""
                [{"$type":"SimpleIssueCustomField","name":"story_points","value":"2,5"}]""", null))
                .storyPoints()).isEqualByComparingTo("2.5");
        assertThat(normalizer.normalize(issue("""
                [{"$type":"SimpleIssueCustomField","name":"StoryPoints","value":3.5}]""", null))
                .storyPoints()).isEqualByComparingTo("3.5");
    }

    @Test
    void missingOrUnparseableValuesBecomeNull() {
        var result = normalizer.normalize(issue("""
                [{"$type":"StateIssueCustomField","name":"State","value":null},
                 {"$type":"SimpleIssueCustomField","name":"Story points","value":null},
                 {"$type":"SingleEnumIssueCustomField","name":"Priority","value":{"name":"Major"}}]""", null));
        assertThat(result.status()).isNull();
        assertThat(result.storyPoints()).isNull();
        assertThat(result.evidenceFoundInText()).isFalse();

        var noFields = normalizer.normalize(issue("null", "text"));
        assertThat(noFields.status()).isNull();
        assertThat(noFields.storyPoints()).isNull();

        var garbage = normalizer.normalize(issue("""
                [{"$type":"SingleEnumIssueCustomField","name":"Story points","value":{"name":"XL"}}]""", null));
        assertThat(garbage.storyPoints()).isNull();
    }

    @Test
    void serializesToSpecContract() {
        var issues = List.of(
                new BacklogIssue("DEV-1", "Sum", "To Do", new BigDecimal("5"), StoryPointsSource.CUSTOM_FIELD, true),
                new BacklogIssue("DEV-4", "No SP", "To Do", null, null, false));
        assertThat(json.writeValueAsString(issues)).isEqualTo("""
                [{"id":"DEV-1","summary":"Sum","status":"To Do","story_points":5,"story_points_source":"custom_field","evidence_found_in_text":true,"adr_refs":[],\
                "triage":{"issue_type":null,"priority":null,"labels":[],"components":[],"due_date":null,"cvss_score":null}},\
                {"id":"DEV-4","summary":"No SP","status":"To Do","story_points":null,"story_points_source":null,"evidence_found_in_text":false,"adr_refs":[],\
                "triage":{"issue_type":null,"priority":null,"labels":[],"components":[],"due_date":null,"cvss_score":null}}]""");
    }

    @Test
    void extractsTriageSignals() {
        String body = """
                {"idReadable":"DEV-9","summary":"CVE-2026-1: RCE, CVSS 9.8","description":"cvss score 7.0 before PoC",
                 "tags":[{"name":"security"},{"name":"legal"}],
                 "customFields":[
                   {"$type":"SingleEnumIssueCustomField","name":"Type","value":{"name":"Bug"}},
                   {"$type":"SingleEnumIssueCustomField","name":"Priority","value":{"name":"Show-stopper"}},
                   {"$type":"MultiOwnedIssueCustomField","name":"Subsystem","value":[{"name":"API"},{"name":"Auth"}]},
                   {"$type":"DateIssueCustomField","name":"Due Date","value":1795176000000}]}""";
        TriageSignals t = normalizer.normalize(json.readValue(body, YouTrackIssue.class)).triage();

        assertThat(t.issueType()).isEqualTo("Bug");
        assertThat(t.priority()).isEqualTo("Show-stopper");
        assertThat(t.labels()).containsExactly("security", "legal");
        assertThat(t.components()).containsExactly("API", "Auth");
        assertThat(t.dueDate()).isEqualTo("2026-11-20");
        assertThat(t.cvssScore()).isEqualByComparingTo("9.8");
    }

    @Test
    void issueWithoutTriageDataHasEmptySignals() {
        var t = normalizer.normalize(issue("[]", "plain text")).triage();
        assertThat(t).isEqualTo(TriageSignals.NONE);
    }

    @Test
    void estimationFallsBackWhenStoryPointsAreEmpty() {
        // real YouTrack shape (sandbox probe 2026-11-09): "1d 4h" = 720 minutes, 1d = 480
        var fromEstimation = normalizer.normalize(issue("""
                [{"$type":"SimpleIssueCustomField","name":"Story points","value":null},
                 {"$type":"PeriodIssueCustomField","name":"Estimation",
                  "value":{"$type":"PeriodValue","minutes":720,"presentation":"1d 4h"}}]""", null));
        assertThat(fromEstimation.storyPoints()).isEqualTo(new BigDecimal("1.5"));
        assertThat(fromEstimation.storyPointsSource()).isEqualTo(StoryPointsSource.TIME_ESTIMATE_FALLBACK);

        var spWins = normalizer.normalize(issue("""
                [{"$type":"SimpleIssueCustomField","name":"Story points","value":3},
                 {"$type":"PeriodIssueCustomField","name":"Estimation","value":{"minutes":960}}]""", null));
        assertThat(spWins.storyPoints()).isEqualByComparingTo("3");
        assertThat(spWins.storyPointsSource()).isEqualTo(StoryPointsSource.CUSTOM_FIELD);

        var twoDays = normalizer.normalize(issue("""
                [{"$type":"PeriodIssueCustomField","name":"Estimation","value":{"minutes":960}}]""", null));
        assertThat(twoDays.storyPoints()).isEqualTo(new BigDecimal("2"));
    }

    @Test
    void estimationFallbackCanBeDisabledAndIgnoresEmptyValues() {
        var off = new YouTrackIssueNormalizer(new EvidenceDetector(), new CvssExtractor(),
                backlogmcp.support.TestAdr.e2e(), 0);
        String fields = """
                [{"$type":"PeriodIssueCustomField","name":"Estimation","value":{"minutes":960}}]""";
        assertThat(off.normalize(issue(fields, null)).storyPoints()).isNull();
        var empty = normalizer.normalize(issue("""
                [{"$type":"PeriodIssueCustomField","name":"Estimation","value":null}]""", null));
        assertThat(empty.storyPoints()).isNull();
        assertThat(empty.storyPointsSource()).isNull();
    }
}
