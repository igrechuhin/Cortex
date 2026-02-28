# Synapse Usage Storage with usage_writable and Static Snapshot Mode

**Status**: PENDING
**Created**: 2026-02-27

## Goal

Store tool usage statistics in Synapse (instead of project-local `.cortex/.cache/usage/`) when a Synapse fork explicitly opts in via `usage_writable: true`. When `usage_writable` is `false` or omitted, Cortex operates as a **static snapshot**: it does not populate or write any statistics for tools, prompts, or resources. This enables self-evolving Synapse forks to collect usage data for their own optimization while other forks remain read-only.

## Context

- **Current state**: Usage data is stored project-locally in `.cortex/.cache/usage/`; this data is only meaningful within the Cortex project and is not visible to Synapse maintainers or other consumer projects.
- **User intent**: For the Synapse fork at `https://github.com/igrechuhin/Synapse.git`, `usage_writable` will be `true`; other forks can keep it `false` or enable it for their own self-evolving forks.
- **Static snapshot**: When `usage_writable: false`, Cortex must not populate statistics for tools, prompts, or resources—i.e., no writes to usage events, context statistics, or aggregation.

## Design Principles

- **Opt-in**: Usage writes only occur when `usage_writable: true` in Synapse config.
- **Static snapshot by default**: When `usage_writable: false` or config missing, no statistics writes; read-only behavior.
- **Synapse-local config**: Config lives in Synapse (per-fork); each fork controls its own flag.
- **Backward compatible**: Project-local storage remains supported when Synapse is not used or `usage_writable: false`.

## Technical Design

### 1. Synapse Config and `usage_writable`

- **Location**: `.cortex/synapse/config.json` (or equivalent Synapse config file within the submodule).
- **Schema**: `{ "usage_writable": true | false }` (default: `false` when missing or invalid).
- **Resolution**: Cortex reads Synapse config via project root + Synapse path; if Synapse submodule not present, treat as `usage_writable: false`.

### 2. Storage Location When `usage_writable: true`

- **Path**: Synapse-relative, e.g. `.cortex/synapse/.cache/usage/`.
- **Committed**: Usage data is **committed** to Synapse (not gitignored). This enables cross-project aggregation: when consumer projects push their Synapse submodule, usage flows into the Synapse fork.
- **Structure**: Same as current—events in `events/YYYY-MM-DD.json`, aggregated in `aggregated/daily|weekly|monthly/`, index in `index.json`.
- **Path resolver**: Add support for "usage storage root"—Synapse `.cortex/synapse/.cache` when `usage_writable: true`.

### 2b. Cross-Project Aggregation (Committed Usage)

- **Flow**: Consumer projects using Cortex + your Synapse fork (with `usage_writable: true`) write usage to their Synapse submodule's `.cache/usage/`. When they commit and push the submodule, usage data flows into the Synapse repo.
- **Aggregation**: The Synapse fork receives usage from all projects that use it and push. Optimization decisions can be made from aggregated data.
- **Trade-offs**: Higher commit volume; possible merge conflicts if multiple projects push usage concurrently (events are append-only per day, so conflicts are localized and mergeable).

### 3. Static Snapshot Mode (`usage_writable: false`)

When `usage_writable` is `false` or absent:

- **Tool usage**: Do NOT call `_persist_event`; `UsageTracker.record_tool_usage` returns early without writing.
- **Context usage statistics**: Do NOT call `save_statistics` / `_update_global_stats`; context analysis returns results but does not persist new entries.
- **Aggregation**: Do NOT run aggregation that writes to disk (or run in-memory only for read-only queries if applicable).
- **Resources**: Do NOT persist resource usage events.
- **Prompts**: No prompt usage writes (if any exist).
- **query_usage / get_tool_usage_stats**: May still read from project-local cache if present (backward compat), but return empty/static data when no writes have occurred.

### 4. Affected Components

| Component | Change |
|-----------|--------|
| `UsageTracker.record_tool_usage` | Gate: if not usage_writable, return before `_persist_event` |
| `mcp_stability_finalize.record_usage_if_available` | Pass-through; tracker no-ops when usage_writable=false |
| `context_analysis_operations._update_global_stats` | Gate: if not usage_writable, skip `save_statistics` |
| `cache_json_access` / `_persist_event` | Resolve usage root from config (project vs Synapse) when writing |
| `path_resolver` / `cache_utils` | Support usage storage root override |
| Config loading | New: `load_synapse_usage_config(project_root) -> { usage_writable: bool }` |

### 5. Config Loading Contract

```python
# Pseudocode
def is_usage_writable(project_root: Path) -> bool:
    config = load_synapse_usage_config(project_root)
    return config.get("usage_writable", False) is True
```

- Config file: `.cortex/synapse/config.json` (or `synapse.json` in Synapse root).
- Default: `false` if file missing, parse error, or key absent.

## Implementation Steps

