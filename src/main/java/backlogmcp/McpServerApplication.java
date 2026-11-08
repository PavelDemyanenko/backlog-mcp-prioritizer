package backlogmcp;

import org.springframework.boot.Banner;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.WebApplicationType;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;

/**
 * Micro-MCP server for backlog prioritization (YouTrack, read-only).
 *
 * <p>Transport: STDIO. The {@code StdioServerTransportProvider} is created by
 * Spring AI auto-configuration ({@code spring.ai.mcp.server.stdio=true}) and binds to
 * {@code System.in} / {@code System.out}. Tools annotated with {@code @McpTool} are
 * discovered automatically and registered with the server.
 *
 * <p><b>stdout is reserved for JSON-RPC frames.</b> Nothing in this codebase may write
 * to {@code System.out}; all logging goes to {@code System.err} (see logback-spring.xml).
 */
@SpringBootApplication
@ConfigurationPropertiesScan
public class McpServerApplication {

    public static void main(String[] args) {
        var app = new SpringApplication(McpServerApplication.class);
        // Hard-coded (not only via YAML) so a misconfigured profile can never re-enable them.
        app.setBannerMode(Banner.Mode.OFF);
        app.setWebApplicationType(WebApplicationType.NONE);
        app.setLogStartupInfo(true); // goes to stderr via Logback
        app.run(args);
        // The STDIO transport reads System.in on a non-daemon thread; the JVM stays alive
        // until the client closes stdin.
    }
}
