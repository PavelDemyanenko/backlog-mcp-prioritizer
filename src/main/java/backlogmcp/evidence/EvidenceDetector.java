package backlogmcp.evidence;

import java.util.EnumSet;
import java.util.Set;
import java.util.regex.Pattern;

import org.springframework.stereotype.Component;

/**
 * Scans free text (issue description) for product evidence markers (spec §3, §8.3).
 *
 * <p>A hit means Evidence Tier 1 for the prioritization agent; no hit means Tier 3-4 and
 * the agent discounts Confidence to 0.5. Detection is deterministic (regex only) on purpose:
 * the flag must be reproducible across E2E runs.
 */
@Component
public class EvidenceDetector {

    public enum Marker {
        /** Confluence page: {@code *.atlassian.net/wiki/...}, self-hosted {@code confluence.*}, {@code /display/...}. */
        CONFLUENCE(Pattern.compile(
                "https?://(?:[\\w-]+\\.)*atlassian\\.net/wiki\\S*"
                        + "|https?://(?:[\\w-]+\\.)*confluence(?:[\\w.-]*)(?::\\d+)?/\\S*"
                        + "|https?://\\S+/(?:wiki/spaces|display|pages/viewpage\\.action)\\S*",
                Pattern.CASE_INSENSITIVE)),
        /** Google Docs / Sheets / Slides / Drive files. */
        GOOGLE_DOCS(Pattern.compile(
                "https?://(?:docs|drive)\\.google\\.com/\\S+", Pattern.CASE_INSENSITIVE)),
        /** Approved architecture decision record (AGENTS.md: ADR link = Tier 1). */
        ADR(Pattern.compile(
                "(?:^|[\\s(\\[`'\"/])(?:docs/)?adr/\\d{3,4}-[\\w.-]+\\.md\\b|\\bADR\\s*[-#]?\\s*\\d{1,4}\\b",
                Pattern.CASE_INSENSITIVE)),
        /** Explicit keyword. */
        EVIDENCE_KEYWORD(Pattern.compile("\\bevidence\\b", Pattern.CASE_INSENSITIVE));

        private final Pattern pattern;

        Marker(Pattern pattern) {
            this.pattern = pattern;
        }

        boolean matches(String text) {
            return pattern.matcher(text).find();
        }
    }

    /** All markers present in {@code text}; empty for null/blank text. */
    public Set<Marker> detect(String text) {
        Set<Marker> found = EnumSet.noneOf(Marker.class);
        if (text == null || text.isBlank()) {
            return found;
        }
        for (Marker marker : Marker.values()) {
            if (marker.matches(text)) {
                found.add(marker);
            }
        }
        return found;
    }

    /**
     * Document evidence only: Confluence, Google Docs, the "evidence" keyword. ADR references are
     * excluded because they count only when the referenced ADR exists and is accepted, which is
     * checked against the ADR directory by the normalizers (see {@code AdrReferenceResolver}).
     */
    public boolean hasDocumentEvidence(String text) {
        Set<Marker> found = detect(text);
        found.remove(Marker.ADR);
        return !found.isEmpty();
    }

    /** Any marker, including an unverified ADR reference. */
    public boolean hasEvidence(String text) {
        return !detect(text).isEmpty();
    }
}
