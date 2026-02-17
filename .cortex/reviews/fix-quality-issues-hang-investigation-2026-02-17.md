# Investigation: fix_quality_issues Hang After execute_pre_commit_checks

**Date:** 2026-02-17  
**Transcript:** `eecf1c41-6362-4d17-9f01-f64e5f6fe925.txt`  
**Log:** `2026-02-17 20:13:24.254 [info] Handling CallTool action for tool 'fix_quality_issues'`

---

## Summary

`fix_quality_issues` hanged after `execute_pre_commit_checks` was called. Both tools use a serial semaphore, so `fix_quality_issues` should wait up to 330 seconds for `execute_pre_commit_checks` to finish. The hang suggests either:

1. `execute_pre_commit_checks` never finished/released the semaphore
2. The semaphore timeout mechanism failed
3. A deadlock prevented semaphore release

---

## What Happened

From the transcript and log:

1. **Agent called `rules`** (line 87-89): `operation="get_relevant"`
2. **Agent called `execute_pre_commit_checks`** (line 90-94): `checks=["type_check","quality","format"]`
3. **Both tools returned empty results** (lines 96, 98): `[Tool result]` with no content
4. **Agent then called `fix_quality_issues`**: Log shows "Handling CallTool action for tool 'fix_quality_issues'"
5. **Tool hanged**: No response, no timeout error

---

## Root Cause Analysis

### Tool Serialization

Both `execute_pre_commit_checks` and `fix_quality_issues` are in `long_running_tools_serialized`:

```python
_LONG_RUNNING_TOOLS_SERIALIZED = frozenset(
    {"execute_pre_commit_checks", "fix_markdown_lint", "fix_quality_issues"}
)
```

This means:

- Only **one** of these tools can run at a time
- A serial semaphore (`TrackedSemaphore(1)`) enforces this
- If `execute_pre_commit_checks` is running, `fix_quality_issues` waits up to **330 seconds**

### Semaphore Wait Logic

From `src/cortex/core/mcp_stability.py` (lines 680-683):

```python
if use_serial_semaphore:
    sem = get_long_running_semaphore()
    if not await sem.try_acquire(timeout=LONG_RUNNING_SEMAPHORE_WAIT_SECONDS):
        raise RuntimeError(_LONG_RUNNING_BUSY_MSG)
```

**Expected behavior**:

- `fix_quality_issues` waits up to 330 seconds for semaphore
- If `execute_pre_commit_checks` finishes within 330 seconds, `fix_quality_issues` proceeds
- If `execute_pre_commit_checks` is still running after 330 seconds, `fix_quality_issues` raises `RuntimeError`

### Possible Causes

1. **`execute_pre_commit_checks` Never Finished**:
   - Tool may be stuck in an infinite loop or blocking operation
   - Tool may have crashed without releasing semaphore
   - Tool may be waiting for a resource that never becomes available

2. **Semaphore Never Released**:
   - Exception in `execute_pre_commit_checks` may have skipped `finally` block
   - Deadlock preventing semaphore release
   - Process crash before semaphore release

3. **Timeout Mechanism Failed**:
   - `asyncio.wait_for` may not be working correctly
   - Event loop may be blocked preventing timeout
   - Timeout value may not be applied correctly

4. **Empty Tool Results**:
   - Both `rules` and `execute_pre_commit_checks` returned empty results
   - This suggests they may have hung or crashed before returning
   - If `execute_pre_commit_checks` crashed, semaphore may not have been released

---

## Evidence

### Transcript Analysis

- **Line 96**: `[Tool result] mcp_cortex_rules` - Empty result
- **Line 98**: `[Tool result] mcp_cortex_execute_pre_commit_checks` - Empty result
- **No further tool calls**: Agent never got to call `fix_quality_issues` in transcript
- **Log shows**: `fix_quality_issues` was called but hung

### Code Analysis

**Semaphore timeout** (`src/cortex/core/mcp_stability_config.py:32-39`):

```python
async def try_acquire(self, timeout: float = 0.0) -> bool:
    """Acquire if available within timeout (seconds). Return True if acquired."""
    try:
        _ = await asyncio.wait_for(self._semaphore.acquire(), timeout=timeout)
        self._current_count -= 1
        return True
    except TimeoutError:
        return False
```

This looks correct - `asyncio.wait_for` should timeout after the specified seconds.

**Semaphore release** (`src/cortex/core/mcp_stability.py:686-687`):

```python
finally:
    sem.release()
```

The `finally` block should ensure semaphore is released even if an exception occurs.

---

## Recommendations

### Immediate Actions

1. **Check Server Logs**:
   - Look for errors in `execute_pre_commit_checks` execution
   - Check if semaphore was released
   - Verify timeout was applied

2. **Check for Stuck Processes**:
   - Verify `execute_pre_commit_checks` completed or crashed
   - Check if semaphore is still held
   - Look for deadlock indicators

3. **Add Diagnostic Logging**:
   - Log when semaphore is acquired/released
   - Log when timeout expires
   - Log semaphore state before/after operations

### Long-Term Improvements

1. **Add Semaphore State Monitoring**:
   - Track which tool holds the semaphore
   - Log semaphore acquisition/release with timestamps
   - Add health check endpoint for semaphore state

2. **Improve Error Handling**:
   - Ensure semaphore is always released, even on crash
   - Add watchdog to detect stuck tools
   - Auto-release semaphore after tool timeout

3. **Better Progress Reporting**:
   - Report progress during semaphore wait
   - Show which tool is blocking
   - Estimate wait time remaining

---

## Related Issues

- **Tool Hang Investigation** (f666c731): `rules` and `execute_pre_commit_checks` returned empty results
- **Connection Closed Investigation** (d3c1b4ce): Tools executed but connection closed
- **Tool Hang Before Execution** (0d491698): Agent hung before making tool calls

---

## Status

**Status**: 🔍 Investigation needed  
**Priority**: High - Blocks quality fixes  
**Next Steps**:

1. Check server logs for `execute_pre_commit_checks` execution
2. Verify semaphore state and release mechanism
3. Add diagnostic logging for semaphore operations
4. Investigate why empty tool results occurred
