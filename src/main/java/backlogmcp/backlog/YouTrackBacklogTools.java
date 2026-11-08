package backlogmcp.backlog;

import java.util.List;

import backlogmcp.youtrack.YouTrackClient;
import backlogmcp.youtrack.YouTrackIssueNormalizer;
import backlogmcp.youtrack.YouTrackProperties;
import backlogmcp.tool.ToolResults;
import io.modelcontextprotocol.spec.McpSchema.CallToolResult;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import tools.jackson.databind.json.JsonMapper;

import org.springframework.ai.mcp.annotation.McpTool;
import org.springframework.ai.mcp.annotation.McpToolParam;
import org.springframework.stereotype.Component;

/**
 * MCP tool {@code youtrack_query_backlog} (spec §8.2).
 *
 * <p>Failures (bad input, auth, network) are thrown as exceptions; the MCP layer turns
 * them into a {@code CallToolResult} with {@code isError=true} and the exception message,
 * so the agent sees a readable error instead of a broken session.
 */
@Component
public class YouTrackBacklogTools {

    private static final Logger log = LoggerFactory.getLogger(YouTrackBacklogTools.class);

    private final YouTrackClient client;
    private final YouTrackIssueNormalizer normalizer;
    private final YouTrackProperties props;
    private final JsonMapper jsonMapper;

    public YouTrackBacklogTools(YouTrackClient client, YouTrackIssueNormalizer normalizer,
                                YouTrackProperties props, JsonMapper jsonMapper) {
        this.client = client;
        this.normalizer = normalizer;
        this.props = props;
        this.jsonMapper = jsonMapper;
    }

    // Parameter names are the wire names of the JSON schema (compiled with -parameters),
    // hence snake_case Java identifiers.
    @McpTool(
            name = "youtrack_query_backlog",
            title = "Query YouTrack backlog (read-only)",
            description = """
                    Fetches issues from YouTrack using a YouTrack search query and returns a normalized \
                    JSON array: [{"id","summary","status","story_points","story_points_source","evidence_found_in_text","triage"}]. \
                    status comes from the State field, story_points from the "Story points" field (null if \
                    unset; then the "Estimation" period field is used, 1 SP = 8h, story_points_source \
                    "time_estimate_fallback"; "custom_field" when Story points is set; null when neither). evidence_found_in_text is true when the description links product evidence \
                    (Confluence, Google Docs, an ADR) or contains the word "evidence"; false means Evidence \
                    Tier 3-4 (discount Confidence to 0.5). triage holds critical-task signals: {"issue_type","priority","labels","components",\
                    "due_date" (yyyy-MM-dd or null),"cvss_score" (highest CVSS base score found in summary or \
                    description, or null)}. The description itself is not returned. Read-only: never modifies the tracker.""",
            annotations = @McpTool.McpAnnotations(
                    title = "Query YouTrack backlog",
                    readOnlyHint = true,
                    destructiveHint = false,
                    idempotentHint = true,
                    openWorldHint = true))
    public CallToolResult youtrackQueryBacklog(
            @McpToolParam(required = true, description =
                    "Strict YouTrack search query, e.g. 'project: DEV #Unresolved sort by: created desc'")
            String search_query,
            @McpToolParam(required = false, description =
                    "Maximum number of issues to return (default 20, max 100)")
            Integer limit) {
        return ToolResults.run("youtrack_query_backlog", () -> {
            if (search_query == null || search_query.isBlank()) {
                throw new IllegalArgumentException("search_query must not be blank");
            }
            int effectiveLimit = BacklogLimits.resolve(limit, props.maxLimit());

            List<BacklogIssue> issues = normalizer.normalize(client.searchIssues(search_query.strip(), effectiveLimit));
            log.info("youtrack_query_backlog: {} issue(s), {} with evidence",
                    issues.size(), issues.stream().filter(BacklogIssue::evidenceFoundInText).count());
            return jsonMapper.writeValueAsString(issues);
        });
    }

    @McpTool(
            name = "youtrack_count_issues",
            title = "Count YouTrack issues (read-only)",
            description = """
                    Counts issues matching a YouTrack search query without the 100-issue limit of \
                    youtrack_query_backlog, e.g. work in progress for team utilization (rho): \
                    'project: DEV State: {In Progress}'. Returns {"count": n, "capped": bool}; capped is true \
                    only above 10000 issues. Read-only.""",
            annotations = @McpTool.McpAnnotations(
                    title = "Count YouTrack issues",
                    readOnlyHint = true,
                    destructiveHint = false,
                    idempotentHint = true,
                    openWorldHint = true))
    public CallToolResult youtrackCountIssues(
            @McpToolParam(required = true, description = "YouTrack search query") String search_query) {
        return ToolResults.run("youtrack_count_issues", () -> {
            if (search_query == null || search_query.isBlank()) {
                throw new IllegalArgumentException("search_query must not be blank");
            }
            var count = client.countIssues(search_query.strip());
            var body = new java.util.LinkedHashMap<String, Object>();   // stable field order (Map.of has none)
            body.put("count", count.count());
            body.put("capped", count.capped());
            return jsonMapper.writeValueAsString(body);
        });
    }
}
