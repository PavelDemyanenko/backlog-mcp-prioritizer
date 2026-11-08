package backlogmcp.http;

import java.io.IOException;
import java.net.InetSocketAddress;
import java.net.Proxy;
import java.net.ProxySelector;
import java.net.SocketAddress;
import java.net.URI;
import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import java.util.function.Function;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Explicit, predictable proxy policy for outbound tracker calls.
 *
 * <p>The JDK {@code HttpClient} ignores {@code HTTP_PROXY}/{@code NO_PROXY} environment
 * variables, while {@code curl}-style tooling and corporate setups (WSL, Docker Desktop)
 * rely on them. This selector reads both the env variables and the {@code http(s).proxyHost}
 * system properties, and <b>always</b> connects directly to local/test hosts
 * ({@code localhost}, {@code 127.*}, {@code ::1}, {@code wiremock}, {@code *.localhost},
 * plus anything listed in {@code NO_PROXY} or passed as extra bypass hosts).
 */
public final class LocalBypassProxySelector extends ProxySelector {

    private static final Logger log = LoggerFactory.getLogger(LocalBypassProxySelector.class);

    /** Hosts that must never go through a proxy (E2E isolation: WireMock is local). */
    public static final List<String> ALWAYS_DIRECT = List.of(
            "localhost", "127.0.0.1", "::1", "[::1]", "0.0.0.0", "wiremock", "host.docker.internal");

    private static final List<Proxy> DIRECT = List.of(Proxy.NO_PROXY);

    private final Proxy httpProxy;   // null = direct
    private final Proxy httpsProxy;  // null = direct
    private final List<String> bypassRules;
    private final boolean bypassAll;

    LocalBypassProxySelector(Proxy httpProxy, Proxy httpsProxy, Collection<String> bypassRules) {
        this.httpProxy = httpProxy;
        this.httpsProxy = httpsProxy;
        var rules = new ArrayList<String>();
        for (String rule : bypassRules) {
            String r = rule.trim().toLowerCase(Locale.ROOT);
            if (!r.isEmpty()) {
                rules.add(r);
            }
        }
        this.bypassAll = rules.contains("*");
        this.bypassRules = List.copyOf(rules);
    }

    /** Builds the selector from the process environment and JVM system properties. */
    public static LocalBypassProxySelector fromEnvironment(Collection<String> extraBypassHosts) {
        return from(System.getenv(), System::getProperty, extraBypassHosts);
    }

    /** Testable factory: {@code env} = environment map, {@code sysProps} = system property lookup. */
    static LocalBypassProxySelector from(Map<String, String> env, Function<String, String> sysProps,
                                         Collection<String> extraBypassHosts) {
        Proxy http = fromSystemProperty(sysProps, "http")
                .or(() -> fromEnvUrl(env, "HTTP_PROXY"))
                .orElse(null);
        Proxy https = fromSystemProperty(sysProps, "https")
                .or(() -> fromEnvUrl(env, "HTTPS_PROXY"))
                .orElse(http);

        var rules = new ArrayList<>(ALWAYS_DIRECT);
        rules.addAll(extraBypassHosts);
        rules.addAll(splitList(envValue(env, "NO_PROXY"), ","));
        rules.addAll(splitList(sysProps.apply("http.nonProxyHosts"), "|"));
        return new LocalBypassProxySelector(http, https, rules);
    }

    @Override
    public List<Proxy> select(URI uri) {
        if (uri == null) {
            throw new IllegalArgumentException("URI must not be null");
        }
        String host = uri.getHost();
        if (host == null || isBypassed(host)) {
            return DIRECT;
        }
        Proxy proxy = "https".equalsIgnoreCase(uri.getScheme()) ? httpsProxy : httpProxy;
        return proxy == null ? DIRECT : List.of(proxy);
    }

    @Override
    public void connectFailed(URI uri, SocketAddress sa, IOException ioe) {
        log.warn("Proxy connection to {} via {} failed: {}", uri.getHost(), sa, ioe.getMessage());
    }

    boolean isBypassed(String rawHost) {
        if (bypassAll) {
            return true;
        }
        String host = rawHost.toLowerCase(Locale.ROOT);
        if (host.startsWith("[") && host.endsWith("]")) {
            host = host.substring(1, host.length() - 1);
        }
        if (host.startsWith("127.") || host.equals("::1") || host.endsWith(".localhost")) {
            return true;
        }
        for (String rule : bypassRules) {
            // NO_PROXY conventions: "example.com", ".example.com", "*.example.com"
            String suffix = rule.startsWith("*.") ? rule.substring(1) : rule;
            if (suffix.startsWith(".")) {
                if (host.endsWith(suffix) || host.equals(suffix.substring(1))) {
                    return true;
                }
            } else if (host.equals(rule) || host.endsWith("." + rule)) {
                return true;
            }
        }
        return false;
    }

    private static Optional<Proxy> fromSystemProperty(Function<String, String> sysProps, String scheme) {
        String host = sysProps.apply(scheme + ".proxyHost");
        if (host == null || host.isBlank()) {
            return Optional.empty();
        }
        int port = parsePort(sysProps.apply(scheme + ".proxyPort"), "https".equals(scheme) ? 443 : 80);
        return Optional.of(new Proxy(Proxy.Type.HTTP, InetSocketAddress.createUnresolved(host, port)));
    }

    private static Optional<Proxy> fromEnvUrl(Map<String, String> env, String name) {
        String value = envValue(env, name);
        if (value == null || value.isBlank()) {
            return Optional.empty();
        }
        try {
            URI uri = URI.create(value.contains("://") ? value.trim() : "http://" + value.trim());
            if (uri.getHost() == null) {
                return Optional.empty();
            }
            if (uri.getUserInfo() != null) {
                // Never log credentials; proxy auth is not supported by this selector.
                log.warn("{} contains credentials; proxy authentication is not supported and is ignored", name);
            }
            int port = uri.getPort() != -1 ? uri.getPort() : ("https".equalsIgnoreCase(uri.getScheme()) ? 443 : 80);
            return Optional.of(new Proxy(Proxy.Type.HTTP, InetSocketAddress.createUnresolved(uri.getHost(), port)));
        } catch (IllegalArgumentException e) {
            log.warn("Ignoring malformed {} value", name);
            return Optional.empty();
        }
    }

    /** Env lookup accepting both UPPER and lower case (curl convention). */
    private static String envValue(Map<String, String> env, String upperName) {
        String v = env.get(upperName);
        return v != null ? v : env.get(upperName.toLowerCase(Locale.ROOT));
    }

    private static List<String> splitList(String value, String separator) {
        if (value == null || value.isBlank()) {
            return List.of();
        }
        return List.of(value.split(java.util.regex.Pattern.quote(separator)));
    }

    private static int parsePort(String value, int fallback) {
        try {
            return value == null ? fallback : Integer.parseInt(value.trim());
        } catch (NumberFormatException e) {
            return fallback;
        }
    }

    @Override
    public String toString() {
        return "LocalBypassProxySelector[http=" + describe(httpProxy) + ", https=" + describe(httpsProxy)
                + ", bypass=" + (bypassAll ? "*" : bypassRules) + "]";
    }

    private static String describe(Proxy p) {
        if (p == null || !(p.address() instanceof InetSocketAddress addr)) {
            return "DIRECT";
        }
        return addr.getHostString() + ":" + addr.getPort();
    }
}
