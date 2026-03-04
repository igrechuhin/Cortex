# Phase 72: Fix is_connection_error Over-Matching and Consolidate Duplicates

## Status

PENDING

## Goal

Fix the `is_connection_error` function to use precise pattern matching that avoids false positives from the "resource" keyword, **and consolidate the three duplicate implementations** into a single shared function.

## Context

The code review (2026-03-04) identified that `is_connection_error` in `core/mcp_stability_config.py` matches on the broad keyword "resource", causing legitimate errors like "resource not found" or "resource limit exceeded" to be incorrectly classified as connection errors. This triggers retry logic instead of proper error handling.

### New finding (2026-03-04 agent audit)

There are **three separate `_is_connection_error` / `is_connection_error` implementations** with divergent logic:

1. **`src/cortex/core/mcp_stability_config.py:126`** — `is_connection_error(e: Exception)` — the one the plan originally targets. Uses `isinstance` checks + broad keyword matching including `"resource"`. Used by `mcp_stability_retry.py` and `mcp_stability_progress.py`.
2. **`src/cortex/main.py:68`** — `_is_connection_error(exc: BaseException)` — private, handles `BaseExceptionGroup` recursively. Does NOT include the `"resource"` keyword but DOES use string matching for `"Broken pipe"` and `"Connection reset"` on `OSError`. Also catches `asyncio.CancelledError`.
3. **`src/cortex/core/context_logging.py:21`** — `_is_connection_error(exc: BaseException)` — private, nearly identical to the `main.py` version but lacks `CancelledError` handling.

This duplication means a fix to one location leaves the other two unpatched. A previous agent implementation only fixed ONE of these locations and declared the phase complete.

## Approach

1. Consolidate all three implementations into a single canonical `is_connection_error()` in `mcp_stability_config.py`
2. Fix the over-matching (remove "resource" keyword, tighten string patterns)
3. Replace the private copies in `main.py` and `context_logging.py` with imports from the canonical location

## Implementation Steps

### Step 1: Audit all three implementations and their callers

- Read all three functions and document their differences
- Map every call site: `main.py`, `context_logging.py`, `mcp_stability_retry.py`, `mcp_stability_progress.py`
- Identify the superset of exception types that need to be handled (including `BaseExceptionGroup` recursion and `CancelledError`)
- Catalog actual MCP connection error messages from the framework

### Step 2: Consolidate into a single canonical function

- Update `is_connection_error` in `mcp_stability_config.py` to handle:
  - `isinstance` checks for `ConnectionError`, `BrokenPipeError`, `OSError`, `anyio.BrokenResourceError`, `anyio.ClosedResourceError`, `asyncio.CancelledError`
  - `BaseExceptionGroup` recursive handling (from `main.py` version)
  - Accept `BaseException` (not just `Exception`) to match all call sites
- **Remove** the private `_is_connection_error` from `main.py` and `context_logging.py`
- **Replace** with imports from `mcp_stability_config`

### Step 3: Fix the over-matching

- **Remove** the broad `"resource"` keyword from keyword matching
- **Remove** `"tool not found"` — this is not a connection error
- Replace broad `"connection"` keyword match on RuntimeError with specific patterns: `"-32000"`, `"connection closed"`, `"connection refused"`, `"connection reset"`
- Tighten OSError string matching to specific messages only
- Add error code-based matching where MCP provides error codes

### Step 4: Post-implementation verification (MANDATORY)

- **Re-read all three source files** after editing to confirm:
  - The canonical function has correct logic
  - `main.py` and `context_logging.py` import from the canonical location
  - No private copies remain
- **Search the full codebase** for `def.*is_connection_error` to confirm exactly one definition exists
- **Search for the removed keywords** (`"resource"`, `"tool not found"`) to confirm they are gone

### Step 5: Add tests

- Test with true connection error messages (should return True)
- Test with false positives: "resource not found", "resource limit exceeded", "resource already exists", "tool not found" (should return False)
- Test `BaseExceptionGroup` containing connection errors
- Test `asyncio.CancelledError` handling
- Test edge cases: empty strings, None, mixed-case messages

## Dependencies

None.

## Success Criteria

- **Single canonical implementation** — exactly one `is_connection_error` definition in the codebase
- Zero false positives from "resource" or "tool not found" keywords
- All genuine connection errors still detected (including BaseExceptionGroup nesting)
- `main.py` and `context_logging.py` import from canonical location (no private copies)
- Clear documentation of which patterns indicate connection errors
- 95%+ test coverage for modified function and callers

## Testing Strategy

- **Unit Tests**: Test each known connection error message, test each known false positive, test BaseExceptionGroup recursion, test CancelledError
- **Integration Tests**: Verify retry logic only triggers for actual connection errors (not "resource not found")
- **Edge Cases**: Empty message, None, unicode, very long messages, partial matches, nested ExceptionGroups
- **Regression**: All existing `test_main_error_handling.py` and `test_mcp_stability_connection_closure.py` tests pass
- **Coverage Target**: 95%+ for modified module

## Risks & Mitigation

- **Risk**: Missing a real connection error pattern after tightening
- **Mitigation**: Catalog errors from MCP framework source; add logging for unrecognized error patterns to catch gaps in production
- **Risk**: Consolidation breaks callers that depend on BaseException vs Exception signatures
- **Mitigation**: Unified function accepts `BaseException`; update type annotations at all call sites
- **Risk**: Agent only fixes one of the three implementations and declares done
- **Mitigation**: Step 4 mandates post-implementation verification across all three files and a codebase-wide search for duplicate definitions

## Timeline

Low effort (2-4h)
