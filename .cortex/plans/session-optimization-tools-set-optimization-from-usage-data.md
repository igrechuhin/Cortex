# Plan: Tool Consolidation — From 64 Tools to ~24

## Status: IN PROGRESS (Step 4 done 2026-02-24)

## Created: 2026-02-24

## Updated: 2026-02-24 (enriched with comprehensive audit)

## Source

- End-of-session analysis (session-optimization-2026-02-24T08-53.md)
- Full tool audit: 64 `@mcp.tool()` + 34 `@mcp.resource()` = 98 registered endpoints
- Usage data: 49,944 invocations across 82 public tools, 22 days of events

## Problem Statement

Cortex MCP registers **64 tools and 34 resources (98 total endpoints)**. Editors like Cursor impose a limit of ~80 tools across ALL MCPs — Cortex alone exceeds this budget before any other MCP server gets a slot.

Key issues identified:

1. **Phase 50 consolidation incomplete**: `query_memory_bank` and `query_usage` were created to replace scattered `get_*` tools, but old tools were never removed. The consolidation *added* tools instead of replacing them.
2. **Ghost tools**: 11+ tools are registered via `@mcp.tool()` but absent from `tool_categories.py` (the canonical registry). They fly under any governance.
3. **Resource/tool duplication**: 33 `*_resource` endpoints duplicate existing tools.
4. **Dead tools**: 11 tools have <5 invocations over 22 days.
5. **Redundant variants**: `write_file` duplicates `manage_file`; `update_config` duplicates `configure`; `load_progressive_context` is a variant of `load_context`.

## Goal

Reduce the published tool count from 64 to ~24 tools while preserving all functionality. Target: leave 56+ tool slots for other MCPs in editors with 80-tool limits.

## Constraints

- No functionality loss — every operation must remain accessible
- Backward-compatible migration path for prompts/instructions referencing old tool names
- All changes must pass existing tests
- `tool_categories.py` must remain the single source of truth

## Usage Data Summary (22 days, 49,944 total invocations)

### Pre-consolidation tools still alive (should have been removed by Phase 50)

| Old tool | Calls | Consolidated into |
|---|---|---|
| `get_memory_bank_stats` | 695 | `query_memory_bank(query_type="stats")` |
| `get_version_history` | 1,238 | `query_memory_bank(query_type="version_history")` |
| `get_link_graph` | 1,332 | `query_memory_bank(query_type="link_graph")` |
| `parse_file_links` | 1,304 | `query_memory_bank(query_type="parse_links")` |
| `validate_links` | 1,390 | `query_memory_bank(query_type="validate_links")` |
| `resolve_transclusions` | 1,584 | `query_memory_bank(query_type="transclusions")` |
| `get_dependency_graph` | 303 | `query_memory_bank(query_type="dependency_graph")` |
| `get_tool_usage_stats` | 264 | `query_usage(query_type="stats")` |
| `get_tool_usage_report` | 262 | `query_usage(query_type="report")` |
| `get_unused_tools` | 263 | `query_usage(query_type="unused")` |
| `get_optimization_recommendations` | 265 | `query_usage(query_type="recommendations")` |
| `get_usage_events` | 15 | `query_usage(query_type="events")` |
| `get_usage_timeline` | 27 | `query_usage(query_type="timeline")` |
| `get_usage_observation` | 22 | `query_usage(query_type="observation")` |
| `search_usage` | 21 | `query_usage(query_type="search")` |

### Dead tools (<5 calls)

