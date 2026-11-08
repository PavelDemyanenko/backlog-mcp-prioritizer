package backlogmcp.adr;

import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.function.Function;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

import org.springframework.stereotype.Component;

/**
 * Finds ADR references in issue text and resolves them against the ADR directory.
 * Recognized: {@code docs/adr/0015-use-spring-ai.md}, {@code adr/7-x.md}, {@code ADR-0015},
 * {@code ADR 15}, {@code ADR#15}.
 */
@Component
public class AdrReferenceResolver {

    private static final Pattern FILE_REF = Pattern.compile("(?i)(?:^|[\\s(\\[`'\"/])(?:docs/)?adr/(\\d{1,4})-[\\w.-]+\\.md\\b");
    private static final Pattern ID_REF = Pattern.compile("(?i)\\bADR\\s*[-#]?\\s*(\\d{1,4})\\b");

    private final AdrRepository repository;

    public AdrReferenceResolver(AdrRepository repository) {
        this.repository = repository;
    }

    /** Referenced ids in order of first appearance, normalized to 4 digits. */
    public static List<String> extractIds(String text) {
        if (text == null || text.isBlank()) {
            return List.of();
        }
        Set<String> ids = new LinkedHashSet<>();
        record Hit(int pos, String id) {
        }
        var hits = new java.util.ArrayList<Hit>();
        for (Pattern p : List.of(FILE_REF, ID_REF)) {
            Matcher m = p.matcher(text);
            while (m.find()) {
                hits.add(new Hit(m.start(1), MadrParser.normalizeId(m.group(1))));
            }
        }
        hits.sort(java.util.Comparator.comparingInt(Hit::pos));
        hits.forEach(h -> ids.add(h.id()));
        return List.copyOf(ids);
    }

    public List<AdrRef> resolve(String text) {
        List<String> ids = extractIds(text);
        if (ids.isEmpty()) {
            return List.of();
        }
        if (!repository.available()) {
            return ids.stream().map(id -> new AdrRef(id, null, AdrRef.UNVERIFIED, null)).toList();
        }
        Map<String, Adr> byId = repository.list().stream()
                .collect(Collectors.toMap(Adr::id, Function.identity(), (a, b) -> a));
        return ids.stream().map(id -> {
            Adr adr = byId.get(id);
            return adr == null
                    ? new AdrRef(id, null, AdrRef.MISSING, null)
                    : new AdrRef(id, adr.title(), adr.status(), adr.supersededBy());
        }).toList();
    }
}
