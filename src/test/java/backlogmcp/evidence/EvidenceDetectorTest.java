package backlogmcp.evidence;

import static org.assertj.core.api.Assertions.assertThat;

import backlogmcp.evidence.EvidenceDetector.Marker;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.junit.jupiter.params.provider.NullAndEmptySource;
import org.junit.jupiter.params.provider.ValueSource;

class EvidenceDetectorTest {

    private final EvidenceDetector detector = new EvidenceDetector();

    @ParameterizedTest(name = "[{0}] {1}")
    @CsvSource(delimiter = '|', textBlock = """
            CONFLUENCE       | PRD: https://company.atlassian.net/wiki/spaces/PROD/pages/123
            CONFLUENCE       | see https://confluence.acme.local/display/PROD/Checkout
            CONFLUENCE       | https://wiki.acme.com/pages/viewpage.action?pageId=42
            GOOGLE_DOCS      | https://docs.google.com/document/d/abc123/edit
            GOOGLE_DOCS      | Research deck: https://docs.google.com/presentation/d/xyz
            GOOGLE_DOCS      | https://drive.google.com/file/d/1AbC/view
            ADR              | Approved in docs/adr/0015-use-spring-ai.md
            ADR              | Decision recorded in /docs/adr/0007-scheduler.md
            ADR              | Per ADR-0015 we migrate
            EVIDENCE_KEYWORD | Customer evidence collected in 12 tickets
            EVIDENCE_KEYWORD | EVIDENCE: churn interviews
            """)
    void detectsEachMarker(Marker expected, String text) {
        assertThat(detector.detect(text)).contains(expected);
        assertThat(detector.hasEvidence(text)).isTrue();
    }

    @ParameterizedTest
    @NullAndEmptySource
    @ValueSource(strings = {
            "   ",
            "Users asked for it, probably.",
            "See the wiki page about it",           // no link
            "https://github.com/acme/repo/issues/1",  // not a product artifact
            "evidenced-based is not a word here",     // no whole-word 'evidence'
            "Refactor the adr parser",                // 'adr' word but not an ADR reference
    })
    void noEvidence(String text) {
        assertThat(detector.detect(text)).isEmpty();
        assertThat(detector.hasEvidence(text)).isFalse();
    }

    @Test
    void reportsAllMarkersPresent() {
        String text = "Evidence: https://docs.google.com/document/d/1 and https://acme.atlassian.net/wiki/x";
        assertThat(detector.detect(text))
                .containsExactlyInAnyOrder(Marker.EVIDENCE_KEYWORD, Marker.GOOGLE_DOCS, Marker.CONFLUENCE);
    }
}
