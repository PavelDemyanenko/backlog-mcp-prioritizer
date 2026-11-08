package backlogmcp;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.io.Writer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.TimeUnit;

import backlogmcp.support.WireMockContainer;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.MethodOrderer;
import org.junit.jupiter.api.Order;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestMethodOrder;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

/**
 * Black-box E2E: launches the packaged jar exactly like Claude Code / Cursor would
 * (a child process speaking JSON-RPC over STDIO) against WireMock in Docker.
 *
 * <p>Verifies the protocol (initialize, tools/list, tools/call), the tool contract, and
 * that <b>every</b> byte the server writes to stdout is a JSON-RPC message.
 */
@Testcontainers
@TestMethodOrder(MethodOrderer.OrderAnnotation.class)
class McpStdioE2EIT {

    @Container
    static final WireMockContainer WIREMOCK = new WireMockContainer();

    private static final Path JAR = Path.of("target/backlog-mcp-server.jar");
    private static final Duration RESPONSE_TIMEOUT = Duration.ofSeconds(30);
    private static final JsonMapper JSON = JsonMapper.builder().build();

    private static Process process;
    private static Writer stdin;
    private static final BlockingQueue<String> STDOUT_LINES = new LinkedBlockingQueue<>();
    private static final List<String> ALL_STDOUT = java.util.Collections.synchronizedList(new ArrayList<>());
    private static int nextId = 1;

    @BeforeAll
    static void startServer() throws Exception {
        assertThat(JAR).as("run `mvn verify` (jar is built in the package phase)").exists();
        String java = ProcessHandle.current().info().command().orElse("java");
        var pb = new ProcessBuilder(java, "-jar", JAR.toString());
        // Inherit the real environment (incl. HTTP_PROXY) to prove the proxy bypass works.
        pb.environment().putAll(Map.of(
                "YOUTRACK_BASE_URL", WIREMOCK.baseUrl(),
                "YOUTRACK_TOKEN", "e2e-token",
                "ADR_DIR", backlogmcp.support.TestAdr.E2E_DIR.toString()));
        pb.redirectError(Files.createDirectories(Path.of("target/e2e")).resolve("mcp-server.stderr.log").toFile());
        process = pb.start();
        stdin = new OutputStreamWriter(process.getOutputStream(), StandardCharsets.UTF_8);

        Thread.ofVirtual().name("mcp-stdout-reader").start(() -> {
            try (var reader = new BufferedReader(new InputStreamReader(process.getInputStream(), StandardCharsets.UTF_8))) {
                String line;
                while ((line = reader.readLine()) != null) {
                    ALL_STDOUT.add(line);
                    STDOUT_LINES.add(line);
                }
            } catch (IOException ignored) {
                // process ended
            }
        });

        JsonNode init = request("initialize", Map.of(
                "protocolVersion", "2025-06-18",
                "capabilities", Map.of(),
                "clientInfo", Map.of("name", "e2e-test", "version", "1")));
        assertThat(init.at("/result/serverInfo/name").stringValue()).isEqualTo("backlog-mcp-prioritizer");
        notify("notifications/initialized");
    }

    @AfterAll
    static void stopServer() throws Exception {
        if (process == null) {
            return;
        }
        stdin.close(); // EOF on stdin = client disconnected
        boolean exited = process.waitFor(15, TimeUnit.SECONDS);
        if (!exited) {
            process.destroyForcibly();
        }
        // The STDIO contract: nothing but JSON-RPC 2.0 on stdout, ever.
        Thread.sleep(200);
        assertThat(ALL_STDOUT).isNotEmpty().allSatisfy(line -> {
            JsonNode node = JSON.readTree(line);
            assertThat(node.get("jsonrpc").stringValue()).isEqualTo("2.0");
        });
        assertThat(exited).as("server exits when stdin is closed").isTrue();
    }

    @Test
    @Order(1)
    void listsYouTrackToolWithContractSchema() throws Exception {
        JsonNode tools = request("tools/list", Map.of()).at("/result/tools");
        JsonNode tool = null;
        for (JsonNode t : tools) {
            if ("youtrack_query_backlog".equals(t.get("name").stringValue())) {
                tool = t;
            }
        }
        assertThat(tool).as("youtrack_query_backlog registered").isNotNull();

        JsonNode schema = tool.get("inputSchema");
        assertThat(schema.at("/properties/search_query/type").stringValue()).isEqualTo("string");
        assertThat(schema.at("/properties/limit/type").stringValue()).isEqualTo("integer");
        List<String> required = new ArrayList<>();
        schema.get("required").forEach(n -> required.add(n.stringValue()));
        assertThat(required).containsExactly("search_query");
        assertThat(tool.at("/annotations/readOnlyHint").booleanValue()).isTrue();
        assertThat(tool.at("/annotations/destructiveHint").booleanValue()).isFalse();
    }

