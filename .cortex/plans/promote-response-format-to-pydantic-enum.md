# Promote response_format Literal to Pydantic Enum

**Status**: PENDING  
**Created**: 2026-02-19

## Goal

Replace `Literal["concise", "detailed"]` type annotations for `response_format` parameters across Cortex MCP tools with a shared `ResponseFormat(str, Enum)` defined in `src/cortex/core/models.py`. This follows the same pattern as `OperationStatus` promotion and aligns with project standards for fixed sets of string values.

## Context

- `response_format: Literal["concise", "detailed"]` is used across multiple tool modules:
  - `src/cortex/tools/refactoring_operations.py` (3 occurrences)
  - `src/cortex/tools/phase1_foundation_stats.py` (2 occurrences)
  - `src/cortex/tools/validation_operations.py` (2 occurrences)
  - `src/cortex/tools/usage_analytics.py` (4 occurrences)
  - `src/cortex/tools/phase4_optimization_handlers.py` (4 occurrences)
- Phase 50 implemented `response_format` parameter using `Literal` type annotations
- Project coding standards (python-coding-standards.mdc) prefer `class X(str, Enum)` for fixed sets of values that are reused or branched on
- Using a `str` Enum provides: runtime validation, IDE autocomplete, consistency with project enum patterns (e.g., `OperationStatus`, `PreCommitCheck`, `AgentRole`), and better type safety
- JSON/MCP serialization remains unchanged (Pydantic serializes `str` Enum as `.value` by default)

## Approach

1. Define `class ResponseFormat(str, Enum)` in `src/cortex/core/models.py` with members `CONCISE = "concise"` and `DETAILED = "detailed"`.
2. Update all function signatures and type annotations from `Literal["concise", "detailed"]` to `ResponseFormat`.
3. Update default values from `"concise"` to `ResponseFormat.CONCISE`.
4. Update comparisons and assignments to use enum members (e.g., `response_format == ResponseFormat.CONCISE`).
5. Ensure Pydantic model_dump/json still emit `"concise"`/`"detailed"` strings (default for str Enum).

## Implementation Steps

### Step 1: Define ResponseFormat enum in core/models.py

- Add `class ResponseFormat(str, Enum)` to `src/cortex/core/models.py`:

  ```python
  class ResponseFormat(str, Enum):
      """Response format for MCP tools that support concise/detailed output."""
      
      CONCISE = "concise"
      DETAILED = "detailed"
  ```

- Ensure `from enum import Enum` is present (already exists from `OperationStatus`).

### Step 2: Update imports across tool modules

- Add `from cortex.core.models import ResponseFormat` to all affected modules:
  - `src/cortex/tools/refactoring_operations.py`
  - `src/cortex/tools/phase1_foundation_stats.py`
  - `src/cortex/tools/validation_operations.py`
  - `src/cortex/tools/usage_analytics.py`
  - `src/cortex/tools/phase4_optimization_handlers.py`
- Remove `Literal` import from `typing` if no other `Literal` usages remain in each file.

### Step 3: Update function signatures and type annotations

- Replace `response_format: Literal["concise", "detailed"]` with `response_format: ResponseFormat` in all function signatures.
- Replace default values `= "concise"` with `= ResponseFormat.CONCISE`.
- Update type annotations in helper functions and internal methods.

### Step 4: Update comparisons and assignments

- Replace string comparisons:
  - `if response_format == "concise":` → `if response_format == ResponseFormat.CONCISE:`
  - `if response_format != "detailed":` → `if response_format != ResponseFormat.DETAILED:`
- Replace string assignments:
  - `response_format = "concise"` → `response_format = ResponseFormat.CONCISE`
- Ensure MCP tool handlers accept `str` from clients and parse to enum internally (following existing pattern for other enums).

### Step 5: Update MCP tool parameter schemas

