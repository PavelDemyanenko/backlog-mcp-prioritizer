package backlogmcp.youtrack;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.method;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.queryParam;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

import java.net.URI;
import java.time.Duration;
import java.util.stream.Collectors;
import java.util.stream.IntStream;

import org.junit.jupiter.api.Test;

import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

class YouTrackCountTest {

    private static String ids(int from, int to) {
        return IntStream.range(from, to).mapToObj(i -> "{\"id\":\"2-" + i + "\"}")
                .collect(Collectors.joining(",", "[", "]"));
    }

    private static YouTrackClient client(RestClient.Builder builder) {
        var props = new YouTrackProperties(URI.create("http://yt"), "t", Duration.ofSeconds(1), Duration.ofSeconds(1), 100, 480);
        return new YouTrackClient(builder.baseUrl("http://yt").build(), props);
    }

    @Test
    void pagesBeyondOneHundredWithGetOnly() {
        var builder = RestClient.builder();
        var server = MockRestServiceServer.bindTo(builder).build();
        server.expect(queryParam("$skip", "0")).andExpect(method(HttpMethod.GET))
                .andRespond(withSuccess(ids(0, 500), MediaType.APPLICATION_JSON));
        server.expect(queryParam("$skip", "500")).andExpect(method(HttpMethod.GET))
                .andRespond(withSuccess(ids(500, 503), MediaType.APPLICATION_JSON));

        var count = client(builder).countIssues("State: {In Progress}");

        assertThat(count.count()).isEqualTo(503);
        assertThat(count.capped()).isFalse();
        server.verify();
    }

    @Test
    void serverIgnoringSkipCannotInflateTheCount() {
        var builder = RestClient.builder();
        var server = MockRestServiceServer.bindTo(builder).build();
        server.expect(queryParam("$skip", "0")).andRespond(withSuccess(ids(0, 500), MediaType.APPLICATION_JSON));
        server.expect(queryParam("$skip", "500")).andRespond(withSuccess(ids(0, 500), MediaType.APPLICATION_JSON));

        assertThat(client(builder).countIssues("x").count()).isEqualTo(500);
    }
}
