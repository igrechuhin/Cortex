### Title

Cleanup Cortex derived-state directories

### Status

PENDING

### Goal

Ensure each of the following directories is either clearly justified (owner, purpose, retention policy) or safely removed/consolidated:

- `.cortex/.cache/sessions`
- `.cortex/.cache/usage`
- `.cortex/.cache/.cache`
- `.cortex/history`
- `.cortex/rules`
- `.cortex/script-capture`
- `benchmark_results`

### Context

The current tree contains multiple “derived state” and history-like directories alongside git history. It is unclear which are essential for Cortex MCP itself (session handoff, optimization, rules, script capture, usage statistics) versus legacy or redundant artifacts. This ambiguity makes the repo feel noisy and increases cognitive load for maintenance.

A roadmap item already exists to evaluate `.cortex/history` versus git history; this plan broadens the scope to all related directories so the cleanup is done coherently instead of piecemeal.

### Approach

1. Treat each directory as a unit of behavior (who writes it, who reads it, and what guarantees it provides) rather than as raw files.
2. For each directory, decide between three outcomes:
   - **Keep and document**: clearly record purpose, owners, and retention policy.
   - **Keep but consolidate**: merge with an existing mechanism (e.g., unify caches, move benchmarks under a single performance/metrics area).
   - **Retire**: remove code that writes to it, migrate any needed data, and delete the directory from the repo.
3. Drive all changes through Cortex MCP tools (`get_structure_info`, `manage_file`, `query_usage`, `query_memory_bank`, `execute_pre_commit_checks`) so the cleanup respects existing rules, memory bank workflows, and commit pipeline constraints.

### Implementation Steps

1. **Inventory producers and consumers**
   1. Use `get_structure_info` and code search to identify all tools, prompts, and scripts that read from or write to:
      - `.cortex/.cache/sessions`
      - `.cortex/.cache/usage`
      - `.cortex/.cache/.cache`
      - `.cortex/history`
      - `.cortex/rules`
      - `.cortex/script-capture`
      - `benchmark_results`
   2. For each directory, document:
      - Which MCP tools or scripts depend on it.
      - Whether it is required at runtime vs. purely diagnostic/optional.
      - Whether contents are safe to regenerate.

#### Step 1 inventory snapshot (2026-03-03)

- **`.cortex/.cache/sessions`**
  - **Producers/consumers**: `src/cortex/tools/session/registry.py` uses `read_cache_json` / `write_cache_json` with key `sessions/active.json` to maintain the multi-agent session registry. MCP tools such as `session_register`, `session_deregister`, and `session_list` operate on this registry; `session()` with `operation="start"` surfaces its contents in the session brief.
  - **Runtime vs. diagnostic**: Ephemeral registry used for coordination and observability between agents; not required for correctness of core Cortex MCP behavior.
  - **Regeneration safety**: Safe to delete; the next call to `session_register` recreates `active.json` from scratch. Deleting it only loses current-session visibility.

- **`.cortex/.cache/usage`**
  - **Producers/consumers**: `src/cortex/managers/usage_tracker.py` (`UsageTracker`) resolves `CacheType.USAGE` via `get_cache_dir` and writes usage events under a per-project cache root; MCP tools in `src/cortex/tools/usage/usage_analytics.py` (and the consolidated `query_usage` tool) read from this directory to answer usage queries and optimization reports. Docs in `docs/architecture/tool-usage-tracking.md` describe the on-disk layout (`events/`, aggregated summaries, `index.json`).
  - **Runtime vs. diagnostic**: Pure analytics/observability; not required for correctness of tool execution, but used for optimization and analysis.
  - **Regeneration safety**: Deleting the directory discards historical analytics but does not break the server; new usage data will be written to a fresh `.cortex/.cache/usage` tree when tracking is enabled.

- **`.cortex/.cache/.cache`**
  - **Producers/consumers**: Current code search found no producers or readers beyond this plan and related documentation; no Python modules reference `.cortex/.cache/.cache` directly.
  - **Runtime vs. diagnostic**: Appears to be an accidental or legacy double-nested cache path rather than an intentional behavior surface.
  - **Regeneration safety**: Candidate for consolidation/retirement in favor of the unified `.cortex/.cache` / `get_cache_dir` layout, after confirming no out-of-tree scripts depend on it.

