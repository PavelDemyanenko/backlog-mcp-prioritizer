package backlogmcp.adr;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Optional;
import java.util.stream.Stream;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

/**
 * Read-only view of the ADR directory. Re-scanned on every call: ADR sets are small and the
 * agent must see edits immediately (no stale cache between a draft and its review).
 */
@Component
public class AdrRepository {

    private static final Logger log = LoggerFactory.getLogger(AdrRepository.class);

    private final Path dir;
    private final int maxReadChars;

    @Autowired
    public AdrRepository(AdrProperties props) {
        this(props.dir(), props.maxReadChars());
    }

    public AdrRepository(Path dir, int maxReadChars) {
        this.dir = dir.toAbsolutePath().normalize();
        this.maxReadChars = maxReadChars;
        if (!Files.isDirectory(this.dir)) {
            log.warn("ADR directory {} does not exist: ADR references cannot be verified "
                    + "(set ADR_DIR); they will be reported as 'unverified' and not count as evidence", this.dir);
        } else {
            log.info("ADR directory: {}", this.dir);
        }
    }

    public boolean available() {
        return Files.isDirectory(dir);
    }

    public Path dir() {
        return dir;
    }

    /** All ADRs ordered by id; files not named {@code NNNN-slug.md} are ignored. */
    public List<Adr> list() {
        if (!available()) {
            return List.of();
        }
        List<Adr> out = new ArrayList<>();
        try (Stream<Path> files = Files.list(dir)) {
            for (Path file : files.filter(Files::isRegularFile).toList()) {
                MadrParser.parse(file.getFileName().toString(), readFile(file)).ifPresent(out::add);
            }
        } catch (IOException e) {
            throw new UncheckedIOException("Cannot list ADR directory " + dir, e);
        }
        out.sort(Comparator.comparing(Adr::id).thenComparing(Adr::file));
        return out;
    }

    public Optional<Adr> find(String id) {
        String normalized = MadrParser.normalizeId(id);
        return list().stream().filter(a -> a.id().equals(normalized)).findFirst();
    }

    /** Markdown of an ADR, capped at {@code maxReadChars}. Lookup by id only: no path input. */
    public Optional<String> read(String id) {
        return find(id).map(adr -> {
            String text = readFile(dir.resolve(adr.file()));
            return text.length() <= maxReadChars ? text
                    : text.substring(0, maxReadChars) + "\n\n[truncated at " + maxReadChars + " characters]";
        });
    }

    private static String readFile(Path file) {
        try {
            return Files.readString(file, StandardCharsets.UTF_8);
        } catch (IOException e) {
            throw new UncheckedIOException("Cannot read " + file, e);
        }
    }
}