| Tool | Calls | Recommendation |
|---|---|---|
| `list_plans` | 1 | Merge into `create_plan(operation="list")` |
| `get_plan` | 2 | Merge into `create_plan(operation="get")` |
| `session_register` | 2 | Make internal (not `@mcp.tool`) |
| `session_deregister` | 2 | Make internal (not `@mcp.tool`) |
| `list_active_tasks` | 2 | Make internal (not `@mcp.tool`) |
| `check_task_available_lock` | 2 | Make internal (not `@mcp.tool`) |
| `claim_task_lock` | 2 | Make internal (not `@mcp.tool`) |
| `release_task_lock` | 2 | Make internal (not `@mcp.tool`) |
| `remove_roadmap_entry` | 4 | Keep (needed for implement workflow) |
| `get_session_tool_anomalies` | 3 | Already removed per mapping doc |
| `run_tool_optimization_workflow` | 2 | Already removed per mapping doc |

### Duplicate tools

| Duplicate | Calls | Canonical tool |
|---|---|---|
| `write_file` | 260 | `manage_file(operation="write")` |
| `update_config` | 248 | `configure` |
| `load_progressive_context` | 1,166 | `load_context(strategy="progressive")` |

## Implementation Steps

### Step 1: Complete Phase 50 consolidation — remove old `get_*` tools ✅ COMPLETED 2026-02-24

Remove 15 pre-consolidation tools that `query_memory_bank` and `query_usage` already replace.

**Files to modify:**

