package backlogmcp.tool;

import java.util.function.Supplier;

import io.modelcontextprotocol.spec.McpSchema.CallToolResult;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Builds tool results ourselves instead of letting Spring AI format exceptions. Its default error
 * text is "message + root-cause message": it duplicates our message and, for tracker errors, would
 * append the HTTP client's raw message (response body) to what the agent sees.
 */
public final class ToolResults {

    private static final Logger log = LoggerFactory.getLogger(ToolResults.class);

    private ToolResults() {
    }

    /** Runs a tool body; success → text content, failure → {@code isError} with our curated message only. */
    public static CallToolResult run(String tool, Supplier<String> body) {
        try {
            return CallToolResult.builder().addTextContent(body.get()).build();
        } catch (IllegalArgumentException | IllegalStateException e) {
            log.info("{}: rejected: {}", tool, e.getMessage());
            return error(e.getMessage());
        } catch (RuntimeException e) {
            if (e.getClass().getPackageName().startsWith("backlogmcp")) {
                return error(e.getMessage()); // our client exceptions carry safe, curated messages
            }
            log.warn("{}: unexpected failure", tool, e); // full detail to stderr only
            return error(tool + " failed unexpectedly (" + e.getClass().getSimpleName() + "); see server logs");
        }
    }

    private static CallToolResult error(String message) {
        return CallToolResult.builder().isError(true).addTextContent(message).build();
    }
}
