---
title: "Refactor: Split Oversized session/brief.py and optimization/handlers.py"
component: "tools"
work_type: refactor
status: PENDING
priority: Medium
created: 2026-04-13
depends_on: []
---

## Refactor: Split Oversized session/brief.py and optimization/handlers.py

## Goal

Two modules violate the project's ≤400-line file-size rule:

- `src/cortex/tools/session/brief.py` — 773 lines
- `src/cortex/tools/optimization/handlers.py` — 727 lines

Split each file along existing responsibility boundaries already visible in
the code. No behaviour changes; only internal module organisation changes.

## Context

### `session/brief.py` (773 lines)

Responsibility groups (from `def`/`class` inventory):

| Lines | Group |
|-------|-------|
| 1–55 | Imports and constants |
| 57–220 | Payload capping helpers (`cap_session_brief_payload`, `_session_brief_cap_*`) |
| 221–325 | Async data-loading helpers (`_read_memory_bank_file`, `_load_concurrent_sessions_safe`, etc.) |
| 326–499 | Brief assembly / composition (`_compute_suggestions_and_create_brief`, `_assemble_session_brief`, `_brief_inputs_*`) |
| 500–759 | Async orchestration and top-level entry (`_load_brief_async`, `_gather_brief_components`, `build_session_brief`) |
| 760–773 | `load_memory_bank_files` (utility, separate concern) |

Natural split: **3 modules**

1. `session/brief_cap.py` — payload capping helpers (lines 57–220)
2. `session/brief_loaders.py` — async data-loading helpers (lines 221–325)
3. `session/brief.py` — assembly, orchestration, and public entry points
   (lines 326–773, now ~350 lines)

### `optimization/handlers.py` (727 lines)

Responsibility groups:

| Lines | Group |
|-------|-------|
| 1–68 | Imports and cache invalidation (`invalidate_context_resource_cache`) |
| 69–196 | `load_context_impl` and its helpers (`_execute_load_context`, `_load_context_body`) |
| 197–391 | `summarize_content` and `get_relevance_scores` with bodies/helpers |
| 392–583 | Context payload append helpers (session goal, scope, operations, artifacts, ingested sources, explore summary) |
| 584–727 | Resource-level async entry points (`build_context_resource_payload_async`, `load_context`, `get_relevance_scores_resource`, `summarize_content_resource`) |

Natural split: **3 modules**

1. `optimization/context_appenders.py` — all `_append_*` and `_read_*` helpers
   (lines 392–583)
2. `optimization/context_loaders.py` — `load_context_impl`, `summarize_content`,
   `get_relevance_scores`, and their bodies/helpers (lines 69–391)
3. `optimization/handlers.py` — cache invalidation, resource entry points,
   and re-exports (lines 1–68 + 584–727, now ~200 lines)

## Implementation Steps

### Step 1 — Read both files in full

`Read` `src/cortex/tools/session/brief.py` and
`src/cortex/tools/optimization/handlers.py` end-to-end. Confirm the boundary
lines and identify any cross-references that will need import updates.

### Verification checklist 1

- [ ] Exact line boundaries for each extracted group are noted
- [ ] List of all symbols imported by other modules (callers via `Grep`) is known

### Step 2 — Find all import sites

```bash
rg "from cortex.tools.session.brief import\|from cortex.tools.session import brief" src tests
rg "from cortex.tools.optimization.handlers import\|from cortex.tools.optimization import handlers" src tests
```

Document every symbol imported externally so new module exports can match.

### Verification checklist 2

- [ ] All external callers of each module are listed
- [ ] No symbol will be left unimported after the split

### Step 3 — Extract `session/brief_cap.py`

1. Create `src/cortex/tools/session/brief_cap.py` containing:
   - `_truncate_for_brief_text`, `_truncate_optional`
   - `_session_brief_cap_core_fields`, `_session_brief_cap_workflow_fields`,
     `_session_brief_cap_update`
   - `cap_session_brief_payload`
   - `_cap_concurrent_session_tasks`
2. Update `brief.py` to import from `brief_cap`.
3. No exports from `session/__init__.py` need changing (these are internal).

### Verification checklist 3

- [ ] `brief_cap.py` is ≤400 lines
- [ ] `brief.py` imports cleanly from `brief_cap`
- [ ] `rg "cap_session_brief_payload" src` shows consistent usage

