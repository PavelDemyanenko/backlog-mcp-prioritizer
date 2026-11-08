package backlogmcp.youtrack;

import java.math.BigDecimal;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Locale;
import java.util.Optional;
import java.util.Set;

import backlogmcp.adr.AdrRef;
import backlogmcp.adr.AdrReferenceResolver;
import backlogmcp.backlog.BacklogIssue;
import backlogmcp.backlog.StoryPointsSource;
import backlogmcp.backlog.TriageSignals;
import backlogmcp.triage.CvssExtractor;
import backlogmcp.evidence.EvidenceDetector;
import backlogmcp.youtrack.YouTrackIssue.CustomField;
import tools.jackson.databind.JsonNode;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

/**
 * Maps raw YouTrack issues (with their polymorphic {@code customFields}) to {@link BacklogIssue}.
 * This is the "anti-GIGO" layer from spec §7: the agent never sees raw customFields.
 */
@Component
public class YouTrackIssueNormalizer {

    static final String STATE_FIELD_TYPE = "StateIssueCustomField";
    /** Fallback names when the State field is not typed as such (e.g. enum-based workflows). */
    static final Set<String> STATUS_FIELD_NAMES = Set.of("state", "status", "stage");
    /** Compared after lower-casing and removing whitespace/underscores/dashes. */
    static final Set<String> STORY_POINT_FIELD_NAMES = Set.of("storypoints", "storypoint", "sp");

    static final Set<String> TYPE_FIELD_NAMES = Set.of("type", "issue type");
    static final Set<String> PRIORITY_FIELD_NAMES = Set.of("priority");
    static final Set<String> COMPONENT_FIELD_NAMES = Set.of("subsystem", "subsystems", "component", "components");
    static final String DATE_FIELD_TYPE = "DateIssueCustomField";
    static final String PERIOD_FIELD_TYPE = "PeriodIssueCustomField";
    static final Set<String> ESTIMATION_FIELD_NAMES = Set.of("estimation", "original estimation", "original estimate");
    static final Set<String> DUE_DATE_FIELD_NAMES = Set.of("due date", "duedate", "deadline");

    private final EvidenceDetector evidenceDetector;
    private final CvssExtractor cvssExtractor;
    private final AdrReferenceResolver adrResolver;
    private final long minutesPerStoryPoint;

    public YouTrackIssueNormalizer(EvidenceDetector evidenceDetector, CvssExtractor cvssExtractor,
                                   AdrReferenceResolver adrResolver) {
        this(evidenceDetector, cvssExtractor, adrResolver, 480);
    }

    @Autowired
    public YouTrackIssueNormalizer(EvidenceDetector evidenceDetector, CvssExtractor cvssExtractor,
                                   AdrReferenceResolver adrResolver, YouTrackProperties props) {
        this(evidenceDetector, cvssExtractor, adrResolver, props.minutesPerStoryPoint());
    }

    YouTrackIssueNormalizer(EvidenceDetector evidenceDetector, CvssExtractor cvssExtractor,
                            AdrReferenceResolver adrResolver, long minutesPerStoryPoint) {
        this.evidenceDetector = evidenceDetector;
        this.cvssExtractor = cvssExtractor;
        this.adrResolver = adrResolver;
        this.minutesPerStoryPoint = minutesPerStoryPoint;
    }

    public List<BacklogIssue> normalize(List<YouTrackIssue> issues) {
        return issues.stream().map(this::normalize).toList();
    }

    public BacklogIssue normalize(YouTrackIssue issue) {
        BigDecimal storyPoints = extractStoryPoints(issue.customFields()).orElse(null);
        StoryPointsSource spSource = storyPoints == null ? null : StoryPointsSource.CUSTOM_FIELD;
        if (storyPoints == null) {
            storyPoints = estimationFallback(issue.customFields()).orElse(null);
            spSource = storyPoints == null ? null : StoryPointsSource.TIME_ESTIMATE_FALLBACK;
        }
        List<AdrRef> adrRefs = adrResolver.resolve(issue.description());
        return new BacklogIssue(
                issue.idReadable(),
                issue.summary(),
                extractStatus(issue.customFields()).orElse(null),
                storyPoints,
                spSource,
                evidenceDetector.hasDocumentEvidence(issue.description()) || adrRefs.stream().anyMatch(AdrRef::isAccepted),
                adrRefs,
                extractTriage(issue));
    }

    TriageSignals extractTriage(YouTrackIssue issue) {
        List<CustomField> fields = issue.customFields();
        return new TriageSignals(
                fieldNamed(fields, TYPE_FIELD_NAMES).flatMap(f -> valueName(f.value())).orElse(null),
                fieldNamed(fields, PRIORITY_FIELD_NAMES).flatMap(f -> valueName(f.value())).orElse(null),
                issue.tags().stream().map(YouTrackIssue.Tag::name).filter(n -> n != null && !n.isBlank()).toList(),
                fields.stream()
                        .filter(f -> f.name() != null && COMPONENT_FIELD_NAMES.contains(f.name().toLowerCase(Locale.ROOT)))
                        .flatMap(f -> valueNames(f.value()).stream())
                        .distinct()
                        .toList(),
                fields.stream()
                        .filter(f -> f.name() != null && DUE_DATE_FIELD_NAMES.contains(f.name().toLowerCase(Locale.ROOT)))
                        .filter(f -> f.type() == null || DATE_FIELD_TYPE.equals(f.type()))
                        .findFirst()
                        .flatMap(f -> epochMillisToDate(f.value()))
                        .orElse(null),
                cvssExtractor.maxScore(issue.summary(), issue.description()).orElse(null));
    }