- **`.cortex/history`**
  - **Producers/consumers**: `src/cortex/core/version_manager.py` uses `get_cortex_path(project_root, CortexResourceType.HISTORY)` for version snapshots; `src/cortex/tools/memory/foundation_stats.py` reads from the same directory to report disk usage; tests such as `tests/unit/test_version_manager.py`, `tests/unit/test_migration.py`, and `tests/tools/test_phase1_foundation.py` exercise creation, rollback, and snapshot paths under `.cortex/history`.
  - **Runtime vs. diagnostic**: Stores Memory Bank version snapshots and rollback points that are not represented in git history; used by version-management tools and migration/rollback flows.
  - **Regeneration safety**: Not a pure cache—deletion removes rollback history and snapshot content. `MigrationManager` tests show rollback handling when history is missing, but any cleanup must be coordinated with versioning/rollback requirements before retiring or restructuring it.

- **`.cortex/rules`**
  - **Producers/consumers**: Optimization config and rules tooling treat `.cortex/rules` as the local rules root (see `tests/tools/test_rules_operations.py`, which expects `get_rules_folder()` to return `.cortex/rules` and integration tests that skip when the folder or `.mdc` files are absent). The `rules()` MCP tool reports `.cortex/rules` as its `rules_folder` in status even though the current repo has `indexed_files=0`, implying no local rule files yet.
  - **Runtime vs. diagnostic**: Intended as the project-local rules directory complementing Synapse rules; used by `rules()` for commit/analysis guidance when populated.
  - **Regeneration safety**: The folder itself is part of the supported structure and should be kept. Individual contents can be added/migrated or removed, but wholesale deletion would prevent local rule overrides until recreated.

- **`.cortex/script-capture`**
  - **Producers/consumers**: `src/cortex/script_detection/storage.py` (`ensure_capture_dir`, `save_capture`, `list_captures`, `get_capture_by_id`, `ScriptCaptureStore`) writes JSON records under `.cortex/script-capture/` and reads them back; `tests/unit/test_script_detection_storage.py` and `tests/unit/test_path_resolver.py` verify path resolution and basic storage behavior.
  - **Runtime vs. diagnostic**: Diagnostic/forensics surface for captured scripts; used for debugging and analysis rather than core MCP operation.
  - **Regeneration safety**: Directory is recreated on demand; deleting it removes existing capture history but does not break script detection storage as long as callers tolerate missing histories.

- **`benchmark_results`**
  - **Producers/consumers**: Referenced from historical progress/roadmap entries and docs as the location for Phase 9 quality reports (e.g. `benchmark_results/phase-9-quality-report.md`). Current code search shows no active Python modules that write to or read from this directory; usage is primarily via documentation links.
  - **Runtime vs. diagnostic**: Purely diagnostic/reporting artifacts for past benchmark runs.
  - **Regeneration safety**: Safe to move or consolidate into a dedicated benchmarks/docs area; deleting it would only remove historical reports referenced from `.cortex/history` and roadmap entries.

1. **Clarify unique value vs. redundancy**
   1. For `.cortex/history`, compare its capabilities to git history:
      - What information is stored only in `.cortex/history` (e.g., session-level optimization reports, handoff details, non-committed work)?
      - Which existing workflows (analyze, commit, plan, session handoff) depend on it?
   2. For cache directories, determine:
      - How `.cortex/synapse/.cache` is used as the shared cache between projects, and which parts of it are required vs. optional.
      - Whether any remaining `.cortex/.cache/*` usage (including double-nesting like `.cortex/.cache/.cache`) is intentional or legacy that should be migrated to `.cortex/synapse/.cache` or removed.
   3. For `.cortex/synapse/rules`, confirm that it is treated as the canonical source of rules for the Cortex MCP server, and identify any legacy or duplicate rule locations (for example `.cortex/rules`) that should be migrated or retired.
   4. For `.cortex/script-capture` (captured scripts, not the canonical script implementations, which live in `.cortex/synapse/scripts`), identify when and how script capture is used (e.g., debugging generated scripts, compliance) and whether retention bounds exist.
   5. For `benchmark_results`, determine whether these artifacts are still used (e.g., current benchmarking workflow) and if they should live in a dedicated performance/benchmarks area or be converted to documentation.

