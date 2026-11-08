package backlogmcp.http;

import static org.assertj.core.api.Assertions.assertThat;

import java.net.InetSocketAddress;
import java.net.Proxy;
import java.net.URI;
import java.util.List;
import java.util.Map;
import java.util.function.Function;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

class LocalBypassProxySelectorTest {

    private static final Function<String, String> NO_SYS_PROPS = key -> null;

    private final LocalBypassProxySelector selector = LocalBypassProxySelector.from(
            Map.of("HTTP_PROXY", "http://proxy.corp:3128",
                    "https_proxy", "http://secure-proxy.corp:8443",
                    "NO_PROXY", ".internal.corp,tracker.acme.com"),
            NO_SYS_PROPS, List.of("my-mock"));

    @ParameterizedTest
    @ValueSource(strings = {
            "http://localhost:8089/api/issues",
            "http://127.0.0.1:8089/api/issues",
            "http://127.0.1.1/x",
            "http://[::1]:8089/x",
            "http://wiremock:8080/api/issues",
            "http://app.localhost/x",
            "http://host.docker.internal:8089/x",
            "http://my-mock:8080/x",                   // extra bypass host
            "https://yt.internal.corp/api/issues",     // NO_PROXY ".internal.corp"
            "https://tracker.acme.com/youtrack/api",   // NO_PROXY exact
            "https://eu.tracker.acme.com/api",         // NO_PROXY subdomain
    })
    void localAndNoProxyHostsGoDirect(String url) {
        assertThat(selector.select(URI.create(url))).containsExactly(Proxy.NO_PROXY);
    }

    @Test
    void remoteHostsUseSchemeSpecificProxy() {
        assertThat(address(selector.select(URI.create("http://acme.youtrack.cloud/api"))))
                .isEqualTo("proxy.corp:3128");
        assertThat(address(selector.select(URI.create("https://acme.youtrack.cloud/api"))))
                .isEqualTo("secure-proxy.corp:8443");
    }

    @Test
    void systemPropertiesWinOverEnvironment() {
        var sel = LocalBypassProxySelector.from(
                Map.of("HTTP_PROXY", "http://env-proxy:1"),
                Map.of("http.proxyHost", "sys-proxy", "http.proxyPort", "8080", "http.nonProxyHosts", "*.lan|nas")::get,
                List.of());
        assertThat(address(sel.select(URI.create("http://example.com")))).isEqualTo("sys-proxy:8080");
        // https falls back to the http proxy when no https proxy is configured
        assertThat(address(sel.select(URI.create("https://example.com")))).isEqualTo("sys-proxy:8080");
        assertThat(sel.select(URI.create("http://box.lan"))).containsExactly(Proxy.NO_PROXY);
        assertThat(sel.select(URI.create("http://nas"))).containsExactly(Proxy.NO_PROXY);
    }

    @Test
    void noProxyConfiguredMeansDirect() {
        var sel = LocalBypassProxySelector.from(Map.of(), NO_SYS_PROPS, List.of());
        assertThat(sel.select(URI.create("https://acme.youtrack.cloud"))).containsExactly(Proxy.NO_PROXY);
    }

    @Test
    void wildcardNoProxyDisablesProxyEverywhere() {
        var sel = LocalBypassProxySelector.from(
                Map.of("HTTP_PROXY", "proxy:3128", "NO_PROXY", "*"), NO_SYS_PROPS, List.of());
        assertThat(sel.select(URI.create("http://example.com"))).containsExactly(Proxy.NO_PROXY);
    }

    @Test
    void credentialsAreNeverExposed() {
        var sel = LocalBypassProxySelector.from(
                Map.of("HTTP_PROXY", "http://user:s3cret@proxy:3128"), NO_SYS_PROPS, List.of());
        assertThat(sel.toString()).doesNotContain("s3cret").contains("proxy:3128");
    }

    private static String address(List<Proxy> proxies) {
        assertThat(proxies).hasSize(1);
        var addr = (InetSocketAddress) proxies.getFirst().address();
        return addr.getHostString() + ":" + addr.getPort();
    }
}
