# Phase 19: Fix MCP Server Crash - BrokenResourceError in stdio_server

## Status

- **Status**: PLANNING
- **Priority**: High (Stability/Crash Issue)
- **Start Date**: 2026-01-14
- **Target Completion Date**: 2026-01-16

## Goal

Investigate and fix the MCP server crash caused by `BrokenResourceError` in the `stdio_server` TaskGroup. The error occurs when the client cancels a request or disconnects, causing the `stdin_reader` task to attempt sending messages after the resource has been closed, resulting in an unhandled `ExceptionGroup` that crashes the server.

## Problem

**Observed Error:**
```
2026-01-14 17:41:08.914 [error] Unexpected error in MCP server: unhandled errors in a TaskGroup (1 sub-exception)
  + Exception Group Traceback (most recent call last):
  |   File "/Users/i.grechukhin/Repo/Cortex/src/cortex/main.py", line 27, in main
  |     mcp.run(transport="stdio")
  |     ~~~~~~~^^^^^^^^^^^^^^^^^^^
  |   ...
  |   File "/Users/i.grechukhin/Repo/Cortex/.venv/lib/python3.13/site-packages/mcp/server/stdio.py", line 83, in stdio_server
  |     async with anyio.create_task_group() as tg:
  |                ~~~~~~~~~~~~~~~~~~~~~~~^^
  |   File "/Users/i.grechukhin/Repo/Cortex/.venv/lib/python3.13/site-packages/anyio/_backends/_asyncio.py", line 772, in __aexit__
  |     raise BaseExceptionGroup(
  |         "unhandled errors in a TaskGroup", self._exceptions
  |     ) from None
  | ExceptionGroup: unhandled errors in a TaskGroup (1 sub-exception)
  +-+---------------- 1 ----------------
    | Traceback (most recent call last):
    |   File "/Users/i.grechukhin/Repo/Cortex/.venv/lib/python3.13/site-packages/mcp/server/stdio.py", line 69, in stdin_reader
    |     await read_stream_writer.send(message)
    |   File "/Users/i.grechukhin/Repo/Cortex/.venv/lib/python3.13/site-packages/anyio/streams/memory.py", line 255, in send
    |     raise BrokenResourceError from None
    | anyio.BrokenResourceError
    +------------------------------------
```

**Additional Context:**
- Client error: "Received a response for an unknown message ID: Request cancelled"
- Error occurs during TaskGroup cleanup when exiting `stdio_server` context
- The `stdin_reader` task continues trying to send messages after the resource is closed
- Current error handling in `main.py` doesn't catch `ExceptionGroup` or `anyio.BrokenResourceError` specifically

**Impact:**
- Server crashes instead of gracefully handling client disconnections
- Poor user experience when client cancels requests
- Server instability during normal operation
- Related issue documented in Phase 11 plan: "MCP Connection Instability" with `BrokenResourceError` causing server restarts

## Context

**Location:** `src/cortex/main.py`

**Current Error Handling:**
```python
def main() -> None:
    try:
        mcp.run(transport="stdio")
    except KeyboardInterrupt:
        logger.info("MCP server interrupted by user")
        sys.exit(0)
    except BrokenPipeError as e:
        logger.warning(f"MCP stdio connection broken (client disconnected): {e}")
        sys.exit(0)
    except ConnectionError as e:
        logger.error(f"MCP connection error: {e}")
        sys.exit(1)
    except OSError as e:
        if "Broken pipe" in str(e) or "Connection reset" in str(e):
            logger.warning(f"MCP connection reset (client disconnected): {e}")
            sys.exit(0)
        logger.error(f"MCP OS error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Unexpected error in MCP server: {e}")
        sys.exit(1)
```

**Issues:**
1. `ExceptionGroup` (Python 3.11+) is not caught - it's a `BaseException`, not an `Exception`
2. `anyio.BrokenResourceError` is not explicitly handled
3. The generic `Exception` handler catches it but logs as "Unexpected error" instead of graceful disconnection
4. No handling for `BaseExceptionGroup` which wraps the `BrokenResourceError`

**Related Code:**
- `src/cortex/core/mcp_stability.py` - Has `_is_connection_error()` helper but doesn't handle `ExceptionGroup`
- Phase 11 plan documents similar `BrokenResourceError` issues
- ADR-006 shows exception group handling patterns but not applied to main entry point

## Approach

### Investigation Steps

1. **Root Cause Analysis**
   - Understand the `stdio_server` TaskGroup lifecycle
   - Identify why `stdin_reader` continues after resource closure
   - Determine if this is expected behavior or a bug in FastMCP/anyio
   - Check FastMCP version and anyio version for known issues

2. **Error Handling Strategy**
   - Add `BaseExceptionGroup` handling to catch TaskGroup exceptions
   - Extract `BrokenResourceError` from exception groups
   - Add explicit `anyio.BrokenResourceError` handling
   - Ensure graceful shutdown on client disconnection

3. **Testing Strategy**
   - Test client disconnection scenarios
   - Test request cancellation scenarios
   - Verify graceful shutdown behavior
   - Ensure no resource leaks

### Implementation Steps

1. **Update Error Handling in `main.py`**
   - Add `BaseExceptionGroup` handler to extract nested exceptions
   - Add explicit `anyio.BrokenResourceError` handling
   - Update `_is_connection_error()` in `mcp_stability.py` to recognize `BrokenResourceError`
   - Ensure graceful exit (exit code 0) for client disconnections

2. **Enhance Logging**
   - Distinguish between client disconnections (warning) and actual errors (error)
   - Log exception group details when extracting nested exceptions
   - Add context about whether error is recoverable

