package backlogmcp.youtrack;

import backlogmcp.http.LocalBypassProxySelector;
import backlogmcp.http.TrackerHttp;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.web.client.RestClient;

@Configuration(proxyBeanMethods = false)
public class YouTrackClientConfiguration {

    private static final Logger log = LoggerFactory.getLogger(YouTrackClientConfiguration.class);

    @Bean
    YouTrackClient youTrackClient(RestClient.Builder builder, YouTrackProperties props,
                                  LocalBypassProxySelector proxySelector) {
        log.info("YouTrack client: {}", props);
        return new YouTrackClient(createRestClient(builder, props, proxySelector), props);
    }

    /** Also used directly by integration tests, without a Spring context. */
    public static RestClient createRestClient(RestClient.Builder builder, YouTrackProperties props,
                                              LocalBypassProxySelector proxySelector) {
        return builder.clone()
                .baseUrl(props.baseUrl().toString())
                .requestFactory(TrackerHttp.requestFactory(props.connectTimeout(), props.readTimeout(), proxySelector))
                .defaultHeader(HttpHeaders.ACCEPT, MediaType.APPLICATION_JSON_VALUE)
                .defaultHeaders(h -> {
                    if (props.hasToken()) {
                        h.setBearerAuth(props.token().trim());
                    }
                })
                .build();
    }
}
