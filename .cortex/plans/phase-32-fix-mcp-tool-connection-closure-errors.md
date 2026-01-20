# Phase 32: Fix MCP Tool Connection Closure Errors

## Status

- **Status**: PLANNING
- **Priority**: ASAP (Stability/Critical Issue)
- **Start Date**: 2026-01-16
- **Target Completion Date**: 2026-01-17

## Goal

Investigate and fix MCP tool connection closure errors that cause tool calls to fail with "MCP error -32000: Connection closed" even when the server error handling is in place. The issue manifests as tool calls failing during execution, causing poor user experience and blocking workflows.

## Problem

**Observed Errors from Logs:**

```text
2026-01-16 15:11:17.885 [error] MCP server TaskGroup error: unhandled errors in a TaskGroup (1 sub-exception)
2026-01-16 15:11:17.939 [error] Error calling tool 'fix_markdown_lint': MCP error -32000: Connection closed
2026-01-16 15:11:17.939 [info] Client closed for command
```

**Additional Context:**

- Error occurs during tool execution (e.g., `fix_markdown_lint`)
- Server error handling catches `BaseExceptionGroup` but tool calls still fail
- Connection is closed during tool execution, not just on client disconnect
- Server restarts/reconnects after errors, indicating connection instability
- Error code -32000 indicates MCP protocol error (connection closed)
- Related to Phase 19 (MCP Server Crash) but focuses on tool execution failures

**Impact:**

- Tool calls fail unpredictably during execution
- Poor user experience with connection errors
- Workflows blocked by connection closures
- Server instability requiring restarts
- Error handling exists but doesn't prevent tool call failures

## Context

**Related Plans:**

- **Phase 19**: Fix MCP Server Crash - Addresses `BrokenResourceError` in TaskGroup, but doesn't address tool execution failures
- **Phase 31**: Fix optimize_context Stale File Errors - Addresses file reading issues, but not connection problems

**Current Error Handling:**

The server has error handling in `main.py` that catches `BaseExceptionGroup` and `BrokenResourceError`, but this doesn't prevent tool calls from failing when the connection closes during execution.

**Location:** `src/cortex/main.py`, `src/cortex/core/mcp_stability.py`

**Current Implementation:**

1. `main.py` handles `BaseExceptionGroup` and exits gracefully
2. `mcp_stability.py` provides retry logic for connection errors
3. Tool calls use `with_mcp_stability()` wrapper for retry protection

**Issues:**

1. Error handling in `main.py` doesn't prevent tool call failures - it only handles server-level errors
2. Tool execution failures occur before error handling can catch them
3. Connection closure during tool execution isn't properly handled
4. Client-side connection management may be closing connections prematurely
5. No connection health checks before tool execution
6. Retry logic may not be sufficient for connection closure errors

## Approach

### Investigation Steps

1. **Root Cause Analysis**
   - Understand when and why connections close during tool execution
   - Identify if connection closure is server-side or client-side
   - Determine if error handling order is correct
   - Check if tool execution is properly wrapped with error handling
   - Analyze MCP protocol error codes (-32000)

2. **Connection Lifecycle Analysis**
   - Map connection lifecycle during tool execution
   - Identify points where connection can close
   - Determine if connection closure is expected or unexpected
   - Check if tool execution timeouts are causing closures

3. **Error Handling Strategy**
   - Ensure tool execution errors are caught before connection closes
   - Add connection health checks before tool execution
   - Improve retry logic for connection closure errors
   - Add connection recovery mechanisms
   - Distinguish between expected and unexpected closures

### Implementation Steps

1. **Enhance Tool Execution Error Handling**
   - Add connection health checks before tool execution
   - Wrap tool execution with connection-aware error handling
   - Add connection closure detection and recovery
   - Improve error messages to distinguish connection vs. execution errors

2. **Improve Connection Stability**
   - Add connection keepalive mechanisms
   - Implement connection health monitoring
   - Add connection recovery on closure
   - Prevent premature connection closure

3. **Enhance Retry Logic**
   - Add connection closure-specific retry handling
   - Implement exponential backoff for connection errors
   - Add connection recovery before retries
   - Distinguish retryable vs. non-retryable connection errors

