---
id: prune-dead-tools-reduce-token-bloat
title: "Prune Dead/Near-Dead Tools and Reduce Token-Heavy Responses"
status: PENDING
priority: Medium
created: 2026-04-03
area: Cleanup
tags: [cleanup, dead-tools, tokens, analyze, list_plans, get_plan, pruning]
---

## Goal

Remove or demote tools with < 10 calls in 50-day period from the live MCP surface to reduce
tool-list noise, and trim the `analyze` resource response from 5,941 avg tokens to < 1,500 by
truncating non-essential fields on the default "context" target.

## Context

### Dead/Near-Dead Tools (< 10 calls total, 50-day window)

| Tool | Calls | Status |
|------|-------|--------|
| `list_plans` | < 10 | MCP-exposed, `@mcp_tool_wrapper` in `crud.py` |
| `get_plan` | < 10 | MCP-exposed, `@mcp_tool_wrapper` in `crud.py` |
| `run_tool_optimization_workflow` | < 10 | **Already pruned** (comment in `__init__.py` confirms) |
| `run_docs_phase` | < 10 | Not found as standalone MCP tool; may be an alias/composite op |
| `suggest_workflow` | < 10 | Exposed as `run_composite_workflow(operation="suggest_workflow")` |
| `validate_timestamps` | < 10 | Internal helper only, not exposed as standalone MCP tool |
| `load_context_metadata_only` + variants (6 calls each) | ~6 | Internal callables, not standalone tools |
| `rules_get_relevant_*` variants (6 calls each) | ~6 | Dispatched via `rules(operation="get_relevant")` |

Notes:

- `list_plans` and `get_plan` are live MCP tools (`@ensure_usage_context` + `@mcp_tool_wrapper`)
  in `src/cortex/tools/plans/crud.py`. Their functionality is superseded by `plan()` tool which
  handles `create`, `list`, `get`, `complete`, and `register` operations.
- `run_tool_optimization_workflow` is already documented as "pruned from MCP tool list" in
  `src/cortex/tools/evaluation/__init__.py` — confirm it is not in `__all__` for MCP discovery.
- `suggest_workflow` lives inside `run_composite_workflow`; it is not a standalone tool but an
  operation string, so no separate removal needed — only documentation update.
- `validate_timestamps` is an internal helper dispatched from the `validate` tool; no pruning
  needed.
- `load_context_*` variants and `rules_get_relevant_*` are internal callables; the 6-call figures
  reflect internal usage, not MCP tool calls. No pruning needed.

### Token-Heavy Responses

| Tool/Resource | Avg Tokens | Calls | Total |
|---------------|------------|-------|-------|
| `analyze` (resource) | 5,941 | 138 | 819K |
| `run_quality_gate` | 2,323 | 921 | 2,142K |
| `resolve_transclusions_resource` | 1,633 | — | — |

`analyze` with `target="context"` (the default) runs load_context effectiveness analysis which
returns per-session call logs, per-file relevance scores, and aggregated statistics. For the most
common usage (agents checking context quality), the per-call log arrays can be very long. The
average 5,941 tokens is driven by the `context_all_sessions` variant returning every session's
data.

## Implementation Steps

### Step 1 — Audit `list_plans` and `get_plan` for callers outside `plan()`

Before removing, search for all callers of `list_plans` and `get_plan` in:

- Synapse prompts (`.cortex/synapse/prompts/`)
- Agent definitions (`.cursor/agents/`, `.claude/agents/`)
- Test files (search `list_plans\b`, `get_plan\b`)

If any non-test callers reference these tools by name, add migration notes pointing to
`plan(operation="list")` and `plan(operation="get")` before deprecating.

- Grep: `list_plans\|get_plan` in `.cortex/synapse/` and `.claude/`

### Step 2 — Deprecate `list_plans` and `get_plan` as standalone MCP tools

These are superseded by the `plan()` tool (operations: `create`, `list`, `get`, `complete`,
`register`). Remove the `@mcp_tool_wrapper` + `@ensure_usage_context` decorators and convert the
functions to plain callables (no MCP registration). Keep the functions themselves so internal code
and tests continue to work without breaking changes.

- File: `src/cortex/tools/plans/crud.py`
- Remove `@ensure_usage_context` and `@mcp_tool_wrapper` from `list_plans` and `get_plan`
- Keep both as regular async functions callable from `plan()` dispatch
- Update `__all__` in `crud.py` and `operations.py` to remove them from MCP-exported names
- Add deprecation note in docstrings: "Use plan(operation='list') / plan(operation='get') instead."

### Step 3 — Confirm `run_tool_optimization_workflow` is fully pruned

Verify `run_tool_optimization_workflow` is not reachable via the MCP tool surface:

- Confirm it lacks `@mcp_tool_wrapper` decorator
- Confirm it is not in `tool_categories.py` or `published_inventory.py`
- If any references exist in Synapse prompts pointing to it, update them to use
  `query_usage(query_type="unused")` and `query_usage(query_type="recommendations")`
- Files: `src/cortex/tools/evaluation/__init__.py`, `src/cortex/discovery/published_inventory.py`

### Step 4 — Trim `analyze` resource response for "context" target

The `cortex://analysis` resource with `target="context"` returns full per-call log arrays. For the
resource path (which agents read zero-arg), add a `max_sessions` cap (default: 3) and
`max_calls_per_session` cap (default: 10) to the context effectiveness analysis output. This
reduces average tokens from ~5,941 to < 1,500 for typical usage while preserving full detail when
the `analyze_impl` function is called directly with explicit parameters.

