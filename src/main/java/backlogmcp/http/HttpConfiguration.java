package backlogmcp.http;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration(proxyBeanMethods = false)
public class HttpConfiguration {

    private static final Logger log = LoggerFactory.getLogger(HttpConfiguration.class);

    /** One proxy policy for every tracker client. */
    @Bean
    LocalBypassProxySelector trackerProxySelector(HttpProperties http) {
        var selector = LocalBypassProxySelector.fromEnvironment(http.noProxyHosts());
        log.info("Outbound proxy policy: {}", selector);
        return selector;
    }
}
