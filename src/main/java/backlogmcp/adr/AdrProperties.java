package backlogmcp.adr;

import java.nio.file.Path;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.bind.DefaultValue;

/**
 * @param dir          ADR directory; relative paths resolve against the server's working
 *                     directory (the project the agent works in)
 * @param maxReadChars cap for {@code adr_read} output
 */
@ConfigurationProperties("adr")
public record AdrProperties(
        @DefaultValue("docs/adr") Path dir,
        @DefaultValue("20000") int maxReadChars) {
}