- Remove `@mcp.tool()` registrations from: `phase1_foundation_stats.py`, `phase1_foundation_version.py`, `phase1_foundation_dependency.py`, `phase2_linking.py` (link_graph, parse_file_links, validate_links, resolve_transclusions), `usage_analytics.py` (all `get_*` usage tools)
- Keep the underlying functions as helpers (they're called by `query_memory_bank`/`query_usage` dispatch)
- Update `tool_categories.py`: remove entries for deleted tools
- Update `optimization.json`: remove from `tool_search.deferred_medium` and `deferred_low`
- Update `__init__.py` docstring tool count

**Prompt/instruction updates:**

- Search all `.cortex/synapse/prompts/*.md` and `.cortex/rules/*.md` for old tool names
- Replace with consolidated equivalents (e.g., `get_link_graph` → `query_memory_bank(query_type="link_graph")`)
- Update `CLAUDE.md` and `AGENTS.md` if they reference old tools
- Update `docs/api/tools.md`

Saves: ~15 tool slots

### Step 2: Remove duplicate tools ✅ COMPLETED 2026-02-24

Remove `write_file`, `update_config`, and `load_progressive_context`.

**Files to modify:**

- `file_crud_operations.py`: remove `write_file` tool registration (keep `manage_file`)
- `configuration_hybrid.py` or `configuration_operations.py`: remove `update_config` (keep `configure`)
- `phase4_optimization_handlers.py`: remove `load_progressive_context` (ensure `load_context` accepts `strategy="progressive"`)
- Update `tool_categories.py` and `optimization.json`

Saves: ~3 tool slots

### Step 3: Remove/internalize dead tools ✅ COMPLETED 2026-02-24

Convert 7 dead tools from public `@mcp.tool()` to internal functions:

- `session_register`, `session_deregister` → internal helpers in `session_registry.py`
- `list_active_tasks`, `check_task_available_lock`, `claim_task_lock`, `release_task_lock` → internal helpers in `task_locking.py` (keep for Phase 58 but not as public MCP tools)
- `list_plans`, `get_plan` → merge into `create_plan` as `operation` parameter

Saves: ~8 tool slots

### Step 4: Consolidate script capture tools (5 → 1) ✅ COMPLETED 2026-02-24

Merge `capture_session_script`, `list_session_scripts`, `analyze_session_scripts`, `suggest_tool_improvements`, `promote_session_script` into a single `session_scripts(operation=...)` tool following the Phase 50 pattern.

**Files to modify:**

- `script_capture_tools.py`: consolidate 5 tools into 1 dispatcher
- Update `tool_categories.py` and `optimization.json`

Saves: ~4 tool slots

### Step 5: Consolidate analytics tools

Merge `analyze_context_effectiveness` + `get_context_usage_statistics` into `analyze(analysis_type="context"|"context_stats")`.

Merge `analyze_health_check` into `analyze(analysis_type="health")`.

**Files to modify:**

- `context_analysis_handlers.py`: remove standalone registrations
- `health_check_operations.py`: remove standalone registration
- `analysis_operations.py`: add dispatch for new analysis types
- Update `tool_categories.py` and `optimization.json`

Saves: ~3 tool slots

### Step 6: Consolidate pre-commit pipeline (3 → 1)

Merge `run_preflight_checks` + `run_docs_and_memory_bank_sync` into `execute_pre_commit_checks(phase="A"|"B"|"full")`.

**Files to modify:**

- `pre_commit_phase_tools.py`: remove standalone registrations
- `pre_commit_tools.py`: add `phase` parameter to `execute_pre_commit_checks`
- Update `tool_categories.py` and `optimization.json`

Saves: ~2 tool slots

### Step 7: Audit and clean up resource registrations

Verify that `*_resource` endpoints are registered via `@mcp.resource()` (not `@mcp.tool()`). If any are registered as tools, convert them to resource-only. Resources should NOT count toward the tool limit in MCP clients.

**Files to audit:**

- All files with `@mcp.resource()` decorators (34 registrations)
- Verify they are not also registered as `@mcp.tool()`

Saves: 0 tool slots (validation) or up to 33 if any are double-registered

### Step 8: Update governance — make `tool_categories.py` authoritative

- Ensure every `@mcp.tool()` registration has a corresponding entry in `tool_categories.py`
- Add a startup assertion or test that validates: registered tools == categorized tools
- Update `optimization.json` to match `tool_categories.py` exactly (currently diverged)

### Step 9: Update documentation

- Update `docs/api/tools.md` to reflect final tool set
- Update `docs/architecture/tool-optimization-mapping.md` with decisions
- Update `CLAUDE.md` and `AGENTS.md` tool references
- Update all Synapse prompts referencing removed tools

### Step 10: Run tests and validate

- Run full test suite — all existing tests must pass
- Run `validate(check_type="roadmap_sync")` to verify roadmap integrity
- Run `execute_pre_commit_checks` to verify quality gates
- Verify tool count: `rg '@mcp\.tool\(' src/cortex/tools/ -c` should show ~24

## Expected Outcome

| Category | Before | After |
|---|---|---|
| Public tools (`@mcp.tool`) | 64 | ~24 |
| Resources (`@mcp.resource`) | 34 | 34 (unchanged) |
| Tool slots consumed | 64 | ~24 |
| Slots remaining for other MCPs (80 limit) | 16 | ~56 |

## Testing Strategy

- **Coverage target**: 95% for modified modules
- **Unit tests**: Verify consolidated dispatch tools route correctly to all operations
- **Integration tests**: Verify end-to-end workflows (implement, commit, plan-create) work with new tool names
- **Regression tests**: Ensure no existing test breaks from tool removal
- **Prompt validation**: Grep all prompts/rules for removed tool names — zero references
- **Startup validation**: Add test asserting `len(registered_tools) == len(tool_categories)`
- **AAA pattern**: All new tests follow Arrange-Act-Assert

## Risks and Mitigation

| Risk | Impact | Mitigation |
|---|---|---|
| Prompts reference old tool names | LLM calls fail | Comprehensive grep-and-replace in Step 1/9 |
| Tests import old tool functions | Test failures | Update imports; keep functions as non-tool helpers |
| Phase 58 needs task-locking tools | Future feature blocked | Keep as internal functions, re-expose when needed |
| `optimization.json` divergence | Stale config | Step 8 alignment + startup assertion |

## Dependencies

- None (self-contained within Cortex)

## References

- `docs/architecture/tool-optimization-mapping.md`
- `src/cortex/tools/tool_categories.py` (canonical registry)
- `src/cortex/tools/__init__.py` (import list)
- `.cortex/config/optimization.json` (runtime config)
- Usage data: `.cortex/.cache/usage/events/*.json`