    private static Optional<CustomField> fieldNamed(List<CustomField> fields, Set<String> names) {
        return fields.stream()
                .filter(f -> f.name() != null && names.contains(f.name().toLowerCase(Locale.ROOT)))
                .findFirst();
    }

    /** All names of a single- or multi-value field. */
    private static List<String> valueNames(JsonNode value) {
        if (value != null && value.isArray()) {
            var names = new java.util.ArrayList<String>();
            for (JsonNode element : value) {
                valueName(element).ifPresent(names::add);
            }
            return names;
        }
        return valueName(value).map(List::of).orElse(List.of());
    }

    /** YouTrack stores dates as epoch milliseconds; the calendar date is taken in UTC. */
    private static Optional<String> epochMillisToDate(JsonNode value) {
        if (value == null || !value.isNumber()) {
            return Optional.empty();
        }
        return Optional.of(Instant.ofEpochMilli(value.longValue()).atZone(ZoneOffset.UTC).toLocalDate().toString());
    }

    Optional<String> extractStatus(List<CustomField> fields) {
        Optional<CustomField> field = fields.stream()
                .filter(f -> STATE_FIELD_TYPE.equals(f.type()))
                .findFirst()
                .or(() -> fields.stream()
                        .filter(f -> f.name() != null && STATUS_FIELD_NAMES.contains(f.name().toLowerCase(Locale.ROOT)))
                        .findFirst());
        return field.map(CustomField::value).flatMap(YouTrackIssueNormalizer::valueName);
    }

    /**
     * "Estimation" (period field, minutes) / minutesPerStoryPoint, rounded to 0.1. Used only when
     * no story points field is set; reported as {@code time_estimate_fallback}.
     */
    Optional<BigDecimal> estimationFallback(List<CustomField> fields) {
        if (minutesPerStoryPoint <= 0) {
            return Optional.empty();
        }
        return fields.stream()
                .filter(f -> PERIOD_FIELD_TYPE.equals(f.type())
                        || (f.name() != null && ESTIMATION_FIELD_NAMES.contains(f.name().toLowerCase(Locale.ROOT))))
                .map(CustomField::value)
                .filter(v -> v != null && v.isObject() && v.path("minutes").isNumber())
                .map(v -> v.path("minutes").decimalValue())
                .filter(m -> m.signum() > 0)
                .findFirst()
                .map(m -> m.divide(BigDecimal.valueOf(minutesPerStoryPoint), 1, java.math.RoundingMode.HALF_UP))
                .map(YouTrackIssueNormalizer::compact);
    }

    /** {@code 2.0 -> 2}, {@code 1.5 -> 1.5}. */
    private static BigDecimal compact(BigDecimal value) {
        BigDecimal stripped = value.stripTrailingZeros();
        return stripped.scale() < 0 ? stripped.setScale(0, java.math.RoundingMode.UNNECESSARY) : stripped;
    }

    Optional<BigDecimal> extractStoryPoints(List<CustomField> fields) {
        return fields.stream()
                .filter(f -> f.name() != null && STORY_POINT_FIELD_NAMES.contains(canonical(f.name())))
                .findFirst()
                .map(CustomField::value)
                .flatMap(YouTrackIssueNormalizer::numericValue);
    }

    /** Display name of a value: {@code {"name": "..."}}, a plain string, or the first array element. */
    private static Optional<String> valueName(JsonNode value) {
        if (value == null || value.isNull() || value.isMissingNode()) {
            return Optional.empty();
        }
        if (value.isArray()) {
            return value.isEmpty() ? Optional.empty() : valueName(value.get(0));
        }
        if (value.isString()) {
            return Optional.of(value.stringValue());
        }
        JsonNode name = value.get("name");
        return name != null && name.isString() ? Optional.of(name.stringValue()) : Optional.empty();
    }

    /**
     * Numeric value of a story-points field: a JSON number (SimpleIssueCustomField),
     * a numeric string, or an enum element whose name is numeric (e.g. {@code {"name": "5"}}).
     */
    private static Optional<BigDecimal> numericValue(JsonNode value) {
        if (value == null || value.isNull() || value.isMissingNode()) {
            return Optional.empty();
        }
        if (value.isNumber()) {
            return Optional.of(value.decimalValue());
        }
        return valueName(value).flatMap(YouTrackIssueNormalizer::parseDecimal);
    }

    private static Optional<BigDecimal> parseDecimal(String s) {
        try {
            return Optional.of(new BigDecimal(s.trim().replace(',', '.')));
        } catch (NumberFormatException e) {
            return Optional.empty();
        }
    }

    private static String canonical(String name) {
        return name.toLowerCase(Locale.ROOT).replaceAll("[\\s_-]", "");
    }
}
