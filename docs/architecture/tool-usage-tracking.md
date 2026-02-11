# Tool Usage Tracking Architecture

**Status**: Implemented (Phase 29)  
**Created**: 2026-02-01

## Goal

Track Cortex MCP tool usage to collect real-world statistics. Use this data to optimize the number of published tools by identifying unused or rarely-used tools that can be deprecated, consolidated, or removed.

## Design Principles

- **Non-Intrusive**: Tracking does not affect tool performance or behavior.
- **Privacy-Conscious**: Parameters are anonymized (hash only); no PII stored.
- **Low Overhead**: Minimal performance impact (target &lt; 1 ms per tool call).
- **Configurable**: Users can disable tracking or configure retention via `.cortex/config/usage_tracking.json`.
- **Backward Compatible**: Existing tools work without modification.

## Data Model (Pydantic)

- **ToolUsageEvent**: Single event (tool_name, timestamp ISO 8601, duration_ms, success, error_type, params_hash).
- **ToolUsageStats**: Aggregated stats (tool_name, total_calls, successful_calls, failed_calls, avg_duration_ms, min/max_duration_ms, error_types dict, first_used, last_used).

All structured data uses Pydantic `BaseModel` (no TypedDict).

## Storage

- **Events**: `.cortex/.cache/usage/events/YYYY-MM-DD.json` — one JSON file per day; append-only events array.
- **Aggregated**: `.cortex/.cache/usage/aggregated/daily/`, `weekly/`, `monthly/` for summaries.
- **Index**: `.cortex/.cache/usage/index.json` — metadata about stored data and last aggregation.

Paths are resolved via `get_cache_path(project_root, "usage")` from `cortex.core.path_resolver`.

### Querying Usage JSON with jq (Step 11)

Power users can inspect raw usage events directly from the JSON files for ad-hoc analysis or dashboards without adding an HTTP API.

- **Directory**: `.cortex/.cache/usage/events/`
- **Format**: Each `YYYY-MM-DD.json` file is a JSON array of `ToolUsageEvent` objects.

Examples:

- List all tool names used on a specific day:

```bash
jq '.[].tool_name' .cortex/.cache/usage/events/2026-02-11.json | sort -u
```

- Show failures with error types for a date range:

```bash
for f in .cortex/.cache/usage/events/2026-02-*.json; do
  jq '.[] | select(.success == false) | {timestamp, tool_name, error_type}' \"$f\"
done
```

- Filter events for a single tool and pretty-print:

```bash
jq '.[] | select(.tool_name == \"manage_file\")' \
  .cortex/.cache/usage/events/2026-02-11.json
```

These examples operate on the same underlying data that powers the `search_usage`, `get_usage_events`, and `get_usage_timeline` MCP tools, but give you full control over post-processing via jq or shell scripts.

## Anonymization

- Parameters are not stored; only an optional `params_hash` (hash of sorted keys + value types) for deduplication.
- No file paths, content, or user-identifiable data in events.

## Retention

- Default: 90 days of detailed events; 1 year of aggregated data.
- Configurable via `retention_days` in `usage_tracking.json`.
- Cleanup job removes older event files; aggregation runs on demand or periodically.

## Integration

1. **UsageTracker** manager: Created by manager initialization; lazy-loaded like other managers.
2. **Recording**: `with_mcp_stability` (in `mcp_stability.py`) records usage after each tool run. It obtains the current managers from a contextvar set by `get_managers()` so that no extra `get_managers` call is needed in the hot path.
3. **Analytics**: MCP tools `get_tool_usage_stats`, `get_unused_tools`, `get_tool_usage_report`, `get_optimization_recommendations` in `cortex.tools.usage_analytics` query the UsageTracker.

## Configuration

- **File**: `.cortex/config/usage_tracking.json`
- **Options**: `enabled`, `anonymize_params`, `retention_days`, `aggregation_enabled`, `opt_out_tools`, `min_duration_ms`.
- **Default**: Tracking enabled; 90-day retention; anonymization on.

## Performance

- Recording is async and non-blocking; failures in recording do not affect tool results.
- Target overhead: &lt; 1 ms per tool call.
