# Phase 75: Unify Tool Response Format

## Status

IN PROGRESS

## Goal

Standardize all MCP tool response formats to use a single consistent pattern, replacing the current three competing patterns.

## Context

The code review (2026-03-04) identified:

- **HIGH**: Tools split between `"status": "success"` and `"success": true` response formats
- **MEDIUM**: Three competing error response patterns: `{"error": "..."}`, `{"status": "error", "message": "..."}`, `{"success": false, "error": "..."}`

This inconsistency forces consumers to handle multiple formats and increases error potential.

## Approach

Define a canonical response format, create a shared response builder utility, and migrate all tools to use it.

## Implementation Steps

### Step 1: Define canonical response format

- Choose `{"status": "success"|"error", ...}` as the canonical format (already the most common pattern)
- Define the canonical error format: `{"status": "error", "error": "<message>", "error_code": "<optional code>"}`
- Document the format in a shared module docstring

### Step 2: Create shared response builder

- Create `src/cortex/tools/response_builder.py` with helper functions:
  - `success_response(**data) -> dict` — returns `{"status": "success", **data}`
  - `error_response(error: str, error_code: str | None = None) -> dict` — returns `{"status": "error", "error": error, ...}`
- Keep it simple — no over-engineering

### Step 3: Migrate tools to use response builder

- Identify all tool modules returning responses
- Replace inline response dict construction with response builder calls
- Work module-by-module to minimize blast radius per commit

### Step 4: Update tests

- Update test assertions to match the canonical format
- Add tests for the response builder itself
- Ensure all tool tests pass with new format

## Dependencies

None.

## Success Criteria

- Single response format across all tools: `{"status": "success"|"error", ...}`
- All response construction uses shared builder
- Zero inline response dict construction in tool modules
- All existing tests pass (updated for new format)
- 95%+ test coverage for response builder

## Testing Strategy

- **Unit Tests**: Response builder produces correct format for success/error cases
- **Integration Tests**: All tool modules return canonical format
- **Edge Cases**: Empty data, None values, nested structures, Unicode error messages
- **Regression**: All existing tool tests pass with updated assertions
- **Coverage Target**: 95%+ for response_builder module

## Risks & Mitigation

- **Risk**: External consumers (MCP clients) may depend on current format
- **Mitigation**: Audit MCP client code for format assumptions; if needed, support a transition period with both formats
- **Risk**: Large number of files to change
- **Mitigation**: Migrate module-by-module; each module change is independent and can be committed separately

## Timeline

High effort (16-24h — many tool modules to migrate)

## Current Progress (2026-03-04)

- Created shared `cortex.tools.response_builder` module with `success_response` and `error_response` helpers using the canonical `{"status": "success"|"error", ...}` shape.
- Migrated `manage_file` helper logic in `manage_file_helpers` to use `error_response` for all error paths.
- Added unit tests for `success_response` and `error_response` in `tests/unit/test_response_builder.py`.
- Verified format, type checks, quality gate, and full test suite all pass with the new helpers.

Next sessions should continue Step 3 by migrating remaining MCP tool modules to use the shared response builder and updating any tests that assert on the old inline response dictionaries.
