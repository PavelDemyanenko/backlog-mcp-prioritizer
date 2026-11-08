package backlogmcp.adr;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

class AdrTest {

    static final Path FIXTURES = Path.of("e2e/adr");

    private final AdrRepository repository = new AdrRepository(FIXTURES, 20_000);
    private final AdrReferenceResolver resolver = new AdrReferenceResolver(repository);

    @Test
    void listsAndParsesAllThreeLayouts() {
        assertThat(repository.list()).containsExactly(
                new Adr("0003", "Run background jobs with cron", "superseded", null, "0007", "0003-cron-jobs.md"),
                new Adr("0007", "Use a managed scheduler for background jobs", "accepted", "2026-06-02", null, "0007-scheduler.md"),
                new Adr("0015", "Use Spring AI for the generation service", "accepted", "2026-09-14", null, "0015-use-spring-ai.md"),
                new Adr("0021", "Event sourcing for orders", "accepted", "2026-10-01", null, "0021-event-sourcing.md"),
                new Adr("0022", "GraphQL gateway for the portal", "proposed", "2026-10-20", null, "0022-graphql-gateway.md"));
    }

    @ParameterizedTest
    @CsvSource(delimiter = '|', textBlock = """
            Accepted                               | accepted
            Approved by architecture board         | accepted
            superseded by ADR-0020                 | superseded
            Deprecated                             | deprecated
            Rejected                               | rejected
            draft                                  | unknown
            """)
    void normalizesStatus(String raw, String expected) {
        assertThat(MadrParser.normalizeStatus(raw)).isEqualTo(expected);
    }

    @Test
    void ignoresFilesThatAreNotAdrs() {
        assertThat(MadrParser.parse("README.md", "# x")).isEmpty();
        assertThat(MadrParser.parse("template.md", "# x")).isEmpty();
    }

    @Test
    void readsByIdOnlyAndCapsLength(@TempDir Path dir) throws Exception {
        Files.writeString(dir.resolve("0001-big.md"), "# Big\n\n- Status: accepted\n\n" + "x".repeat(500));
        var small = new AdrRepository(dir, 100);
        assertThat(small.read("1")).hasValueSatisfying(t -> assertThat(t).hasSize(100 + "\n\n[truncated at 100 characters]".length()));
        assertThat(small.read("0002")).isEmpty();
        assertThat(repository.read("15")).hasValueSatisfying(t -> assertThat(t).contains("Spring AI 2.x"));
    }

    @Test
    void extractsReferencesInOrderWithoutDuplicates() {
        assertThat(AdrReferenceResolver.extractIds(
                "Per ADR-15 and docs/adr/0007-scheduler.md (see also adr/0015-use-spring-ai.md, ADR #3)"))
                .containsExactly("0015", "0007", "0003");
        assertThat(AdrReferenceResolver.extractIds("Refactor the adr parser, v2.1")).isEmpty();
    }

    @Test
    void resolvesStatusMissingAndSupersession() {
        assertThat(resolver.resolve("docs/adr/0015-use-spring-ai.md, ADR-0003, ADR-0022, ADR-0031")).containsExactly(
                new AdrRef("0015", "Use Spring AI for the generation service", "accepted", null),
                new AdrRef("0003", "Run background jobs with cron", "superseded", "0007"),
                new AdrRef("0022", "GraphQL gateway for the portal", "proposed", null),
                new AdrRef("0031", null, "missing", null));
    }

    @Test
    void withoutAdrDirectoryReferencesAreUnverified(@TempDir Path dir) {
        var noDir = new AdrReferenceResolver(new AdrRepository(dir.resolve("absent"), 1000));
        assertThat(noDir.resolve("ADR-0015")).containsExactly(new AdrRef("0015", null, "unverified", null));
        assertThat(noDir.resolve("ADR-0015").getFirst().isAccepted()).isFalse();
    }

    @Test
    void toolsListFilterAndRejectPathInput() {
        var adrTools = new AdrTools(repository, tools.jackson.databind.json.JsonMapper.builder().build());
        assertThat(adrTools.list("accepted")).contains("\"0007\"", "\"0015\"", "\"0021\"").doesNotContain("\"0003\"", "\"0022\"");
        assertThat(adrTools.read("ADR-15")).contains("Spring AI 2.x");
        for (String bad : List.of("../../pom.xml", "0015-use-spring-ai.md", "/etc/passwd", "")) {
            org.assertj.core.api.Assertions.assertThatThrownBy(() -> adrTools.read(bad))
                    .isInstanceOf(IllegalArgumentException.class);
        }
    }
}
