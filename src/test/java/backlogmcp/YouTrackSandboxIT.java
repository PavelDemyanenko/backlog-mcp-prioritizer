package backlogmcp;

import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;

/**
 * The Golden Dataset contract against a <b>real</b> YouTrack (docker compose profile
 * {@code sandbox}, seeded by {@code e2e/youtrack-sandbox/seed.py}). Validates that the hand-written
 * WireMock fixtures match what the real API returns. Skipped unless the sandbox env is set:
 * <pre>source e2e/youtrack-sandbox/.env && mvn verify -Dit.test=YouTrackSandboxIT</pre>
 */
@EnabledIfEnvironmentVariable(named = "YOUTRACK_SANDBOX_TOKEN", matches = ".+")
class YouTrackSandboxIT extends GoldenBacklogContract {

    YouTrackSandboxIT() {
        super(System.getenv().getOrDefault("YOUTRACK_SANDBOX_URL", "http://127.0.0.1:8088"),
                System.getenv("YOUTRACK_SANDBOX_TOKEN"));
    }
}
