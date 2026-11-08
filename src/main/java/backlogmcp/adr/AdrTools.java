package backlogmcp.adr;

import java.util.List;
import java.util.Locale;

import backlogmcp.tool.ToolResults;
import io.modelcontextprotocol.spec.McpSchema.CallToolResult;

import tools.jackson.databind.json.JsonMapper;

import org.springframework.ai.mcp.annotation.McpTool;
import org.springframework.ai.mcp.annotation.McpToolParam;
import org.springframework.stereotype.Component;

/** Read-only MCP tools over the project's ADR directory (AGENTS.md §2, ADR Custodian). */
@Component
public class AdrTools {

    private final AdrRepository repository;
    private final JsonMapper jsonMapper;

    public AdrTools(AdrRepository repository, JsonMapper jsonMapper) {
        this.repository = repository;
        this.jsonMapper = jsonMapper;
    }

    @McpTool(
            name = "adr_list",
            title = "List architecture decision records",
            description = """
                    Lists ADRs from the project's ADR directory (default docs/adr) as a JSON array: \
                    [{"id","title","status","date","superseded_by","file"}]. status is one of proposed, \
                    accepted, rejected, deprecated, superseded, unknown. Only accepted ADRs are binding \
                    and count as evidence. Read-only.""",
            annotations = @McpTool.McpAnnotations(title = "List ADRs", readOnlyHint = true,
                    destructiveHint = false, idempotentHint = true, openWorldHint = false))
    public CallToolResult adrList(
            @McpToolParam(required = false, description = "Only ADRs with this status, e.g. 'accepted'")
            String status) {
        return ToolResults.run("adr_list", () -> list(status));
    }

    String list(String status) {
        if (!repository.available()) {
            throw new IllegalStateException("ADR directory " + repository.dir() + " does not exist (set ADR_DIR)");
        }
        List<Adr> adrs = repository.list();
        if (status != null && !status.isBlank()) {
            String wanted = status.strip().toLowerCase(Locale.ROOT);
            adrs = adrs.stream().filter(a -> a.status().equals(wanted)).toList();
        }
        return jsonMapper.writeValueAsString(adrs);
    }

    @McpTool(
            name = "adr_read",
            title = "Read an architecture decision record",
            description = "Returns the full Markdown of one ADR by its number (e.g. '15' or '0015'). Read-only.",
            annotations = @McpTool.McpAnnotations(title = "Read ADR", readOnlyHint = true,
                    destructiveHint = false, idempotentHint = true, openWorldHint = false))
    public CallToolResult adrRead(
            @McpToolParam(required = true, description = "ADR number, e.g. '0015'") String id) {
        return ToolResults.run("adr_read", () -> read(id));
    }

    String read(String id) {
        if (id == null || !id.strip().matches("(?i)(?:ADR\\s*[-#]?\\s*)?\\d{1,4}")) {
            throw new IllegalArgumentException("id must be an ADR number such as '0015', got " + id);
        }
        String digits = id.strip().replaceAll("\\D", "");
        return repository.read(digits)
                .orElseThrow(() -> new IllegalArgumentException("ADR " + MadrParser.normalizeId(digits) + " not found"));
    }
}