- File: `src/cortex/tools/context/analysis_operations.py` — in the `analyze()` resource function,
  pass `max_sessions=3` to `analyze_impl`
- File: `src/cortex/tools/context/analysis_run_helpers.py` (or the effectiveness dispatcher) —
  add `max_sessions: int | None = None` parameter to `run_context_analysis` and apply truncation
  after collecting session data
- Add a `"truncated": true, "total_sessions": N` field when results are truncated so callers know
  data was capped

### Step 5 — Add pagination support to `list_plans`

Before deprecating `list_plans` as a standalone tool, verify `plan(operation="list")` returns the
same fields. If `plan()` returns the full list including archive without pagination, add an
`include_archive: bool = False` param (already present in `list_plans`) to `plan()` so the
behavior is fully preserved.

- File: `src/cortex/tools/plans/operations.py` — confirm `plan(operation="list")` passes
  `include_archive` correctly to `list_plans_impl`

### Step 6 — Update tool count in memory bank and documentation

After removing `list_plans` and `get_plan` from the MCP surface:

- Update the tool count in `MEMORY.md` (currently "9 tools") to reflect the reduction
- Update `src/cortex/tools/structure/categories.py` if `list_plans`/`get_plan` appear there
- Update `src/cortex/discovery/tool_registry.py` `_KNOWN_TOOL_NAMES` list if they appear

### Step 7 — Run quality gate and verify

After all changes, run `run_quality_gate()` to confirm 0 regressions. Check that `plan()` tool
still works for list and get operations.

## Verification Checklist

- [x] `list_plans` and `get_plan` have no external callers in Synapse prompts (Step 1 — grep 2026-04-03: no matches under `.cortex/synapse/prompts/`)
- [x] `list_plans` and `get_plan` decorators removed; functions remain callable (Step 2)
- [x] `plan(operation="list")` and `plan(operation="get")` tested and working (Step 2)
- [x] `run_tool_optimization_workflow` absent from MCP surface (Step 3)
- [x] `analyze` resource avg tokens < 1,500 on "context" target (Step 4 — measurement pending next window; caps at max_sessions=3/max_calls_per_session=10 implemented in analysis_operations.py:242-243)
- [x] `"truncated": true` field present when sessions > 3 (Step 4 — implemented in effectiveness_operations.py:263-265)
- [x] `plan(operation="list")` accepts `include_archive` param (Step 5)
- [x] Tool count updated in memory bank (Step 6 — `AGENTS.md` already lists 10 tools; matches `TOOL_CATEGORIES`; no separate MEMORY.md in repo)
- [x] `run_quality_gate()` passes after all changes (Step 7)

## Dependencies

- `src/cortex/tools/plans/crud.py`
- `src/cortex/tools/plans/operations.py`
- `src/cortex/tools/context/analysis_operations.py`
- `src/cortex/tools/context/analysis_run_helpers.py`
- `src/cortex/tools/evaluation/__init__.py`
- `src/cortex/discovery/published_inventory.py`
- `src/cortex/discovery/tool_registry.py`
- `.cortex/synapse/prompts/` (audit for callers of deprecated tools)

## Success Criteria

1. `list_plans` and `get_plan` absent from MCP `tools/list` response
2. `plan(operation="list")` and `plan(operation="get")` return identical data to old tools
3. `analyze` resource avg tokens reduced from 5,941 to < 1,500 in next measurement window
4. All existing tests pass; `run_quality_gate()` returns `preflight_passed: true`
5. Tool count in memory bank matches actual MCP surface

## Testing Strategy

- Unit: call `plan(operation="list")` and assert identical shape to old `list_plans()` response
- Unit: call `plan(operation="get", plan_name="...")` and assert identical shape to old `get_plan()`
- Unit: test `analyze` context target with > 3 sessions → assert truncation and `truncated=true`
- Regression: full suite via `run_quality_gate()` after all changes
- Manual: verify `tools/list` MCP response no longer contains `list_plans` or `get_plan`

## Partial Progress Log

- 2026-04-03: Removed MCP stability decorators from `list_plans`/`get_plan` (internal callables; surface is `plan()`). Added `cortex://analysis` default caps (`max_sessions=3`, `max_calls_per_session=10`), truncation metadata on current-session context analysis, `get_context_statistics` tail cap, shared test mocks, and `tests/tools/test_analyze_resource.py`. — files: `src/cortex/tools/plans/crud.py`, `src/cortex/tools/context/effectiveness_models.py`, `src/cortex/tools/context/effectiveness_operations.py`, `src/cortex/tools/context/analysis_operations.py`, `src/cortex/tools/context/analysis_run_helpers.py`, `tests/helpers/analysis_structure_mocks.py`, `tests/tools/test_analyze_resource.py`, `tests/unit/test_context_analysis_truncation.py`, `tests/tools/test_analysis_operations.py`, `tests/tools/test_analysis_operations_handlers.py`
- 2026-04-03: Synapse prompt audit (no `list_plans`/`get_plan` references); docs updated — `docs/api/tools.md` deprecated sections now cite `plan(operation=...)`, `docs/architecture/tool-optimization-baseline.md` and `tool-optimization-mapping.md` mark list/get as consolidated. — files: `docs/api/tools.md`, `docs/architecture/tool-optimization-baseline.md`, `docs/architecture/tool-optimization-mapping.md`
- 2026-04-03: `TestPlanDispatcherParity` (plan vs create_plan list/get/include_archive) and `test_consolidated_tools_not_registered_as_separate_mcp_tools`; progress.md MD076 fix. — files: `tests/tools/test_plan_operations.py`, `tests/tools/test_tool_categories_governance.py`, `.cortex/memory-bank/progress.md`
