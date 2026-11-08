package backlogmcp.support;

import java.nio.file.Path;

import backlogmcp.adr.AdrReferenceResolver;
import backlogmcp.adr.AdrRepository;

/** ADR resolvers over the committed fixtures. */
public final class TestAdr {

    /** {@code e2e/adr}: fixtures used by tracker tests (0003 superseded, 0007/0015/0021 accepted, 0022 proposed). */
    public static final Path E2E_DIR = Path.of("e2e/adr").toAbsolutePath();
    /** {@code evals/golden/adr}: only 0015 accepted (Golden Dataset). */
    public static final Path GOLDEN_DIR = Path.of("evals/golden/adr").toAbsolutePath();

    private TestAdr() {
    }

    public static AdrReferenceResolver resolver(Path dir) {
        return new AdrReferenceResolver(new AdrRepository(dir, 20_000));
    }

    public static AdrReferenceResolver e2e() {
        return resolver(E2E_DIR);
    }
}
