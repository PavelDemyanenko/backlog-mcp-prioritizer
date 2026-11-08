package backlogmcp.triage;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.junit.jupiter.params.provider.ValueSource;
import org.junit.jupiter.api.Test;

class CvssExtractorTest {

    private final CvssExtractor extractor = new CvssExtractor();

    @ParameterizedTest(name = "{0} -> {1}")
    @CsvSource(delimiter = '|', textBlock = """
            CVSS 9.8                                                     | 9.8
            cvss: 7.5 (high)                                             | 7.5
            CVSS v3.1 base score 9.1                                     | 9.1
            CVSSv3 Base Score: 6.4                                       | 6.4
            CVSS 4.0: 9.3                                                | 9.3
            CVSS score is 10.0                                           | 10.0
            CVSS 10                                                      | 10
            CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H base score 9.8  | 9.8
            Vector CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H, CVSS 9.8 | 9.8
            CVSS 3.x base score: 9.8                                     | 9.8
            CVSS 3.x Base Score 7.5 / CVSS 2.0 base score 5.0            | 7.5
            CVSS 5.3 initially, re-scored to CVSS 9.0 after PoC          | 9.0
            """)
    void extractsHighestScore(String text, String expected) {
        assertThat(extractor.maxScore(text)).hasValueSatisfying(v -> assertThat(v).isEqualByComparingTo(expected));
    }

    @ParameterizedTest
    @ValueSource(strings = {
            "",
            "Bump version to 9.8",
            "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",   // vector only: 3.1 is a version, not a score
            "CVSS 12.5",                                      // out of range
            "CVSS 3.x",                                       // version only
            "see CVSS calculator",
    })
    void noScore(String text) {
        assertThat(extractor.maxScore(text)).isEmpty();
    }

    @Test
    void scansAllTextsAndIgnoresNulls() {
        assertThat(extractor.maxScore(null, "CVSS 4.3", "summary: CVSS 9.1"))
                .hasValueSatisfying(v -> assertThat(v).isEqualByComparingTo("9.1"));
    }
}
