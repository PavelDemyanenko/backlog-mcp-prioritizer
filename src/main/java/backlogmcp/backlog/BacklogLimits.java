package backlogmcp.backlog;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/** {@code limit} handling shared by all {@code *_query_backlog} tools (spec §8.2: default 20). */
public final class BacklogLimits {

    private static final Logger log = LoggerFactory.getLogger(BacklogLimits.class);

    public static final int DEFAULT_LIMIT = 20;

    private BacklogLimits() {
    }

    /** null → default (capped), &lt;1 → error, &gt;max → max. */
    public static int resolve(Integer limit, int maxLimit) {
        if (limit == null) {
            return Math.min(DEFAULT_LIMIT, maxLimit);
        }
        if (limit < 1) {
            throw new IllegalArgumentException("limit must be >= 1, got " + limit);
        }
        if (limit > maxLimit) {
            log.info("limit {} capped to {}", limit, maxLimit);
            return maxLimit;
        }
        return limit;
    }
}
