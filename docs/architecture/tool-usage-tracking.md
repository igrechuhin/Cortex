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

### Version control policy (superproject vs Synapse submodule)

**Should I commit today’s `YYYY-MM-DD.json` under usage events?** In the **Cortex superproject** (this repository), **no** — the root [`.gitignore`](../../.gitignore) contains a `.cache` rule that ignores `.cortex/.cache/` (and any other `.cache` directory). Treat project-local usage trees as **derived state**: they are recreated by the server when tracking is enabled; committing them upstream adds merge noise and is not the default workflow. In the **Synapse submodule** (`.cortex/synapse/`), Synapse’s own [`.gitignore`](../../.cortex/synapse/.gitignore) **allows** `.cache/usage/events/*.json` to be tracked so forks that opt into shared analytics can aggregate cross-project data. Commit those daily files **only** when your Synapse fork’s policy expects it and you intend to push rollup data — coordinate with submodule maintainers. For **`.cortex/.session/context-usage-statistics.json`**, the superproject `.gitignore` includes `.session`, so new files there are normally **untracked**; do not commit that JSON as part of routine Cortex contributions unless you are deliberately publishing anonymized effectiveness stats (legacy clones may still have the file tracked from before ignore rules).

### Synapse Usage Storage and Static Snapshot Mode

When a Synapse fork opts in via `usage_writable: true` in `.cortex/synapse/config.json`:

- **Storage location**: Usage events are written to `.cortex/synapse/.cache/usage/events/` (committed to Synapse for cross-project aggregation).
- **Config**: `{"usage_writable": true}` in `.cortex/synapse/config.json`.
- **Cross-project flow**: Consumer projects push usage into their Synapse submodule; the Synapse fork receives aggregated data.

When `usage_writable` is `false` or absent (default):

- **Static snapshot**: Cortex does not write any usage statistics (tools, context stats, prompts, resources). No population of usage stores.
- **Read-only**: `query_usage` and `get_tool_usage_stats` may still read from project-local cache if present (backward compat).

### Context usage statistics file (`context-usage-statistics.json`)

Load-context effectiveness aggregates persist at `.cortex/.session/context-usage-statistics.json` (see `get_statistics_path` in `effectiveness_operations_io.py`). That file is separate from tool-usage event JSON under `.cortex/.cache/usage/`.

#### File format and `schema_version`

The JSON object validates as `ContextUsageStatistics` (`effectiveness_models.py`). It includes optional top-level **`schema_version`** (default `1` when omitted on load). New writes include `schema_version` so operators can tell which document shape they hold; bump the default in code when fields change in a breaking way.

| Field / group | Meaning |
| --- | --- |
| `schema_version` | Format version; missing in older files is treated as `1`. |
| `last_updated` | ISO 8601 timestamp (minute resolution), updated when **new** session rows are merged into `entries` (e.g. `_update_global_stats`, `analyze_session_logs` after processing logs) — not on every read. |
| `total_sessions_analyzed` | Count of distinct sessions represented by rows in `entries` that have been incorporated into this aggregate (incremented when a new `session_id` is added). |
| `total_load_context_calls` | **Not** a lifetime count of every `load_context` invocation. It equals the number of **production-quality** rows in the optimization rollup (`record_quality == PRODUCTION`). Synthetic or excluded rows stay in `entries` but are omitted from this total and from averages. |
| `avg_*`, `common_task_patterns`, `insights` | Recomputed from the production rollup only (`_update_aggregates` → `_production_rollup_entries`). |
| `entries` | Full list of per-session/per-call rows (including non-production classifications). |

Aggregates are **not** a fixed time window (e.g. last 7 days); they always reflect the current contents of `entries` and the current classification rules. **Sudden drops** in `total_load_context_calls` or averages usually mean more rows were classified as non-production, reconciliation changed labels, or `entries` shrank — not necessarily fewer real users.

#### Reconcile on load

On each load, `load_statistics` may run `reconcile_context_usage_statistics_entries` to re-apply telemetry quality labels (`record_quality`, `telemetry_quality_note`) to existing rows and refresh rollups (production-only averages and insights). When reconciliation changes data, the updated statistics object is written back **only if** `is_usage_writable(project_root)` is true (same `usage_writable` flag in `.cortex/synapse/config.json` as for MCP tool usage).

Implications for operators:

- With **`usage_writable: true`**: reconciliation fixes persisted JSON when classification rules change (e.g., after upgrades).
- With **`usage_writable: false`**: reconciliation still runs **in memory** for the lifetime of the process that loaded the file (so MCP responses and tools see corrected aggregates for that session), but the file on disk is **not** rewritten. To persist fixes, set `usage_writable` to `true` temporarily or run a small in-repo script that loads and saves statistics with writes enabled (same guard as production code).

#### Context telemetry rollup exclusion metrics (optional)

When rows are excluded from optimization rollups (synthetic or invalid-data classifications), Cortex maintains in-process counters and structured logs. Operators may optionally push **debounced JSON snapshots** of those counters to an HTTP endpoint (for example a metrics gateway or log pipeline that accepts POST bodies):

- **`CORTEX_CONTEXT_TELEMETRY_EXCLUSION_METRICS_URL`**: If set (non-empty), after each rollup exclusion the server may `POST` a `ContextTelemetryExclusionCountersSnapshot` JSON document to this URL. Default unset (no export).
- **`CORTEX_CONTEXT_TELEMETRY_EXCLUSION_METRICS_EXPORT_INTERVAL_SEC`**: Minimum seconds between POSTs when the URL is set (default `10`). Use `0` to disable debouncing (each exclusion can trigger a POST; use only when the sink can handle the volume).
- **`CORTEX_CONTEXT_TELEMETRY_EXCLUSION_METRICS_AUTHORIZATION`**: Optional full `Authorization` header value (for example `Bearer <token>`). Omit when the endpoint does not require auth.

Exports are best-effort: failures are logged at DEBUG only and do not affect MCP behavior.

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

These examples operate on the same underlying data that powers the `query_usage` MCP tool (query_type: search, events, timeline), but give you full control over post-processing via jq or shell scripts.

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
3. **Analytics**: MCP tool `query_usage` (query_type: stats, unused, report, recommendations, search, events, observation, timeline) in `cortex.tools.query_usage_operations` queries the UsageTracker.

## Configuration

- **File**: `.cortex/config/usage_tracking.json`
- **Options**: `enabled`, `anonymize_params`, `retention_days`, `aggregation_enabled`, `opt_out_tools`, `min_duration_ms`.
- **Default**: Tracking enabled; 90-day retention; anonymization on.

## Performance

- Recording is async and non-blocking; failures in recording do not affect tool results.
- Target overhead: &lt; 1 ms per tool call.
