# Promote load_context depth Literal to Pydantic Enum

**Status**: PENDING  
**Created**: 2026-02-19

## Goal

Replace `Literal["metadata_only", "summary", "full"]` type annotations for the `depth` parameter (used by `load_context` and related context operations) with a shared `ContextDepth(str, Enum)` defined in `src/cortex/core/models.py`. This aligns with the same pattern as `OperationStatus` and the planned `ResponseFormat` promotion, and with project standards for fixed sets of string values.

## Context

- `depth: Literal["metadata_only", "summary", "full"]` (or `depth: str`) is used in:
  - `src/cortex/tools/phase4_optimization_handlers.py`: `load_context` tool, `_execute_load_context`, `_execute_load_context_with_logging`, `_determine_depth_from_budget` (5 occurrences of the Literal type; internal helpers pass `effective_depth: str` into phase4_context_operations).
  - `src/cortex/tools/phase4_context_operations.py`: `load_context_impl`, `_dispatch_by_depth`, `_handle_full_or_summary_depth`, `manage_file` (get_content), and other helpers use `depth: str` with string comparisons (`depth == "metadata_only"`, `depth == "summary"`).
- Phase 51 introduced the `depth` parameter for `load_context` with values `metadata_only`, `summary`, `full`.
- Project coding standards (python-coding-standards.mdc) prefer `class X(str, Enum)` for fixed sets of values that are reused or branched on.
- Using a `str` Enum provides: runtime validation, IDE autocomplete, consistency with `OperationStatus` and the planned `ResponseFormat` enum, and better type safety.
- JSON/MCP serialization remains unchanged (Pydantic serializes `str` Enum as `.value` by default).

## Approach

1. Define `class ContextDepth(str, Enum)` in `src/cortex/core/models.py` with members `METADATA_ONLY = "metadata_only"`, `SUMMARY = "summary"`, `FULL = "full"`.
2. Update all function signatures and type annotations from `Literal["metadata_only", "summary", "full"]` or `depth: str` (where depth is one of these three values) to `ContextDepth` (or `ContextDepth | None` where applicable).
3. Update default values from `"full"` to `ContextDepth.FULL` where the parameter is typed as `ContextDepth`.
4. Update comparisons and assignments to use enum members (e.g. `depth == ContextDepth.METADATA_ONLY`).
5. Ensure MCP tool handlers accept `str` from clients and parse to `ContextDepth` (or None) internally; Pydantic/FastMCP can coerce string arguments to enum.
6. Ensure Pydantic model_dump/JSON still emit `"metadata_only"` / `"summary"` / `"full"` strings (default for str Enum).

## Implementation Steps

### Step 1: Define ContextDepth enum in core/models.py

- Add `class ContextDepth(str, Enum)` to `src/cortex/core/models.py`:

  ```python
  class ContextDepth(str, Enum):
      """Content depth for load_context and context operations."""

      METADATA_ONLY = "metadata_only"
      SUMMARY = "summary"
      FULL = "full"
  ```

- Ensure `from enum import Enum` is present (already exists from `OperationStatus`).

### Step 2: Update phase4_optimization_handlers.py

- Add `from cortex.core.models import ContextDepth`.
- Replace `Literal["metadata_only", "summary", "full"]` with `ContextDepth` in:
  - `load_context(..., depth: ContextDepth | None = None, ...)`.
  - `_execute_load_context_with_logging(..., depth: ContextDepth | None, ...)`.
  - `_execute_load_context(..., depth: ContextDepth | None, ...)`.
  - `_determine_depth_from_budget(depth: ContextDepth | None, token_budget: int | None) -> ContextDepth`.
- In `_determine_depth_from_budget`, return `ContextDepth.FULL`, `ContextDepth.METADATA_ONLY`, `ContextDepth.SUMMARY` instead of string literals.
- When calling into `phase4_context_operations.load_context_impl`, pass `effective_depth` as `ContextDepth` (implementation in phase4_context_operations will accept enum).
- Remove `Literal` from typing import in this file if no other Literal usages remain.

### Step 3: Update phase4_context_operations.py

