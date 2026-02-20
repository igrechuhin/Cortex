# Session Optimization: Step 12.7 MCP Connection Stability Enhancements

**Status**: PENDING

**Created**: 2026-02-19

## Goal

Enhance MCP connection stability for Step 12.7 (tests with coverage validation) in the commit pipeline to prevent commit blocks due to connection closure during long-running test execution.

## Context

During commit pipeline execution, Step 12.7 (`execute_pre_commit_checks(checks=["tests"])`) failed with MCP error -32000 ("Connection closed") during execution. The retry attempt failed with "tools not found" error, indicating complete MCP server disconnection. Per commit pipeline rules, Step 12.7 MUST execute successfully in Step 12 with no fallback allowed, so the commit was correctly blocked.

**Root causes identified**:

1. Client-side timeout during long tool execution (test_timeout=600s may exceed client timeout)
2. No fallback mechanism for Step 12.7 (by design for commit safety)
3. MCP server recovery not automatic after connection closure

**Related work**:

- "Session Optimization: MCP Connection Stability and Fallback Script Improvements" (COMPLETE 2026-02-19) - addressed general connection stability and fallback scripts
- This plan focuses specifically on Step 12.7 enhancements

## Approach

Implement three high-priority enhancements:

1. Connection health check before Step 12.7 execution
2. Enhanced retry logic with exponential backoff
3. Connection stability monitoring for long-running operations

## Steps

### Step 1: Add Connection Health Check Before Step 12.7

**Target**: Commit prompt Step 12.7.1 (before test execution)

**Implementation**:

- Add explicit `check_mcp_connection_health()` call immediately before Step 12.7 execution
- If health check fails or returns unhealthy:
  - Wait 2-5 seconds
  - Retry health check once
  - If still unhealthy, block commit with clear message: "MCP connection unhealthy before Step 12.7. Please reconnect Cortex MCP server and re-run commit pipeline."
- Document in commit prompt that health check is mandatory before Step 12.7

**Files to modify**:

- `.cortex/synapse/prompts/commit.md` - Add health check step before Step 12.7.1

**Testing**:

- Unit test: Health check failure blocks commit
- Integration test: Health check success allows Step 12.7 to proceed

### Step 2: Enhanced Retry Logic for Step 12.7

**Target**: Commit prompt Step 12.7 connection error handling

**Implementation**:

- Current behavior: Retry once immediately on connection error
- Enhanced behavior: Exponential backoff retry (2s delay, then 5s delay)
  - First retry: Wait 2 seconds, retry `execute_pre_commit_checks(checks=["tests"])`
  - Second retry (if first fails): Wait 5 seconds, retry again
  - If both retries fail: Block commit with message: "Step 12.7 failed after retries. Please reconnect MCP server and re-run commit pipeline."
- Document retry behavior in commit prompt

**Files to modify**:

- `.cortex/synapse/prompts/commit.md` - Update Step 12.7 connection error handling section

**Testing**:

- Unit test: Retry logic with delays
- Integration test: Connection closure recovery via retry

### Step 3: Connection Stability Monitoring

**Target**: MCP stability module (`mcp_stability.py`)

**Implementation**:

- Log connection health metrics before and after long-running tool calls
- Specifically for `execute_pre_commit_checks(checks=["tests"])`:
  - Record health status before execution
  - Record health status after execution (if successful)
  - Record connection error details if execution fails
- Store metrics in usage context or dedicated connection stability log
- Use metrics to identify patterns:
  - Timeout thresholds (when do connections close relative to execution time?)
  - Concurrent operation limits (does semaphore usage correlate with failures?)
  - Client vs server-side timeouts

**Files to modify**:

- `src/cortex/core/mcp_stability.py` - Add connection health logging
- `src/cortex/tools/pre_commit_tools.py` - Log health before/after test execution

**Testing**:

- Unit test: Health metrics recorded correctly
- Integration test: Metrics available for analysis

### Step 4: Documentation Updates

**Target**: `docs/guides/troubleshooting.md`

**Implementation**:

- Add subsection "Step 12.7 Timeout and Connection Requirements"
- Document:
  - Expected test execution time (up to 600s)
  - Client-side timeout requirements
  - How to increase client timeout if needed
  - Connection health check before Step 12.7
  - Retry behavior and when to reconnect MCP

**Files to modify**:

- `docs/guides/troubleshooting.md` - Add Step 12.7 timeout documentation

## Dependencies

- `check_mcp_connection_health` MCP tool (already exists)
- `mcp_stability.py` connection health utilities (already exists)
- Commit prompt structure (already supports health checks)

## Success Criteria

1. ✅ Connection health check executes before Step 12.7
2. ✅ Enhanced retry logic with exponential backoff implemented
3. ✅ Connection stability metrics logged for long-running operations
4. ✅ Documentation updated with Step 12.7 timeout requirements
5. ✅ All tests pass (95%+ coverage)
6. ✅ Quality gate passes (no violations)

## Testing Strategy

**Unit tests**:

- Health check failure blocks commit
- Health check success allows Step 12.7
- Retry logic with delays
- Connection health logging

**Integration tests**:

- Full commit pipeline with health check
- Connection closure recovery via retry
- Metrics collection during test execution

**Coverage target**: 95%+

## Risks

- **Risk**: Health check adds latency to commit pipeline
  - **Mitigation**: Health check is fast (<1s); latency acceptable for reliability gain

- **Risk**: Retry delays extend commit pipeline duration
  - **Mitigation**: Retries only occur on failure; successful runs unaffected

- **Risk**: Metrics collection adds overhead
  - **Mitigation**: Logging is lightweight; impact minimal

## Timeline

- **Step 1**: 1-2 hours (health check implementation)
- **Step 2**: 1-2 hours (retry logic enhancement)
- **Step 3**: 2-3 hours (monitoring implementation)
- **Step 4**: 1 hour (documentation)
- **Testing**: 2-3 hours (unit + integration tests)

**Total estimate**: 7-11 hours

## Notes

- This plan complements the completed "Session Optimization: MCP Connection Stability and Fallback Script Improvements" plan
- Focus is specifically on Step 12.7 reliability, not general connection stability
- No fallback mechanism for Step 12.7 is intentional (by design for commit safety)
- Recommendations based on end-of-session analysis: `.cortex/reviews/session-optimization-2026-02-19T22-35.md`
