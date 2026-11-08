package backlogmcp.support;

import java.nio.file.Path;

import org.testcontainers.containers.GenericContainer;
import tools.jackson.databind.JsonNode;
import org.testcontainers.containers.wait.strategy.Wait;
import org.testcontainers.utility.DockerImageName;
import org.testcontainers.utility.MountableFile;

/**
 * WireMock in Docker loaded with the same frozen fixtures as docker-compose.e2e.yml
 * ({@code e2e/wiremock}). Live YouTrack is never contacted in tests (AGENTS.md §5).
 */
public class WireMockContainer extends GenericContainer<WireMockContainer> {

    public static final String IMAGE = "wiremock/wiremock:3.13.2";
    private static final Path FIXTURES = Path.of("e2e/wiremock").toAbsolutePath();

    public WireMockContainer() {
        super(DockerImageName.parse(IMAGE));
        withExposedPorts(8080);
        withCommand("--port=8080", "--disable-banner", "--global-response-templating");
        withCopyFileToContainer(MountableFile.forHostPath(FIXTURES.resolve("mappings")), "/home/wiremock/mappings");
        withCopyFileToContainer(MountableFile.forHostPath(FIXTURES.resolve("__files")), "/home/wiremock/__files");
        waitingFor(Wait.forHttp("/__admin/health").forStatusCode(200));
    }

    /** Base URL as reachable from the host (and from processes started by the test). */
    public String baseUrl() {
        return "http://" + getHost() + ":" + getMappedPort(8080);
    }

    /** HTTP/2 (h2c upgrade by the JDK client) lower-cases header names, so look them up case-insensitively. */
    public static String header(JsonNode request, String name) {
        for (var e : request.get("headers").properties()) {
            if (e.getKey().equalsIgnoreCase(name)) {
                return e.getValue().isArray() ? e.getValue().get(0).stringValue() : e.getValue().stringValue();
            }
        }
        throw new AssertionError("header " + name + " not sent: " + request.get("headers"));
    }
}
