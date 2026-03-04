# Phase 77: Fix Coverage Gaps, Silent Error Handling, and Stub Implementation

## Status

PENDING

## Goal

Address completeness gaps: add tests for the 0%-coverage module, fix silent error swallowing blocks, and resolve the stub implementation.

## Context

The code review (2026-03-04) identified three completeness issues:

- **MEDIUM**: `result_links_models.py` has 0% test coverage (87 statements, lines 3-166)
- **MEDIUM**: 11 broad `except Exception: pass` blocks silently swallow errors
- **HIGH**: `_migrate_doc_mcp_style` in `structure_migration.py` is an unimplemented stub

## Approach

Add tests for uncovered module, replace silent catches with specific exception handling and logging, and either implement or remove the migration stub.

## Implementation Steps

### Step 1: Add tests for result_links_models.py

- Read `src/cortex/tools/validation/result_links_models.py` to understand its classes
- Create `tests/tools/validation/test_result_links_models.py`
- Test all public classes and methods
- Cover edge cases: empty inputs, invalid data, boundary conditions
- Target 95%+ coverage

### Step 2: Fix silent error swallowing (11 blocks)

- Find all 11 `except Exception: pass` blocks
- For each block:
  - Determine what exceptions are actually expected
  - Replace `Exception` with specific exception types
  - Add `logger.debug()` or `logger.warning()` for caught exceptions
  - Remove bare `pass` — add meaningful handling
- Focus on the 5 MEDIUM-severity blocks first

### Step 3: Resolve _migrate_doc_mcp_style stub

- Read `src/cortex/structure/structure_migration.py` to understand the stub
- Determine if migration is still needed (check if the doc MCP style migration is a current requirement)
- If needed: implement the migration logic
- If not needed: remove the stub and add a comment explaining the decision

### Step 4: Verify coverage improvements

- Run pytest with coverage for modified modules
- Verify result_links_models.py reaches 95%+
- Verify overall coverage remains above 92%

## Dependencies

None.

## Success Criteria

- `result_links_models.py` coverage reaches 95%+
- Zero `except Exception: pass` blocks in codebase
- `_migrate_doc_mcp_style` either implemented or cleanly removed
- All tests pass
- Overall coverage maintained or improved

## Testing Strategy

- **Unit Tests**: All public classes in result_links_models.py, error handling behavior for each fixed except block
- **Edge Cases**: Empty inputs, malformed data, missing fields, None values
- **Regression**: All existing tests pass
- **Coverage Target**: 95%+ for new/modified modules

## Risks & Mitigation

- **Risk**: Replacing silent catches may surface previously hidden errors
- **Mitigation**: Replace gradually with logging first, then specific handling; run full test suite after each change
- **Risk**: _migrate_doc_mcp_style removal may break a migration path
- **Mitigation**: Check if any code calls it before removing; if called, implement it

## Timeline

Medium effort (8-12h)