3. **Add Tests**
   - Unit tests for error handling paths
   - Integration tests simulating client disconnections
   - Test exception group extraction logic

4. **Documentation**
   - Update error handling documentation
   - Document graceful shutdown behavior
   - Add troubleshooting guide for connection issues

## Implementation Details

### Step 1: Update `main.py` Error Handling

**Changes:**
- Import `BaseExceptionGroup` from `builtins` (Python 3.11+)
- Import `anyio` to access `BrokenResourceError`
- Add handler for `BaseExceptionGroup` that extracts nested exceptions
- Add explicit handler for `anyio.BrokenResourceError`
- Ensure graceful exit for client disconnections

**Code Pattern:**
```python
import sys
from builtins import BaseExceptionGroup  # Python 3.11+
import anyio

def main() -> None:
    try:
        mcp.run(transport="stdio")
    except KeyboardInterrupt:
        logger.info("MCP server interrupted by user")
        sys.exit(0)
    except BaseExceptionGroup as eg:
        # Extract nested exceptions from TaskGroup
        broken_resource_found = False
        for exc in eg.exceptions:
            if isinstance(exc, anyio.BrokenResourceError):
                broken_resource_found = True
                logger.warning(
                    f"MCP stdio connection broken during TaskGroup cleanup "
                    f"(client disconnected): {exc}"
                )
                break
        
        if broken_resource_found:
            sys.exit(0)  # Graceful shutdown
        else:
            logger.error(f"MCP server TaskGroup error: {eg}")
            sys.exit(1)
    except anyio.BrokenResourceError as e:
        logger.warning(f"MCP stdio connection broken (client disconnected): {e}")
        sys.exit(0)  # Graceful shutdown
    except BrokenPipeError as e:
        logger.warning(f"MCP stdio connection broken (client disconnected): {e}")
        sys.exit(0)
    except ConnectionError as e:
        logger.error(f"MCP connection error: {e}")
        sys.exit(1)
    except OSError as e:
        if "Broken pipe" in str(e) or "Connection reset" in str(e):
            logger.warning(f"MCP connection reset (client disconnected): {e}")
            sys.exit(0)
        logger.error(f"MCP OS error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Unexpected error in MCP server: {e}")
        sys.exit(1)
```

### Step 2: Update `mcp_stability.py`

**Changes:**
- Update `_is_connection_error()` to recognize `anyio.BrokenResourceError`
- Add `BrokenResourceError` to connection error types

**Code Pattern:**
```python
import anyio

def _is_connection_error(e: Exception) -> bool:
    connection_error_types = (
        ConnectionError,
        BrokenPipeError,
        OSError,
        RuntimeError,
        anyio.BrokenResourceError,  # Add explicit handling
    )
    # ... rest of function
```

### Step 3: Add Tests

**Test Cases:**
1. Test `BaseExceptionGroup` with `BrokenResourceError` extraction
2. Test direct `anyio.BrokenResourceError` handling
3. Test graceful shutdown on client disconnection
4. Test that other exceptions still raise appropriately

**Test File:** `tests/unit/test_main_error_handling.py`

### Step 4: Documentation Updates

**Files to Update:**
- `docs/development/error-handling.md` (if exists)
- `docs/troubleshooting.md` (if exists)
- Add to `CLAUDE.md` under "Common Pitfalls"

## Dependencies

- **Python 3.11+**: Required for `BaseExceptionGroup` support
- **anyio**: Already a dependency (via FastMCP)
- **FastMCP**: MCP server framework (check version for known issues)

## Success Criteria

1. ✅ Server handles client disconnections gracefully (exit code 0)
2. ✅ `BrokenResourceError` in TaskGroup is caught and handled
3. ✅ No server crashes on request cancellation
4. ✅ Appropriate logging (warning for disconnections, error for actual errors)
5. ✅ Tests pass for all error handling paths
6. ✅ Documentation updated with error handling patterns

## Testing Strategy

### Unit Tests

- Test `BaseExceptionGroup` extraction logic
- Test `anyio.BrokenResourceError` handling
- Test exception priority (most specific handlers first)
- Test graceful exit codes

### Integration Tests

- Simulate client disconnection during request
- Simulate request cancellation
- Verify no resource leaks
- Verify proper cleanup

### Manual Testing

- Connect client and disconnect abruptly
- Cancel requests mid-execution
- Verify server logs show appropriate warnings
- Verify server exits cleanly

## Risks & Mitigation

### Risk 1: Breaking Existing Error Handling

**Mitigation:**
- Keep all existing exception handlers
- Add new handlers before generic `Exception` handler
- Test all existing error paths still work

### Risk 2: Python Version Compatibility

**Mitigation:**
- `BaseExceptionGroup` is Python 3.11+ only
- Check Python version before importing
- Provide fallback for older Python versions (if needed)

### Risk 3: Masking Real Errors

**Mitigation:**
- Only treat `BrokenResourceError` as graceful disconnection
- Log all other exceptions in exception groups as errors
- Maintain distinction between warnings and errors

## Timeline

- **Day 1 (2026-01-14)**: Investigation and root cause analysis
- **Day 2 (2026-01-15)**: Implementation and testing
- **Day 3 (2026-01-16)**: Documentation and validation

## Notes

- This issue is related to the "MCP Connection Instability" documented in Phase 11
- FastMCP/anyio may have updates that address this - check for library updates
- Consider upstreaming fix to FastMCP if root cause is in library
- Monitor for similar issues after fix is deployed

## Related Issues

- Phase 11: "MCP Connection Instability" - Documents `BrokenResourceError` causing server restarts
- ADR-006: Exception group handling patterns (not applied to main entry point)
