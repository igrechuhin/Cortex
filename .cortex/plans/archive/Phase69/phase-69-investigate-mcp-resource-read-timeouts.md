# Phase 69: Investigate and fix MCP resource read timeouts (-32001)

## Status

- **Status**: COMPLETE
- **Priority**: Blocker (ASAP)
- **Created**: 2026-02-04
- **Goal**: Resolve `MCP error -32001: Request timed out` when reading Cortex MCP resources so that resource reads complete reliably under normal and parallel load.

## Context

Users observe repeated timeouts when the IDE/client reads Cortex MCP **resources** (not tools). Error log sample (2026-02-04):

```text
Error reading resource 'cortex://memory-bank/stats': MCP error -32001: Request timed out
Error reading resource 'cortex://links/graph': MCP error -32001: Request timed out
Error reading resource 'cortex://usage/unused': MCP error -32001: Request timed out
Error reading resource 'cortex://usage/report': MCP error -32001: Request timed out
Error reading resource 'cortex://scripts/list': MCP error -32001: Request timed out
Error reading resource 'cortex://usage/optimization-recommendations': MCP error -32001: Request timed out
Error reading resource 'cortex://scripts/analyze': MCP error -32001: Request timed out
Error reading resource 'cortex://synapse/prompts': MCP error -32001: Request timed out
Error reading resource 'cortex://links/validate': MCP error -32001: Request timed out
Error reading resource 'cortex://optimization/context-effectiveness': MCP error -32001: Request timed out
Error reading resource 'cortex://usage/stats': MCP error -32001: Request timed out
```

Phase 68 (fix_quality_issues connection closed) documents that resource read timeouts (-32001) can occur when the client fetches many resources in parallel while a long tool is running: requests queue behind the tool, the client times them out, then the server responds later. That explanation does not remove the user impact: when the client opens a resource-heavy UI (e.g. memory bank stats, link graph, usage, scripts, synapse prompts), multiple resource reads are issued; if they consistently time out, the feature is broken. This plan treats -32001 on resource reads as an ASAP blocker and defines investigation and fixes.

## Goal

- **Primary**: Identify root cause(s) of MCP resource read timeouts (-32001) for the listed URIs and implement server- or client-side mitigations so resource reads complete within client expectations.
- **Secondary**: Document when to prefer tools over resources and any client-side best practices to avoid timeout storms.

## Approach

1. **Reproduce and measure**: Reproduce timeout scenario (e.g. client fetching many resources in parallel; or single slow resource). Measure client timeout value (if discoverable), server-side handler duration per resource, and effect of shared semaphore/queue.
2. **Root cause**: Classify causes: (a) client timeout shorter than server handler duration, (b) server handler genuinely slow, (c) queueing behind other tools/resources, (d) cold start / manager initialization delay.
3. **Server-side**: Ensure every resource handler uses `@mcp_resource_wrapper(timeout=...)` with a timeout at least as large as typical handler duration; consider raising timeouts for known-heavy resources. Optimize any handler that exceeds client timeout. Optionally add lightweight caching or faster paths for hot resources.
4. **Documentation**: Update docs (e.g. `docs/mcp-tool-timeouts.md`) with a "Resource read timeouts (-32001)" section: cause, server timeouts, client behavior, and recommendation to prefer tools when bulk data is needed during commit or long operations.
5. **Validation**: Re-test with parallel resource reads and confirm timeouts are eliminated or reduced to acceptable rate.

## Implementation Steps

