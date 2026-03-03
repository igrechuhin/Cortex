# Derived-state and history directories

This document captures the current, explicit contract for Cortex’s derived-state
and history-like directories. It is the implementation artifact for the
“Cleanup Cortex derived-state directories” plan and should be treated as the
single source of truth for which directories are durable, which are caches, and
which are safe to delete.

## Directory decision matrix

| Directory | Purpose / current usage | Consumers | Safe to delete? | Recommended action |
| --- | --- | --- | --- | --- |
| `.cortex/.cache/sessions` | Ephemeral multi-agent session registry used for coordination and observability between agents. Backed by `read_cache_json` / `write_cache_json` with the `sessions/active.json` key. | MCP session tools (`session(operation="start")` surface it in the brief), session registry helpers. | Yes. The registry file is recreated on demand; deleting it only loses current-session visibility and does not break core Cortex MCP behavior. | **Keep** as an ephemeral cache. Document it as safe to clear and not required for core correctness. |
| `.cortex/.cache/usage` | Usage analytics and optimization data written by `UsageTracker` and read by usage/optimization tools. Stores per-project usage events and aggregated summaries. | `query_usage` MCP tool family and usage analytics scripts; docs under `docs/architecture/tool-usage-tracking.md`. | Yes. The directory is recreated and new events are recorded; deleting it discards historical analytics only. | **Keep** as an optional analytics cache. Document that it is safe to delete and not required for core behavior. |
| `.cortex/.cache/.cache` | Legacy or accidental double-nested cache path with no active producers/consumers in the codebase. | None identified in current code search; not referenced by MCP tools. | Yes. No in-tree tools depend on it; any out-of-tree scripts should be migrated to the unified cache layout. | **Retire** by removing remaining filesystem artifacts over time and avoiding new references. Consolidate on the primary `.cortex/.cache` / `get_cache_dir` layout. |
| `.cortex/history` | Memory Bank version snapshots and rollback points that go beyond what git stores (e.g. structured snapshots for migration and rollback helpers). | Version-management tools (`MigrationManager`, version manager APIs), foundation and migration tests that exercise snapshot/rollback behavior. | No. Deletion discards rollback history and snapshot content, even though tools can tolerate a missing directory. | **Keep** as a durable history surface with documented purpose and retention policy. Future work may simplify layout but should not retire it wholesale. |
| `.cortex/rules` | Project-local rules root used by the `rules()` MCP tool when local `.mdc` rule files are present. Complements shared rules under `.cortex/synapse/rules`. | `rules()` MCP tool, rule indexing and validation tests. | Partially. The folder itself is part of the supported structure and should exist; individual rule files can be added, migrated, or removed. | **Keep** as the project-local rules folder. Use it for overrides and project-specific rules; avoid introducing additional ad-hoc rule directories. |
| `.cortex/script-capture` | Local directory used for storing captured scripts and related metadata for debugging and analysis. The canonical script implementations live in `.cortex/synapse/scripts`. | Script capture/storage utilities and their tests. | Yes. The directory is recreated on demand; deleting it removes only capture history, not core behavior. | **Treat as diagnostic/optional**. It is safe to delete during cleanup; longer term, consolidate capture workflows so scripts and their promotion paths live under `.cortex/synapse/scripts`. |
| `.cortex/benchmark_results` | Historical benchmark reports and JSON outputs produced by the benchmark framework and `run_benchmarks.py`, referenced from roadmap/progress entries and docs. No production code paths depend on these files. | Documentation and manual review of past benchmark runs. | Yes. It is safe to move or delete after capturing any important reports in docs. | **Consolidate** useful reports under a dedicated `docs/benchmarks` (or similar) area while treating `.cortex/benchmark_results` as a derived diagnostics surface that can be cleared. |

## Target layout and cleanup rules

1. **Durable history**
   - `.cortex/history` remains the durable Memory Bank history surface.
   - Do not treat it as a cache; any cleanup or rotation must respect migration
     and rollback needs.

2. **Ephemeral caches**
   - `.cortex/.cache/sessions` and `.cortex/.cache/usage` are **ephemeral
     caches**:
     - They are safe to delete; the next run of the relevant tools will
       recreate needed files.
     - They must never be the only place where user-visible or irreversible
       state is stored.
   - `.cortex/.cache/.cache` is considered **retired**:
     - New tools must not read from or write to this path.
     - Any remaining artifacts can be cleaned up as part of repository hygiene
       or migration scripts.

3. **Rules**
   - `.cortex/synapse/rules` is the canonical shared rules location for Cortex
     MCP.
   - `.cortex/rules` is the project-local rules root:
     - Use it for project-specific overrides and additional rules.
     - Do not introduce other ad-hoc rule directories for new work.

4. **Script capture**
   - `.cortex/script-capture` is an **opt-in diagnostic surface**:
     - It is safe to delete during derived-state cleanup.
     - Consumers must tolerate missing directories and empty histories.
   - Canonical scripts and promoted helpers continue to live under
     `.cortex/synapse/scripts`.

5. **Benchmarks**
   - New benchmark reports should live under a dedicated documentation area
     (for example `docs/benchmarks/`) rather than `benchmark_results` at the
     repo root.
   - Existing reports under `benchmark_results` can be migrated into docs and
     the directory removed once references are updated.

These rules are intentionally conservative: when in doubt, treat a directory as
durable history (like `.cortex/history`) rather than a cache, and prefer
explicit documentation plus tests before retiring or consolidating it.