### Step 4 — Extract `session/brief_loaders.py`

1. Create `src/cortex/tools/session/brief_loaders.py` containing:
   - `_read_memory_bank_file`, `_extract_project_name`
   - `_load_concurrent_sessions_safe`, `_load_locked_tasks_safe`,
     `_load_concurrency_info`
   - `_load_gate_feedback_summary_safe`
   - `_constitution_notice_if_missing`
2. Update `brief.py` to import from `brief_loaders`.

### Verification checklist 4

- [ ] `brief_loaders.py` is ≤400 lines
- [ ] No circular imports between `brief_loaders`, `brief_cap`, `brief`

### Step 5 — Verify `brief.py` is now ≤400 lines

After Steps 3–4 the remaining `brief.py` should hold assembly logic,
`_BriefComponents`, `_WorkflowBriefFields`, `build_session_brief`, and
`load_memory_bank_files`. Check line count.

If still over 400, extract `load_memory_bank_files` into `brief_loaders.py`.

### Verification checklist 5

- [ ] `wc -l src/cortex/tools/session/brief.py` ≤ 400

### Step 6 — Extract `optimization/context_appenders.py`

1. Create `src/cortex/tools/optimization/context_appenders.py` containing all
   `_append_*_to_context_payload` and `_read_*` helpers (lines 392–583 approx).
2. Update `handlers.py` to import from `context_appenders`.

### Verification checklist 6

- [ ] `context_appenders.py` is ≤400 lines
- [ ] `handlers.py` imports cleanly

### Step 7 — Extract `optimization/context_loaders.py`

1. Create `src/cortex/tools/optimization/context_loaders.py` containing:
   - `_resolve_load_context_inputs`, `_execute_load_context`, `load_context_impl`,
     `_load_context_body`
   - `summarize_content`, `_summarize_content_body`
   - `get_relevance_scores`, `_resolve_relevance_task`,
     `_execute_relevance_scores_core`, `_get_relevance_scores_body`
2. Update `handlers.py` to import from `context_loaders`.

### Verification checklist 7

- [ ] `context_loaders.py` is ≤400 lines
- [ ] All symbols previously imported from `handlers` by other modules are
  either re-exported from `handlers` or the callers are updated

### Step 8 — Verify `handlers.py` is now ≤400 lines

`handlers.py` should now contain only: cache invalidation,
`build_context_resource_payload_async`, `_append_scoped_context_to_payload`,
and the three resource-level entry points (`load_context`,
`get_relevance_scores_resource`, `summarize_content_resource`).

### Verification checklist 8

- [ ] `wc -l src/cortex/tools/optimization/handlers.py` ≤ 400

### Step 9 — Run quality gate

`run_quality_gate()` — zero regressions expected (pure re-organisation).
Fix any import errors or type checker issues. Do not change function signatures.

### Verification checklist 9

- [ ] All tests pass
- [ ] Type checker is clean
- [ ] Coverage ≥ 90% (no new uncovered paths from the split)

## Dependencies

None. This is a pure internal restructuring; no public MCP tool signatures
change.

## Success Criteria

1. `brief.py`, `brief_cap.py`, `brief_loaders.py` each ≤400 lines.
2. `handlers.py`, `context_appenders.py`, `context_loaders.py` each ≤400 lines.
3. All existing tests pass unchanged.
4. No circular imports.
5. `run_quality_gate()` green.

## Testing Strategy

- **No new tests required** — this is a pure structural refactor. All existing
  tests for `session/brief` and `optimization/handlers` must pass as-is.
- If any test imports from the old module paths directly (not via public API),
  update those import paths in the test files.
- After the split, run the full suite and confirm coverage does not drop below
  the current baseline.

Coverage target: maintain existing ≥90% baseline; no new uncovered code.

## Partial Progress Log

- 2026-04-14: Extracted `brief_cap.py`, `brief_loaders.py`, `context_appenders.py`, and `context_loaders.py`; updated `brief.py`/`handlers.py` imports and compatibility shims — files: src/cortex/tools/session/brief.py, src/cortex/tools/session/brief_cap.py, src/cortex/tools/session/brief_loaders.py, src/cortex/tools/optimization/handlers.py, src/cortex/tools/optimization/context_appenders.py, src/cortex/tools/optimization/context_loaders.py