4. **Add Diagnostics**
   - Log connection state before tool execution
   - Track connection closure events
   - Add metrics for connection stability
   - Provide diagnostic information in error messages

## Implementation Details

### Step 1: Add Connection Health Checks

**Changes:**

- Add `check_connection_health()` before tool execution
- Verify connection is alive before executing tools
- Fail fast if connection is closed
- Provide clear error messages

**Code Pattern:**

```python
async def execute_tool_with_connection_check(
    func: Callable[..., Awaitable[T]],
    *args: object,
    **kwargs: object,
) -> T:
    """Execute tool with connection health check.
    
    Args:
        func: Tool function to execute
        *args: Positional arguments
        **kwargs: Keyword arguments
        
    Returns:
        Tool execution result
        
    Raises:
        ConnectionError: If connection is closed
    """
    # Check connection health before execution
    health = await check_connection_health()
    if not health.get("healthy", False):
        raise ConnectionError(
            f"Connection not healthy before tool execution: {health}"
        )
    
    # Execute with stability wrapper
    return await with_mcp_stability(func, *args, **kwargs)
```

### Step 2: Enhance Connection Closure Handling

**Changes:**

- Detect connection closure during tool execution
- Add connection recovery mechanisms
- Improve error messages for connection closures
- Add connection state tracking

**Code Pattern:**

```python
async def _handle_connection_closure(
    func_name: str,
    e: Exception,
    attempt: int,
) -> tuple[bool, Exception | None]:
    """Handle connection closure during tool execution.
    
    Args:
        func_name: Name of tool function
        e: Exception that occurred
        attempt: Current retry attempt
        
    Returns:
        Tuple of (should_retry, exception_to_store)
    """
    if isinstance(e, (anyio.BrokenResourceError, ConnectionError)):
        # Check if connection can be recovered
        health = await check_connection_health()
        if health.get("healthy", False):
            logger.warning(
                f"Connection closed during {func_name} execution "
                f"(attempt {attempt}), connection recovered"
            )
            return True, None  # Retry with recovered connection
        else:
            logger.error(
                f"Connection closed during {func_name} execution "
                f"(attempt {attempt}), connection not recoverable"
            )
            return False, e  # Don't retry, connection is dead
    
    return False, e  # Not a connection error
```

### Step 3: Improve Tool Execution Wrapper

**Changes:**

- Add connection health check before execution
- Add connection closure detection during execution
- Improve error handling for connection errors
- Add connection recovery before retries

**Code Pattern:**

```python
async def execute_tool_with_stability(
    func: Callable[..., Awaitable[T]],
    *args: object,
    timeout: float = MCP_TOOL_TIMEOUT_SECONDS,
    **kwargs: object,
) -> T:
    """Execute MCP tool with connection stability and health checks.
    
    Enhanced version that:
    - Checks connection health before execution
    - Detects connection closure during execution
    - Recovers connection before retries
    - Provides clear error messages
    
    Args:
        func: Tool function to execute
        *args: Positional arguments
        timeout: Maximum execution time
        **kwargs: Keyword arguments
        
    Returns:
        Tool execution result
        
    Raises:
        ConnectionError: If connection is closed and not recoverable
        TimeoutError: If execution exceeds timeout
    """
    # Check connection health before execution
    health = await check_connection_health()
    if not health.get("healthy", False):
        raise ConnectionError(
            f"Connection not healthy before tool execution: {health}"
        )
    
    # Execute with enhanced retry logic
    last_exception: Exception | None = None
    func_name = func.__name__
    
    for attempt in range(1, MCP_CONNECTION_RETRY_ATTEMPTS + 1):
        try:
            return await _execute_single_attempt(
                func, semaphore, timeout, args, kwargs
            )
        except Exception as e:
            # Check if connection closure occurred
            should_retry, stored_exception = await _handle_connection_closure(
                func_name, e, attempt
            )
            
            if not should_retry:
                if stored_exception:
                    last_exception = stored_exception
                else:
                    raise  # Non-retryable error
            
            # Connection recovered, retry
            if attempt < MCP_CONNECTION_RETRY_ATTEMPTS:
                await asyncio.sleep(0.1 * attempt)  # Exponential backoff
                continue
    
    # All retries exhausted
    if last_exception:
        raise ConnectionError(
            f"Tool {func_name} failed after {MCP_CONNECTION_RETRY_ATTEMPTS} "
            f"attempts due to connection issues"
        ) from last_exception
    
    raise ConnectionError(f"Tool {func_name} failed unexpectedly")
```