- Verify FastMCP tool decorators accept `str` input and validate to `ResponseFormat` enum inside handlers.
- Ensure JSON schema generation still exposes `"concise"` and `"detailed"` as string enum values.
- Update tool descriptions if needed to reference `ResponseFormat` enum.

### Step 6: Verify Pydantic serialization

- Confirm that model fields typed as `ResponseFormat` serialize to `"concise"`/`"detailed"` in `model_dump()` and `model_dump_json()`.
- Test at least one MCP tool response to ensure JSON output contains string values, not enum names.

### Step 7: Update tests

- Update test fixtures and assertions to use `ResponseFormat.CONCISE` / `ResponseFormat.DETAILED` instead of string literals.
- Ensure tests that pass `response_format="concise"` as strings still work (Pydantic should coerce from string).
- Add unit tests for enum definition and serialization.

### Step 8: Run quality gate and fix issues

- Run full test suite; fix any failures.
- Run type checker (pyright) and fix any new errors.
- Run `execute_pre_commit_checks(checks=["quality"])` and fix lint/format/type issues.
- Verify no remaining `Literal["concise", "detailed"]` in the codebase.

## Dependencies

- None. Builds on existing `response_format` implementation from Phase 50 and follows the same pattern as `OperationStatus` promotion.

## Success Criteria

- `ResponseFormat` is a `str` Enum in `cortex.core.models` with `CONCISE` and `DETAILED` members.
- All 5 tool modules that use `response_format` still type-check and pass tests.
- JSON/MCP output for tool responses still contains `"response_format": "concise"` or `"response_format": "detailed"` (no schema change).
- No remaining `Literal["concise", "detailed"]` type annotations in the codebase.
- All function signatures use `ResponseFormat` enum type.
- All comparisons and assignments use enum members.

## Testing Strategy

- **Coverage target**: Minimum 95% for changed code (enum definition, updated functions, validation/branching logic).
- **Unit tests**:
  - (1) Enum has exactly two members
  - (2) `ResponseFormat.CONCISE.value == "concise"` and `ResponseFormat.DETAILED.value == "detailed"`
  - (3) At least one MCP tool that uses `response_format: ResponseFormat` serializes to JSON with string "concise"/"detailed"
  - (4) Test that string input is coerced to enum (e.g., `ResponseFormat("concise")` works)
- **Integration tests**: Verify MCP tool calls with `response_format="concise"` (string) still work and return concise output.
- **Regression**: All existing tests that assert on `response_format` parameter (string value or comparison) continue to pass.
- **AAA pattern**: All new tests follow Arrange–Act–Assert.
- **No blanket skips**: Any skip must be justified and linked to a ticket.

## Risks and Mitigation

- **Risk**: MCP tool parameter schemas might expose enum names instead of values.  
  **Mitigation**: FastMCP/Pydantic typically serialize str Enum as value; verify one MCP tool response after change. Ensure handlers accept `str` and parse to enum internally.
- **Risk**: Test code that passes string literals might break if coercion doesn't work.  
  **Mitigation**: Pydantic v2 coerces strings to enum members automatically; verify with integration tests. Update test fixtures to use enum members for clarity.
- **Risk**: Third-party code or external callers might pass invalid strings.  
  **Mitigation**: Pydantic validation will raise `ValidationError` for invalid values; this is desired behavior. Document enum values in tool descriptions.

## Timeline

Single session (small, localized change across 5 modules).

## Notes

- Follows the same pattern as `OperationStatus` promotion (see `.cortex/plans/archive/Other/operation-status-promote-to-enum.md`).
- Phase 50 plan: `.cortex/plans/archive/Phase50/phase-50-tool-consolidation-response-format.md` (implemented `response_format` with `Literal`).
- Project coding standards: `.cortex/synapse/rules/python/python-coding-standards.mdc` (prefer `class X(str, Enum)` for fixed sets).
- Current usage: 15+ occurrences across 5 tool modules.