2. **Decision matrix and target state**
   1. Build a small decision matrix table per directory capturing:
      - Purpose and current usage.
      - Consumers (tools, prompts, tests).
      - Safety of deletion (what would break).
      - Recommended action: **Keep**, **Consolidate**, or **Retire**.
   2. Propose a target layout, e.g.:
      - Keep `.cortex/synapse/rules` as the canonical rules location, with clear documentation, and migrate or remove any legacy `.cortex/rules` content.
      - Keep `.cortex/synapse/.cache` as the primary shared cache with well-defined subfolders and retention rules; migrate or remove any remaining `.cortex/.cache` usage (including redundant `.cache/.cache` nesting) if it is accidental or redundant.
      - Either keep `.cortex/history` with a clearly documented reason (session optimization, handoff, non-git data) or replace it with a lighter-weight mechanism, ensuring no loss of safety/rollback guarantees.
      - Decide whether `benchmark_results` stays in-repo, moves under docs, or is replaced by external dashboards.
      - Decide whether `.cortex/script-capture` should be opt-in and/or trimmed regularly, given that canonical scripts live in `.cortex/synapse/scripts`.

3. **Implement code and configuration changes**
   1. Update Cortex MCP tools, scripts, and prompts to match the target layout:
      - Remove or gate any writes to directories marked **Retire**.
      - Consolidate cache writers under a single `.cortex/.cache` layout.
      - Ensure tools that rely on `.cortex/history` either:
        - Use the new, minimal structure; or
        - Use git and memory bank artifacts instead, if `.cortex/history` is retired.
      - Audit `.cortex/index.json` for references to removed or migrated directories and legacy records, and either clean it in place or regenerate it from the current source of truth so it only indexes structures that actually exist.
   2. Use `manage_file` for all memory-bank-related updates (activeContext, progress, roadmap) and avoid direct edits to memory-bank paths.
   3. Update any hardcoded paths in prompts/scripts to use `get_structure_info` or configuration instead of literals.

4. **Documentation and rules updates**
   1. Update `AGENTS.md`, `CLAUDE.md`, and relevant docs under `docs/` to:
      - Describe the final set of “long-lived” directories and their purposes.
      - Clarify which directories are ephemeral (caches) vs. durable (rules, memory bank, selected history).
      - Document retention/cleanup expectations (e.g., caches safe to delete, benchmark results rotation).
   2. Update rules in `.cortex/rules` (via Cortex MCP rules tooling) so:
      - New prompts/tools do not reintroduce deprecated directories.
      - Script-capture and benchmark outputs, if kept, are used consistently and do not bloat the repo.

5. **Testing and validation**
   1. Run `execute_pre_commit_checks` (Phase A and Phase B) to ensure:
      - Formatting, linting, types, and tests all pass.
      - Roadmap, memory bank, and timestamps remain valid.
   2. Add or extend tests to cover:
      - Tools that previously wrote to or read from the affected directories.
      - Behavior when caches or history directories are missing or cleaned.
   3. Manually verify:
      - End-to-end flows that used `.cortex/history` (e.g., analyze, commit, plan, session handoff) still work as expected.
      - Caches can still be safely removed by users without breaking the MCP server.

### Risks and Mitigations

- **Risk**: Removing or restructuring a directory breaks hidden dependencies.
  - **Mitigation**: Use `query_usage` and tests to identify tool usage; stage changes behind feature flags where appropriate; make changes incrementally.
- **Risk**: Losing valuable diagnostic/benchmark history.
  - **Mitigation**: Before deleting, snapshot key artifacts into docs or an archived location; ensure important performance history is captured in markdown or external tooling.
- **Risk**: Confusion during transition.
  - **Mitigation**: Update documentation and rules in lockstep with code changes; add temporary warnings or logs when deprecated directories are accessed.

### Testing Strategy

- **Coverage target**: At least 95% coverage for any new modules or functions introduced to manage cache/history layout or directory discovery.
- **Unit tests**:
  - For helper functions that compute paths, classify directories, or handle migration decisions.
  - For any new configuration or flags controlling cache/history behavior.
- **Integration tests**:
  - For workflows that previously relied on `.cortex/history`, `.cortex/.cache/*`, `.cortex/rules`, `.cortex/script-capture`, and `benchmark_results`, ensuring they still work with the new layout.
- **Edge cases**:
  - Running Cortex MCP with some or all caches missing.
  - First-run scenarios where directories do not yet exist.
  - Migration from an older layout where deprecated directories are present.
- **Regression tests**:
  - Ensure commit, plan, and analyze flows behave identically before and after cleanup, aside from the intended directory layout changes.