### Step 4: Add Connection State Tracking

**Changes:**

- Track connection state throughout tool execution
- Log connection state changes
- Add connection state to error messages
- Provide diagnostic information

**Code Pattern:**

```python
class ConnectionState:
    """Track connection state for diagnostics."""
    
    def __init__(self) -> None:
        self.last_check: float = 0.0
        self.is_healthy: bool = True
        self.closure_count: int = 0
        self.recovery_count: int = 0
    
    async def check_health(self) -> dict[str, object]:
        """Check connection health and update state."""
        health = await check_connection_health()
        self.last_check = time.time()
        self.is_healthy = health.get("healthy", False)
        return health
    
    def record_closure(self) -> None:
        """Record connection closure event."""
        self.closure_count += 1
        self.is_healthy = False
    
    def record_recovery(self) -> None:
        """Record connection recovery event."""
        self.recovery_count += 1
        self.is_healthy = True
```

## Dependencies

- **Phase 19**: Fix MCP Server Crash - Provides foundation for error handling
- **Connection Health Tool**: Already exists (`check_mcp_connection_health`)
- **MCP Stability Module**: Already exists (`mcp_stability.py`)

## Success Criteria

1. ✅ Tool calls don't fail with "Connection closed" errors during execution
2. ✅ Connection health is checked before tool execution
3. ✅ Connection closures are detected and recovered automatically
4. ✅ Clear error messages distinguish connection vs. execution errors
5. ✅ Connection state is tracked and logged for diagnostics
6. ✅ Retry logic handles connection closures appropriately
7. ✅ Tests pass for all connection error scenarios
8. ✅ Documentation updated with connection handling patterns

## Testing Strategy

### Unit Tests

- Test connection health check before tool execution
- Test connection closure detection during execution
- Test connection recovery mechanisms
- Test retry logic for connection errors
- Test error message clarity

### Integration Tests

- Simulate connection closure during tool execution
- Test connection recovery scenarios
- Verify tool execution succeeds after connection recovery
- Test connection health monitoring
- Verify no resource leaks

### Manual Testing

- Execute tools during connection instability
- Verify connection recovery works
- Check error messages are clear
- Verify connection state tracking
- Test with various connection scenarios

## Risks & Mitigation

### Risk 1: Over-Engineering Connection Handling

**Mitigation:**

- Keep changes minimal and focused
- Reuse existing connection health tool
- Don't add unnecessary complexity
- Test thoroughly before deployment

### Risk 2: Performance Impact

**Mitigation:**

- Connection health checks should be fast (<10ms)
- Cache connection health state
- Don't check on every tool call if not needed
- Monitor performance metrics

### Risk 3: Masking Real Errors

**Mitigation:**

- Distinguish connection errors from execution errors
- Log all connection events for debugging
- Don't retry non-retryable errors
- Maintain clear error messages

### Risk 4: Connection Recovery Failures

**Mitigation:**

- Implement fallback mechanisms
- Add connection recovery timeout
- Fail fast if recovery impossible
- Provide clear error messages

## Timeline

- **Day 1 (2026-01-16)**: Investigation and root cause analysis
- **Day 2 (2026-01-17)**: Implementation and testing

## Notes

- This plan builds on Phase 19 but focuses on tool execution failures
- Connection closure during tool execution is different from server crash
- Error code -32000 is MCP protocol error for connection closed
- Client-side connection management may need investigation
- Consider upstreaming fixes to FastMCP if root cause is in library

## Related Issues

- Phase 19: Fix MCP Server Crash - Related but different issue
- Phase 31: Fix optimize_context Stale File Errors - Different issue but similar error patterns
- MCP Connection Instability (Phase 11) - Historical context
