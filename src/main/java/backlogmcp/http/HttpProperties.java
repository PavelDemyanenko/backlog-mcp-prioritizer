package backlogmcp.http;

import java.util.List;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.bind.DefaultValue;

/**
 * Outbound HTTP settings shared by all tracker clients.
 *
 * @param noProxyHosts extra hosts to reach directly, on top of
 *                     {@link LocalBypassProxySelector#ALWAYS_DIRECT} and {@code NO_PROXY}
 */
@ConfigurationProperties("mcp.http")
public record HttpProperties(@DefaultValue({}) List<String> noProxyHosts) {
}
