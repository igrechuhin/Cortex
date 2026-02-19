# Promote OperationStatus to str Enum

**Status**: PENDING  
**Created**: 2026-02-19

## Goal

Replace the `OperationStatus` type alias (`type OperationStatus = Literal["success", "error"]`) in `src/cortex/core/models.py` with a `str`-subclassed Enum. This follows the optional follow-up noted in Phase 64 (promote fixed strings to enums) and aligns with existing patterns (e.g. `PreCommitCheck`). JSON and MCP output must remain `"success"` / `"error"` (Pydantic serializes `str` Enum as `.value` by default).

## Context

- `OperationStatus` was introduced as a shared type alias in `cortex.core.models` and is used across 8 modules: core/models, tools/models, refactoring/models, refactoring/rollback_analysis, rules/models, validation/models, tools/pre_commit_helpers, tools/pre_commit_tools.
- Phase 64 (archived) deferred "Generic `Literal["success", "error"]` in every response model" as an optional follow-up; this plan implements that for the single shared type we now have.
- Using a `str` Enum gives: runtime validation, IDE autocomplete, and consistency with project enum patterns; serialization stays unchanged if we use `class OperationStatus(str, Enum)`.

## Approach

1. Define `class OperationStatus(str, Enum)` in `src/cortex/core/models.py` with members `SUCCESS = "success"` and `ERROR = "error"`.
2. Remove the `type OperationStatus = Literal["success", "error"]` alias.
3. Keep all Pydantic model fields as `status: OperationStatus`; no change to field names or JSON shape.
4. Update any code that constructs or compares status (e.g. `result.status == "success"` or `status="success"`) to use `OperationStatus.SUCCESS` / `OperationStatus.ERROR` where values are set, and optionally keep string comparison for reads if desired (e.g. `result.status == OperationStatus.SUCCESS` or `result.status == "success"` both work when the field is typed as `OperationStatus` and Pydantic coerces from string).
5. Ensure Pydantic model_dump/json still emit `"success"`/`"error"` (default for str Enum).

## Implementation Steps

### Step 1: Add enum and remove type alias in core/models.py

- Add `from enum import Enum` if not present.
- Define:
  - `class OperationStatus(str, Enum): SUCCESS = "success"; ERROR = "error"`.
- Remove the line `type OperationStatus = Literal["success", "error"]`.
- Remove unused `Literal` import from `typing` if no other Literal usages remain in that file.

### Step 2: Verify Pydantic serialization

- Confirm that model fields typed as `OperationStatus` serialize to `"success"`/`"error"` in `model_dump()` and `model_dump_json()` (Pydantic v2 serializes str Enum by value by default).
- If any MCP tool returns these models, run a quick smoke test or unit test that parses JSON and asserts string values.

### Step 3: Update construction and comparison sites

- Search codebase for places that set `status="success"` or `status="error"` (or `status=Literal[...]`) in result objects and replace with `status=OperationStatus.SUCCESS` / `status=OperationStatus.ERROR`.
- Optionally replace comparisons like `if result.status == "success"` with `if result.status == OperationStatus.SUCCESS` for consistency; both are valid once the field is typed as `OperationStatus`.
- Ensure no code assumes `status` is a raw str in a way that breaks (e.g. string concatenation or regex on status is fine since str Enum inherits str).

### Step 4: Imports and re-exports

- All modules that currently `from cortex.core.models import ... OperationStatus` continue to work; they now receive the enum class instead of the type alias.
- No change to public API surface; only the type of `OperationStatus` changes from type alias to enum.

### Step 5: Tests and quality gate

- Run full test suite; fix any tests that assert on `status` type (e.g. `assert result.status == "success"` remains valid; if any test checks `type(result.status)` adjust to accept enum).
- Run type checker (pyright) and fix any new errors.
- Run `execute_pre_commit_checks(checks=["quality"])` and fix lint/format/type issues.

## Dependencies

- None. Builds on the existing `OperationStatus` type alias and Phase 64 patterns.

## Success Criteria

- `OperationStatus` is a `str` Enum in `cortex.core.models` with `SUCCESS` and `ERROR`.
- All 8 modules that use `OperationStatus` still type-check and pass tests.
- JSON/MCP output for result models still contains `"status": "success"` or `"status": "error"` (no schema change).
- No remaining `type OperationStatus = Literal[...]` in the codebase.

## Testing Strategy

- **Coverage target**: Minimum 95% for changed code (enum definition, any new validation/branching).
- **Unit tests**: (1) Enum has exactly two members; (2) `OperationStatus.SUCCESS.value == "success"` and `OperationStatus.ERROR.value == "error"`; (3) at least one Pydantic model that uses `status: OperationStatus` serializes to JSON with string "success"/"error".
- **Regression**: All existing tests that assert on `result.status` (string value or comparison) continue to pass; update only if a test explicitly checks that status is a `str` type (change to accept enum or assert on `.value`).
- **AAA pattern**: All new tests follow Arrange–Act–Assert.
- **No blanket skips**: Any skip must be justified.

## Risks and Mitigation

- **Risk**: OpenAPI/MCP schema might expose enum names instead of values.  
  **Mitigation**: Pydantic v2 and FastMCP typically serialize str Enum as value; verify one MCP tool response after change.
- **Risk**: Third-party or test code that does `if status is "success"` could break (identity check).  
  **Mitigation**: Prefer `== "success"` or `== OperationStatus.SUCCESS`; grep for `is "success"` / `is "error"` and fix if found.

## Timeline

Single session (small, localized change).

## Notes

- Phase 64 plan: `.cortex/plans/archive/Phase64/phase-64-promote-fixed-strings-to-enums.md` (optional follow-up item).
- Current definition: `src/cortex/core/models.py` line 23 (`type OperationStatus = Literal["success", "error"]`).
