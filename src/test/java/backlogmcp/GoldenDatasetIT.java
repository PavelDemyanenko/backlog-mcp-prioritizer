package backlogmcp;

import backlogmcp.support.WireMockContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

/**
 * Golden Dataset contract against the generated WireMock fixtures. A dataset edit that accidentally
 * changes a scenario (e.g. a description now containing "evidence") fails here.
 */
@Testcontainers
class GoldenDatasetIT extends GoldenBacklogContract {

    @Container
    static final WireMockContainer WIREMOCK = new WireMockContainer();

    GoldenDatasetIT() {
        super(WIREMOCK.baseUrl(), "golden-token");
    }
}