1. **Add Synapse usage config loader**
   - Create `load_synapse_usage_config(project_root: Path) -> dict[str, object]` in a new module or extend existing config loader.
   - Read from `.cortex/synapse/config.json`; return `{"usage_writable": False}` on missing/error.
   - Add `is_usage_writable(project_root: Path) -> bool` helper.

2. **Define usage storage root resolution**
   - Extend `path_resolver` or `cache_utils` to support `get_usage_storage_root(project_root: Path) -> Path`.
   - When `usage_writable: true`: return `project_root / ".cortex" / "synapse" / ".cache"` (usage stored under Synapse; committed, not gitignored).
   - When `usage_writable: false`: gate writes at `record_tool_usage` and context stats—no path resolution needed.

3. **Gate UsageTracker.record_tool_usage**
   - At start of `record_tool_usage`, call `is_usage_writable(self._project_root)`; if False, return immediately without persisting.
   - No changes to event building or `_persist_event` call when True.

4. **Gate context usage statistics writes**
   - In `_update_global_stats` (or callers that call `save_statistics`), add check: if not `is_usage_writable(project_root)`, skip the write path (do not extend `stats.entries`, do not call `save_statistics`).
   - Ensure `get_context_statistics` and read paths still work (may return empty or previously loaded data).

5. **Wire usage storage root for writes when usage_writable=true**
   - Update `_persist_event` to use `get_usage_storage_root(project_root)` when `usage_writable` is true, so events go to Synapse `.cache/usage/`.
   - Update `read_cache_json` / `read_modify_write_cache_json` call sites for usage to pass the correct root (or add a `usage_project_root` parameter that can be Synapse cache dir).
   - Ensure `cache_json_access` can accept an alternate root for usage (e.g. `usage_storage_root` instead of `project_root` for the usage relative key).

6. **Do NOT gitignore usage in Synapse**
   - Ensure `.cache/usage/` (and subdirs) are **not** in Synapse `.gitignore`. Usage data is committed so it flows to the Synapse fork when consumers push.

7. **Update tool-usage-tracking architecture doc**
   - Document `usage_writable`, storage-in-Synapse, and static-snapshot behavior in `docs/architecture/tool-usage-tracking.md`.

8. **Resource and prompt usage (if any)**
   - Audit codebase for any resource or prompt usage recording; gate those writes with `is_usage_writable`.

9. **Cortex MCP startup sync (optional)**
   - Add a startup step so Cortex MCP fetches and updates the project repo on startup: `git fetch origin` and `git submodule update --init --recursive`.
   - Gated by `CORTEX_SYNC_ON_STARTUP=1` (opt-in).
   - Purpose: Reduce merge conflicts and ensure agents always work with the newest Synapse setup (submodule) and upstream changes.
   - Non-blocking: log and continue on failure so MCP always starts.
   - Use cwd as starting point, walk up to find git root.

## Dependencies

- Synapse submodule must exist for Synapse storage; when absent, `usage_writable` is effectively false.
- No external services; pure filesystem.

## Success Criteria

- When `usage_writable: true` in Synapse config: usage events and context stats are written to Synapse `.cache/usage/` and committed.
- When `usage_writable: false` or config missing: no usage events, no context stats updates; Cortex operates as static snapshot for statistics.
- Usage from consumer projects flows to the Synapse fork when they commit and push the submodule.
- User's Synapse fork (igrechuhin/Synapse) can set `usage_writable: true`; other forks default to `false`.

## Testing Strategy

- **Unit tests**: `is_usage_writable` returns False for missing config, invalid JSON, `usage_writable: false`; returns True for `usage_writable: true`.
- **Unit tests**: `UsageTracker.record_tool_usage` does not call `_persist_event` when `usage_writable: false`; mocks verify no write.
- **Unit tests**: Context stats `_update_global_stats` does not call `save_statistics` when `usage_writable: false`.
- **Integration tests**: End-to-end: start Cortex with `usage_writable: false`, invoke tools, verify no new files under `.cortex/.cache/usage/` or context stats path.
- **Integration tests**: With `usage_writable: true` and Synapse config, verify events appear under Synapse `.cache/usage/`.
- **Coverage target**: Minimum 95% for new config loader and gating logic.

## Risks & Mitigation

- **Commit volume**: Usage commits will increase Synapse repo history. Acceptable for optimization value; consider periodic aggregation/squash if it grows too large.
- **Merge conflicts**: Multiple projects pushing usage can cause conflicts on the same day file. Events are append-only; merge strategy: combine arrays. Document in architecture doc.
- **Config format evolution**: Use a minimal schema; document in architecture doc.

## Timeline

- Estimate: 1–2 sprints (medium complexity).
- Prerequisite: None.

## Notes

- "Static snapshot" means no population of statistics—Cortex does not add new data to tools/prompts/resources usage stores.
- The flag is intentionally named `usage_writable` to align with the concept of Synapse being writable for usage data only when opted in.
