package backlogmcp.http;

import java.net.ProxySelector;
import java.net.http.HttpClient;
import java.time.Duration;

import org.springframework.http.client.ClientHttpRequestFactory;
import org.springframework.http.client.JdkClientHttpRequestFactory;

/** Shared HTTP plumbing for all read-only tracker clients (YouTrack). */
public final class TrackerHttp {

    private TrackerHttp() {
    }

    /** JDK HttpClient with explicit proxy policy and timeouts. */
    public static ClientHttpRequestFactory requestFactory(Duration connectTimeout, Duration readTimeout,
                                                          ProxySelector proxySelector) {
        HttpClient httpClient = HttpClient.newBuilder()
                .proxy(proxySelector)
                .connectTimeout(connectTimeout)
                .followRedirects(HttpClient.Redirect.NORMAL)
                .build();
        var factory = new JdkClientHttpRequestFactory(httpClient);
        factory.setReadTimeout(readTimeout);
        return factory;
    }

    public static String rootMessage(Throwable t) {
        Throwable root = t;
        while (root.getCause() != null && root.getCause() != root) {
            root = root.getCause();
        }
        return root.getMessage() != null ? root.getMessage() : root.getClass().getSimpleName();
    }
}
