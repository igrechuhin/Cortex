# Phase 86: MCP Connection Resilience and Auto-Recovery

**Status**: PENDING
**Priority**: High
**Complexity**: High
**Category**: Fix / Infrastructure

## Goal

Add automatic MCP connection recovery so that agent sessions are not blocked by transient connection drops. Currently, MCP disconnections require manual user intervention to reconnect.

## Context

- MCP connection instability was the **single most disruptive recurring issue** across all analyzed chat sessions.
- In commit discussion-15, a full commit pipeline was halted because MCP disconnected mid-pipeline and the agent had to ask the user to reconnect manually.
- Multiple sessions show "connection closed" errors followed by "Not connected" on retry.
- The `mcp_stability.py` module already has retry logic for individual tool calls, but no reconnection logic at the transport level.
- Current behavior: agent detects unhealthy MCP → stops → asks user to reconnect → user says "proceed" → works.

## Approach

1. Add transport-level reconnection to the MCP client.
2. Implement exponential backoff reconnection with configurable limits.
3. Add a health-check loop that proactively detects connection loss.
4. Ensure the retry wrapper in `mcp_stability.py` triggers reconnection on connection-level errors.

## Implementation Steps

### Step 1: Analyze current transport layer

- Read `mcp_stability.py`, `mcp_stability_usage.py`, `mcp_stability_finalize.py`, and `mcp_failure_handler.py`.
- Identify where connection state is managed.
- Map error types: transient (reconnectable) vs permanent (fatal).

### Step 2: Implement reconnection logic

- Add `reconnect()` method to the MCP client/transport layer.
- Implement exponential backoff: 1s, 2s, 4s, max 30s, max 5 attempts.
- Add connection state machine: `connected` → `reconnecting` → `connected`/`failed`.

### Step 3: Wire reconnection into retry wrapper

- In `_run_with_retry_and_record`, detect connection-level errors (e.g., `ConnectionError`, "connection closed", "Not connected").
- Trigger reconnection before retry.
- Distinguish connection errors from tool-level errors.

### Step 4: Add proactive health monitoring

- Add periodic (every 60s) lightweight health check ping during active sessions.
- If health check fails, trigger reconnection proactively.

### Step 5: Add circuit breaker

- After N consecutive reconnection failures, enter "degraded mode" instead of infinite retries.
- In degraded mode, log warnings and allow graceful fallback (e.g., skip non-critical MCP operations).

### Step 6: Update session start to handle reconnection

- `session_start_impl` should attempt reconnection if MCP is unhealthy before giving up.
- Commit pipeline should auto-retry on connection errors rather than stopping.

## Verification Checklist

| What to search for | Scope | Expected result |
|---|---|---|
| `reconnect` | `src/cortex/core/mcp_stability*.py` | Implementation present |
| `"Not connected"` hard stop | Commit/implement prompts | Replaced with auto-recovery |

## Dependencies

- None.

## Success Criteria

- Transient MCP disconnections are recovered automatically without user intervention.
- Commit pipeline completes even if MCP has a brief disconnect mid-pipeline.
- After 5 failed reconnection attempts, graceful degradation with clear message.
- No infinite reconnection loops.

## Testing Strategy

- **Coverage Target**: 95%+ for reconnection logic.
- **Unit Tests**: Mock connection errors and verify reconnection attempts.
- **Integration Tests**: Simulate connection drop during tool call and verify recovery.
- **Edge Cases**: Test max retries, concurrent reconnection attempts, rapid disconnects.
- **AAA Pattern**: All tests follow Arrange-Act-Assert.

## Risks & Mitigation

- **Risk**: Reconnection during active operation causes data corruption. **Mitigation**: Use idempotent operations; reconnect only between tool calls.
- **Risk**: Infinite reconnection loop. **Mitigation**: Circuit breaker with max attempts.

## Timeline

- Estimated: 1–2 days.
