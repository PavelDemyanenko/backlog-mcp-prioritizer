package backlogmcp.triage;

import java.math.BigDecimal;
import java.util.Optional;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import org.springframework.stereotype.Component;

/**
 * Extracts the highest CVSS base score mentioned in free text.
 *
 * <p>Recognized: {@code CVSS 9.8}, {@code CVSS 3.x base score: 9.8} (NVD wording), {@code CVSS: 9.8}, {@code CVSS v3.1 score 9.8},
 * {@code CVSSv3 base score: 7.5}, {@code CVSS 4.0: 9.3}. Vector strings such as
 * {@code CVSS:3.1/AV:N/AC:L/...} are removed first so that the version ({@code 3.1}) is never
 * mistaken for a score. Values outside 0.0–10.0 are ignored.
 */
@Component
public class CvssExtractor {

    /** {@code CVSS:3.1/AV:N/...} or {@code CVSS:4.0/AV:N/...}: version + metric vector. */
    private static final Pattern VECTOR = Pattern.compile("CVSS:\\d\\.\\d(?:/[A-Za-z]+:[A-Za-z])+", Pattern.CASE_INSENSITIVE);

    private static final Pattern SCORE = Pattern.compile(
            "\\bCVSS"
                    + "(?:\\s*v?\\s*[234](?:\\.[\\dx])?(?![\\d.]))?"   // optional version: v3, v3.1, 3.x, 4.0 (not the score)
                    + "(?:\\s*(?:base|overall|temporal|environmental))?"
                    + "(?:\\s*score)?"
                    + "\\s*(?:[:=]|is|of)?\\s*"
                    + "(10(?:\\.0)?|\\d(?:\\.\\d)?)(?![\\d.]*\\d)(?!\\.x)",
            Pattern.CASE_INSENSITIVE);

    public Optional<BigDecimal> maxScore(String... texts) {
        BigDecimal max = null;
        for (String text : texts) {
            if (text == null || text.isBlank()) {
                continue;
            }
            Matcher m = SCORE.matcher(VECTOR.matcher(text).replaceAll("CVSS")); // keep the keyword, drop the version
            while (m.find()) {
                BigDecimal score = new BigDecimal(m.group(1));
                if (score.compareTo(BigDecimal.TEN) <= 0 && (max == null || score.compareTo(max) > 0)) {
                    max = score;
                }
            }
        }
        return Optional.ofNullable(max);
    }
}