1. **Audit resource handlers and timeouts**  
   List all `@mcp.resource()` handlers and their `@mcp_resource_wrapper(timeout=...)` values. Map each URI from the error log to handler and timeout (e.g. cortex://memory-bank/stats → get_memory_bank_stats_resource, MCP_TOOL_TIMEOUT_MEDIUM). Document in the plan or a short audit doc.

2. **Measure handler duration**  
   For each resource that timed out, add or use existing metrics/logging to measure p50/p95 duration. Run under load (e.g. 10+ parallel resource reads). Identify handlers that exceed 30–60s (typical client timeout guess) or that have high variance.

3. **Identify client timeout**  
   If possible, determine the client/IDE timeout for resource read requests (e.g. from docs, config, or experiments). If not configurable, use a conservative server target (e.g. all resource handlers complete in &lt; 45s under normal load).

4. **Align server timeouts and optimize slow handlers**  
   Ensure server-side timeout &gt;= measured p95 duration and &gt;= client timeout. For any handler that exceeds client timeout: optimize (reduce work, cache, lazy init) or split into lighter resources. Raise `mcp_resource_wrapper(timeout=...)` only where necessary to match reality; avoid masking slow logic with very large timeouts.

5. **Concurrency and queueing**  
   Review whether resource handlers share a global semaphore with tools and whether queueing causes head-of-line blocking. If so, consider separate concurrency limits for resources vs tools, or document that parallel resource fetches may queue and suggest client-side staggering or lower concurrency.

6. **Documentation**  
   Add or extend "Resource read timeouts (-32001)" in `docs/mcp-tool-timeouts.md`: root cause (client timeout, queueing, slow handler), server timeout strategy, and guidance (prefer tools for bulk operations; avoid opening many resources in parallel during long tool runs).

7. **Verification**  
   Re-run the scenario that produced the log (e.g. IDE opening all listed resources). Confirm timeouts are gone or rare; add or run integration test that performs parallel resource reads and asserts success or acceptable failure rate.

## Dependencies

- Phase 43 (resources registration): resource handlers and `mcp_resource_wrapper` already in place.
- Phase 68 and `docs/mcp-tool-timeouts.md`: existing context on -32001 and "unknown message ID"; this plan deepens the fix for resource reads specifically.

## Success Criteria

- No systematic -32001 timeouts when the client reads the listed resources (cortex://memory-bank/stats, cortex://links/graph, cortex://usage/*, cortex://scripts/*, cortex://synapse/prompts, cortex://links/validate, cortex://optimization/context-effectiveness) under normal and parallel load.
- All resource handlers have explicit, justified timeouts and, where needed, optimizations so they complete within client expectations.
- Documentation clearly explains resource timeout cause and mitigations; agents and users know to prefer tools when appropriate.

## Technical Design

- **Resource wrapper**: Existing `mcp_resource_wrapper(timeout=...)` in `mcp_stability.py` applies `with_mcp_stability(..., kind="resource")`. No change to wrapper contract; only timeout values and handler logic.
- **Constants**: Use existing `cortex.core.constants` (MCP_TOOL_TIMEOUT_FAST/MEDIUM/COMPLEX). Add a resource-specific constant only if we need a different default (e.g. `MCP_RESOURCE_TIMEOUT_DEFAULT`).
- **Observability**: Optional: log resource handler duration at debug level to confirm p95 in production.

## Testing Strategy

- **Coverage target**: ≥95% for any new or modified logic (timeout constants, resource handler changes, new docs).
- **Unit tests**: Any new helper or constant; existing resource handler tests still pass.
- **Integration tests**: Add or extend test that performs multiple parallel resource reads (e.g. 5–10 URIs) and asserts all succeed within a generous overall timeout (e.g. 120s), or document acceptable failure rate if client timeout is not under our control.
- **Regression**: Confirm existing tool and resource tests pass; no regression in tool timeout behavior (Phase 68).

## Risks & Mitigation

- **Client timeout unknown**: If client timeout cannot be determined, set server timeouts to a conservative value (e.g. 45–60s) and optimize handlers to stay under it.
- **Queueing unavoidable**: If MCP protocol or client always queues resource requests behind tools, document and recommend reducing parallel resource fetches or using tools for bulk data.

## Timeline

- Investigation and audit: 0.5–1 day.
- Handler optimization and timeout alignment: 0.5–1 day.
- Docs and verification: 0.5 day.

## Notes

- Error code -32001 is the standard MCP "Request timed out" response.
- The listed URIs map to handlers in: phase1_foundation_stats (memory-bank/stats), link_graph_operations (links/graph), usage_analytics (usage/*), script_capture_tools (scripts/*), synapse_tools (synapse/prompts), link_validation_operations (links/validate), context_analysis_handlers (optimization/context-effectiveness). All use `mcp_resource_wrapper` with FAST/MEDIUM/COMPLEX timeouts.
