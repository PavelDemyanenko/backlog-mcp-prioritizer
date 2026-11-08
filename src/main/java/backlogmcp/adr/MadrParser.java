package backlogmcp.adr;

import java.util.Locale;
import java.util.Optional;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Parses the metadata of an ADR file. Supported layouts:
 * <ul>
 *   <li>MADR 2.x list items: {@code * Status: accepted}, {@code - Date: 2026-09-14};</li>
 *   <li>MADR 3/4 YAML front matter: {@code status: accepted}, {@code date: 2026-09-14};</li>
 *   <li>Nygard: a {@code ## Status} section whose first line is the status.</li>
 * </ul>
 * "Superseded by ADR-0020" / "superseded by [ADR-0020](0020-x.md)" sets {@code superseded_by}.
 */
public final class MadrParser {

    static final Pattern FILE_NAME = Pattern.compile("^(\\d{1,4})-[\\w.-]+\\.md$", Pattern.CASE_INSENSITIVE);
    private static final Pattern TITLE = Pattern.compile("(?m)^#\\s+(.+?)\\s*$");
    private static final Pattern TITLE_PREFIX = Pattern.compile("^(?:ADR[-\\s]?)?\\d+[.:]?\\s*", Pattern.CASE_INSENSITIVE);
    private static final Pattern FRONT_MATTER = Pattern.compile("\\A---\\s*\\R(.*?)\\R---\\s*(?:\\R|\\z)", Pattern.DOTALL);
    private static final Pattern LIST_FIELD = Pattern.compile("(?im)^\\s*(?:[-*]\\s*)?(?:\\*\\*)?(status|date)(?:\\*\\*)?\\s*:(?:\\*\\*)?\\s*(.+?)\\s*$");
    private static final Pattern STATUS_SECTION = Pattern.compile("(?im)^#{2,3}\\s*status\\s*$\\R+\\s*(.+?)\\s*$");
    private static final Pattern SUPERSEDED_BY = Pattern.compile(
            "superseded\\s+by\\s*\\[?\\s*(?:ADR\\s*[-#]?\\s*)?(\\d{1,4})", Pattern.CASE_INSENSITIVE);

    private MadrParser() {
    }

    /** Empty when the file name is not {@code NNNN-slug.md} (e.g. README.md, template.md). */
    public static Optional<Adr> parse(String fileName, String content) {
        Matcher name = FILE_NAME.matcher(fileName);
        if (!name.matches()) {
            return Optional.empty();
        }
        String id = normalizeId(name.group(1));

        String status = null;
        String date = null;
        Matcher fm = FRONT_MATTER.matcher(content);
        String body = content;
        if (fm.find()) {
            for (String line : fm.group(1).split("\\R")) {
                String[] kv = line.split(":", 2);
                if (kv.length == 2) {
                    String key = kv[0].trim().toLowerCase(Locale.ROOT);
                    String value = unquote(kv[1].trim());
                    if (key.equals("status")) {
                        status = value;
                    } else if (key.equals("date")) {
                        date = value;
                    }
                }
            }
            body = content.substring(fm.end());
        }
        Matcher field = LIST_FIELD.matcher(body);
        while (field.find()) {
            if (status == null && field.group(1).equalsIgnoreCase("status")) {
                status = field.group(2);
            } else if (date == null && field.group(1).equalsIgnoreCase("date")) {
                date = field.group(2);
            }
        }
        if (status == null) {
            Matcher section = STATUS_SECTION.matcher(body);
            if (section.find()) {
                status = section.group(1);
            }
        }

        String supersededBy = null;
        if (status != null) {
            Matcher sup = SUPERSEDED_BY.matcher(status);
            if (sup.find()) {
                supersededBy = normalizeId(sup.group(1));
            }
        }

        Matcher title = TITLE.matcher(body);
        String cleanTitle = title.find() ? TITLE_PREFIX.matcher(title.group(1)).replaceFirst("").trim() : null;
        return Optional.of(new Adr(id, cleanTitle, normalizeStatus(status), date, supersededBy, fileName));
    }

    static String normalizeId(String digits) {
        return String.format(Locale.ROOT, "%04d", Integer.parseInt(digits));
    }

    static String normalizeStatus(String raw) {
        if (raw == null || raw.isBlank()) {
            return "unknown";
        }
        String s = raw.toLowerCase(Locale.ROOT);
        if (s.contains("supersed")) {
            return "superseded";
        }
        for (String known : new String[] {"accepted", "proposed", "rejected", "deprecated"}) {
            if (s.contains(known)) {
                return known;
            }
        }
        if (s.contains("approved")) {
            return "accepted";
        }
        return "unknown";
    }

    private static String unquote(String s) {
        return s.length() >= 2 && (s.startsWith("\"") && s.endsWith("\"") || s.startsWith("'") && s.endsWith("'"))
                ? s.substring(1, s.length() - 1) : s;
    }
}