    @Test
    @Order(2)
    void callReturnsNormalizedBacklog() throws Exception {
        JsonNode result = request("tools/call", Map.of(
                "name", "youtrack_query_backlog",
                "arguments", Map.of("search_query", "project: DEV #Unresolved", "limit", 3))).get("result");

        assertThat(result.path("isError").asBoolean(false)).isFalse();
        JsonNode issues = JSON.readTree(result.at("/content/0/text").stringValue());
        assertThat(issues.size()).isEqualTo(3);
        assertThat(JSON.writeValueAsString(issues.get(0))).isEqualTo(
                "{\"id\":\"DEV-1\",\"summary\":\"Migrate prioritization service to Spring AI\",\"status\":\"To Do\","
                        + "\"story_points\":5,\"story_points_source\":\"custom_field\",\"evidence_found_in_text\":true,"
                        + "\"adr_refs\":[{\"id\":\"0015\",\"title\":\"Use Spring AI for the generation service\",\"status\":\"accepted\",\"superseded_by\":null}],"
                        + "\"triage\":{\"issue_type\":\"Task\",\"priority\":\"Major\",\"labels\":[\"architecture\"],"
                        + "\"components\":[\"Prioritization\",\"MCP\"],\"due_date\":null,\"cvss_score\":null}}");
        assertThat(issues.get(1).get("evidence_found_in_text").booleanValue()).isFalse();
        assertThat(issues.get(2).get("status").stringValue()).isEqualTo("In Progress");
    }

    @Test
    @Order(3)
    void limitDefaultsTo20() throws Exception {
        JsonNode result = request("tools/call", Map.of(
                "name", "youtrack_query_backlog",
                "arguments", Map.of("search_query", "project: DEV"))).get("result");
        JsonNode issues = JSON.readTree(result.at("/content/0/text").stringValue());
        assertThat(issues.size()).isEqualTo(7);
        JsonNode cve = issues.get(6);
        assertThat(cve.get("id").stringValue()).isEqualTo("DEV-7");
        assertThat(cve.at("/triage/cvss_score").decimalValue()).isEqualByComparingTo("9.8");
        assertThat(cve.at("/triage/priority").stringValue()).isEqualTo("Show-stopper");
        assertThat(cve.has("description")).as("raw description is never exposed").isFalse();
    }

    @Test
    @Order(4)
    void invalidInputIsAToolErrorNotAProtocolFailure() throws Exception {
        JsonNode response = request("tools/call", Map.of(
                "name", "youtrack_query_backlog",
                "arguments", Map.of("search_query", "  ", "limit", 5)));
        JsonNode result = response.get("result");
        assertThat(result).as("tool errors are reported in-band: %s", response).isNotNull();
        assertThat(result.get("isError").booleanValue()).isTrue();
        assertThat(result.at("/content/0/text").stringValue())
                .as("our message only, once (Spring AI would append the root cause)")
                .isEqualTo("search_query must not be blank");

        // server is still healthy afterwards
        assertThat(request("tools/list", Map.of()).at("/result/tools").size()).isPositive();
    }

    @Test
    @Order(8)
    void adrToolsListAndReadWithoutPathAccess() throws Exception {
        JsonNode list = request("tools/call", Map.of("name", "adr_list",
                "arguments", Map.of("status", "accepted"))).get("result");
        JsonNode adrs = JSON.readTree(list.at("/content/0/text").stringValue());
        List<String> ids = new ArrayList<>();
        adrs.forEach(a -> ids.add(a.get("id").stringValue()));
        assertThat(ids).containsExactly("0007", "0015", "0021");

        JsonNode read = request("tools/call", Map.of("name", "adr_read", "arguments", Map.of("id", "ADR-15"))).get("result");
        assertThat(read.at("/content/0/text").stringValue()).contains("Spring AI 2.x");

        JsonNode traversal = request("tools/call", Map.of("name", "adr_read",
                "arguments", Map.of("id", "../../pom.xml"))).get("result");
        assertThat(traversal.get("isError").booleanValue()).isTrue();
        assertThat(findTool("adr_list").at("/annotations/readOnlyHint").booleanValue()).isTrue();
    }

    @Test
    @Order(9)
    void countToolCountsWithoutTheHundredIssueLimit() throws Exception {
        JsonNode result = request("tools/call", Map.of("name", "youtrack_count_issues",
                "arguments", Map.of("search_query", "project: GOLD State: {In Progress}"))).get("result");
        assertThat(result.path("isError").asBoolean(false)).as("%s", result).isFalse();
        assertThat(result.at("/content/0/text").stringValue()).isEqualTo("{\"count\":9,\"capped\":false}");
        assertThat(findTool("youtrack_count_issues").at("/annotations/readOnlyHint").booleanValue()).isTrue();
    }

    private static JsonNode findTool(String name) throws Exception {
        for (JsonNode t : request("tools/list", Map.of()).at("/result/tools")) {
            if (name.equals(t.get("name").stringValue())) {
                return t;
            }
        }
        throw new AssertionError(name + " is not registered");
    }

    // ---- minimal JSON-RPC client ----

    private static JsonNode request(String method, Map<String, Object> params) throws Exception {
        int id = nextId++;
        send(Map.of("jsonrpc", "2.0", "id", id, "method", method, "params", params));
        long deadline = System.nanoTime() + RESPONSE_TIMEOUT.toNanos();
        while (System.nanoTime() < deadline) {
            String line = STDOUT_LINES.poll(500, TimeUnit.MILLISECONDS);
            if (line == null) {
                assertThat(process.isAlive()).as("server process died; see target/e2e/mcp-server.stderr.log").isTrue();
                continue;
            }
            JsonNode node = JSON.readTree(line); // fails fast on any non-JSON stdout
            if (node.has("id") && node.get("id").asInt() == id) {
                return node;
            }
        }
        throw new AssertionError("No response to " + method + " within " + RESPONSE_TIMEOUT);
    }

    private static void notify(String method) throws IOException {
        send(Map.of("jsonrpc", "2.0", "method", method));
    }

    private static void send(Map<String, Object> message) throws IOException {
        stdin.write(JSON.writeValueAsString(message));
        stdin.write('\n');
        stdin.flush();
    }
}
