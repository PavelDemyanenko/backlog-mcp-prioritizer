package backlogmcp;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.regex.Pattern;
import java.util.stream.Stream;

import org.junit.jupiter.api.Test;

/**
 * Guard for the STDIO contract (spec §8.1): production code must never write to stdout.
 * Cheap static check; the E2E test verifies the runtime behaviour.
 */
class StdoutHygieneTest {

    private static final Pattern FORBIDDEN = Pattern.compile(
            "System\\.out|\\bprintStackTrace\\(\\s*\\)|\\bIO\\.print(ln)?\\(|FileDescriptor\\.out");

    @Test
    void productionCodeDoesNotWriteToStdout() throws IOException {
        List<String> offenders;
        try (Stream<Path> files = Files.walk(Path.of("src/main/java"))) {
            offenders = files.filter(p -> p.toString().endsWith(".java"))
                    .flatMap(StdoutHygieneTest::offendingLines)
                    .toList();
        }
        assertThat(offenders).as("stdout is reserved for MCP JSON-RPC").isEmpty();
    }

    @Test
    void logbackHasNoStdoutAppender() throws IOException {
        String xml = Files.readString(Path.of("src/main/resources/logback-spring.xml"))
                .replaceAll("(?s)<!--.*?-->", ""); // comments may legitimately mention System.out
        assertThat(xml).contains("<target>System.err</target>")
                .doesNotContain("System.out")
                .doesNotContain("console-appender.xml")
                .doesNotContain("base.xml");
    }

    private static Stream<String> offendingLines(Path file) {
        try {
            List<String> lines = Files.readAllLines(file);
            return java.util.stream.IntStream.range(0, lines.size())
                    .filter(i -> !lines.get(i).strip().startsWith("*") && !lines.get(i).strip().startsWith("//"))
                    .filter(i -> FORBIDDEN.matcher(lines.get(i)).find())
                    .mapToObj(i -> file + ":" + (i + 1) + ": " + lines.get(i).strip());
        } catch (IOException e) {
            throw new IllegalStateException(e);
        }
    }
}