- Add `from cortex.core.models import ContextDepth`.
- Change `load_context_impl(..., depth: str = "full", ...)` to `depth: ContextDepth | str = ContextDepth.FULL` (or `ContextDepth` only and default `ContextDepth.FULL`); normalize any `str` input to `ContextDepth` at entry if needed for backward compatibility.
- Change `_dispatch_by_depth`, `_handle_full_or_summary_depth`, and any other helpers that take `depth: str` to use `ContextDepth` (or accept `ContextDepth | str` and normalize once at boundary).
- Replace string comparisons:
  - `depth == "metadata_only"` → `depth == ContextDepth.METADATA_ONLY` (or compare with `.value` if keeping str in a few places).
  - `depth == "summary"` → `depth == ContextDepth.SUMMARY`.
- Update `manage_file` get_content path and any other call sites that pass `"depth": "metadata_only"` to use `ContextDepth.METADATA_ONLY.value` or the enum as appropriate.
- Ensure docstrings and tool descriptions still document the three values as strings for API consumers.

### Step 4: MCP tool parameter and coercion

- Verify `load_context` MCP tool still accepts string values `"metadata_only"`, `"summary"`, `"full"` from clients (FastMCP/Pydantic typically coerce str to str Enum).
- If needed, add explicit coercion in the handler: e.g. `depth = ContextDepth(depth) if depth is not None else None` for string input.
- Ensure JSON schema for the tool still exposes the three string enum values.

### Step 5: Verify Pydantic serialization

- Confirm that any model fields or response structures that include `depth` serialize to `"metadata_only"` / `"summary"` / `"full"` in `model_dump()` and `model_dump_json()`.
- Spot-check one MCP response that includes `depth` to ensure JSON uses string values.

### Step 6: Update tests

- Update tests in `tests/tools/test_phase4_*.py` (and any other tests touching load_context or context depth) to use `ContextDepth.METADATA_ONLY`, `ContextDepth.SUMMARY`, `ContextDepth.FULL` instead of string literals where assertions or parameters are set in code.
- Keep tests that pass `depth="metadata_only"` as strings where testing MCP/API behavior (coercion).
- Add unit tests for `ContextDepth` (members, values, serialization).
- Ensure no remaining `Literal["metadata_only", "summary", "full"]` in the codebase.

### Step 7: Run quality gate

- Run full test suite; fix any failures.
- Run type checker (pyright) and fix any new errors.
- Run `execute_pre_commit_checks(checks=["quality"])` and fix lint/format/type issues.

## Dependencies

- None. Follows the same pattern as `OperationStatus` and the planned `ResponseFormat` promotion (`.cortex/plans/promote-response-format-to-pydantic-enum.md`).

## Success Criteria

- `ContextDepth` is a `str` Enum in `cortex.core.models` with `METADATA_ONLY`, `SUMMARY`, `FULL` members.
- All usages in `phase4_optimization_handlers.py` and `phase4_context_operations.py` use `ContextDepth` (or normalized from str at boundary).
- JSON/MCP output and tool parameters still use string values `"metadata_only"`, `"summary"`, `"full"` (no schema change for clients).
- No remaining `Literal["metadata_only", "summary", "full"]` type annotations.
- All depth comparisons use enum members.

## Testing Strategy

- **Coverage target**: Minimum 95% for changed code (enum definition, updated functions, depth branching).
- **Unit tests**: (1) Enum has exactly three members with correct values. (2) At least one MCP or internal path that uses `ContextDepth` serializes to JSON with string values. (3) String input is coerced to enum where required. (4) `_determine_depth_from_budget` returns correct enum members for None, low/medium/high budget.
- **Integration tests**: Verify `load_context(depth="metadata_only")` (string) still works and returns metadata-only style output; same for `"summary"` and `"full"`.
- **Regression**: All existing load_context and context-operation tests pass; depth-related behavior unchanged.
- **AAA pattern**: All new tests follow Arrange–Act–Assert.
- **No blanket skips**: Any skip must be justified and linked to a ticket.

## Risks and Mitigation

- **Risk**: MCP clients send unknown strings for `depth`.  
  **Mitigation**: Validate/coerce in handler; Pydantic or explicit `ContextDepth(value)` will raise for invalid values; document enum in tool description.
- **Risk**: Internal callers (e.g. manage_file) pass str.  
  **Mitigation**: Normalize at boundary (e.g. `ContextDepth(depth)` or accept `ContextDepth | str` and normalize once).

## Timeline

Single session (localized change across two main modules and tests).

## Notes

- Aligns with `.cortex/plans/promote-response-format-to-pydantic-enum.md` and completed OperationStatus promotion.
- Phase 51: depth parameter introduced for load_context (see `.cortex/plans/archive/Phase51/phase-51-just-in-time-context-section-loading.md`).
