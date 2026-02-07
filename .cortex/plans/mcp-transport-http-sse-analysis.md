# Plan: Analyze and Consider Alternative MCP Transport (HTTP/SSE)

## Status

- **Status**: PENDING — **Promoted** (recommended for active consideration)
- **Priority**: **High** — Stdio is a poor channel for Cortex MCP; analysis should be prioritized so we can decide on HTTP/SSE or other transport and roadmap implementation.
- **Created**: 2026-02-03
- **Promoted**: 2026-02-07 (post connection-closed investigation)

## Goal

Analyze whether moving the Cortex MCP server from **stdio** to an alternative transport (e.g. **HTTP + SSE** or **Streamable HTTP**) is feasible and desirable to achieve **real request concurrency**, eliminating resource read timeouts and "unknown message ID" errors that occur when the client sends many ReadResource requests while a long-running tool is executing.

## Context

- **Stdio is a poor channel for Cortex MCP**: A single stdio connection is inherently limiting: (1) **Single request at a time** — long tools block all other traffic; (2) **Client-side timeouts** — the client (e.g. Cursor) can close the connection after ~60 s even when the server is sending progress (see investigation `.cortex/plans/archive/Investigations/2026-02-07/investigate-mcp-connection-closed-2026-02-07.md`); (3) **No real concurrency** — ReadResource and other calls queue behind long-running tools, leading to "unknown message ID" and resource read timeouts. Retries and fallbacks mitigate symptoms but do not fix the channel.
- **Current limitation** (documented in `docs/mcp-tool-timeouts.md`): Over stdio, the MCP Python SDK processes one request at a time. When a long tool (e.g. `rules`, `fix_quality_issues`, `fix_markdown_lint`) runs, all ReadResource requests are queued. The client times them out (~5–10 s), cancels them, and later reports "unknown message ID" when the server responds. Mitigations in place: short-TTL cache for structure resources, progress/heartbeat for long tools, and recommendations to retry then fallback on "Connection closed"—but the underlying channel remains fragile.
- **Quote from docs**: "Real concurrency would require a different transport (e.g. HTTP/SSE); for stdio, caching and the recommendations above are the available mitigations."
- **MCP Python SDK**: Supports multiple transports—stdio (current), SSE, and Streamable HTTP. Stdio is single-connection, single-request-at-a-time; HTTP-based transports can support concurrent request handling and connection pooling.
- **Stakeholders**: Users running commit workflows and IDE integrations (e.g. Cursor) that prefetch many resources in parallel; agents that rely on resources for instructions or context.

## Approach

1. **Research**: Confirm MCP Python SDK transport options, API surface, and how HTTP/SSE or Streamable HTTP enable concurrent request handling.
2. **Client compatibility**: Determine whether primary clients (e.g. Cursor) support connecting to Cortex via HTTP/SSE or Streamable HTTP instead of stdio; document any gaps.
3. **Design options**: Outline what a dual-transport or transport-switch would entail (entry point, config, backward compatibility).
4. **Decision**: Produce a go/no-go recommendation with rationale (benefits, cost, risk) and, if go, a high-level implementation path.

No code changes are required in this plan beyond optional spike/prototype in a later phase.

## Implementation Steps

1. **Step 1: SDK transport survey**  
   Review MCP Python SDK docs and source for:
   - Supported transports (stdio, SSE, Streamable HTTP) and how to run the server with each.
   - Whether HTTP/SSE (or Streamable HTTP) allows the server to handle multiple requests concurrently (e.g. one request per connection or multiplexed).
   - Any breaking API differences between stdio and HTTP transports for tool/resource handlers.

2. **Step 2: Client compatibility matrix**  
   Document which clients are in scope (e.g. Cursor, CLI, other IDEs):
   - How each connects to MCP servers (stdio only vs HTTP/SSE capable).
   - If Cursor (or primary client) only supports stdio for local MCP servers, note that as a blocker or constraint for adoption of an alternative transport.

3. **Step 3: Concurrency and behavior**  
   Clarify expected behavior with HTTP/SSE (or chosen transport):
   - Can the server process ReadResource while a CallTool is in progress?
   - Connection lifecycle (single long-lived connection vs request-scoped).
   - Impact on existing timeouts, progress reporting, and usage tracking.

4. **Step 4: Design options document**  
   Write a short design note (e.g. in `docs/` or plan appendix) with:
   - **Option A**: Stdio only (current); keep relying on caching and recommendations.
   - **Option B**: Add optional HTTP/SSE (or Streamable HTTP) server alongside stdio; config or env to choose transport.
   - **Option C**: Switch default to HTTP/SSE where client supports it; keep stdio as fallback.
   - Trade-offs: deployment (port, process model), client support, complexity, security (exposed port vs stdio).

5. **Step 5: Recommendation and roadmap**  
   - Publish recommendation (go/no-go) and rationale.
   - If go: add a follow-up plan for implementation (entry point, config, tests, docs) and place it in the roadmap. If no-go: update `docs/mcp-tool-timeouts.md` to state that stdio remains the supported transport and reference this analysis.

## Dependencies

- MCP Python SDK version and transport documentation/source.
- Cursor (and any other primary client) documentation or behavior for MCP transport options.
- No dependency on other in-repo plans; can run in parallel with Phase 43/45/68.

## Success Criteria

- Documented summary of MCP SDK transport options and concurrency behavior.
- Client compatibility matrix for stdio vs HTTP/SSE (or Streamable HTTP).
- Design options document with trade-offs.
- Clear recommendation (go/no-go) and, if go, a follow-up implementation plan referenced in the roadmap.

## Technical Design

- **Scope**: Analysis and design only; implementation is out of scope unless follow-up plan is created.
- **Deliverables**: Markdown docs (in repo or plan appendix); optional spike branch with minimal HTTP/SSE server run (no production path changes without follow-up plan).
- **Architecture**: Current Cortex entry point is `mcp.run(transport="stdio")` in `src/cortex/main.py`. Alternative transport would require a second entry point or transport selection (e.g. env `CORTEX_MCP_TRANSPORT=stdio|sse`) and possibly a new module for HTTP/SSE setup (host, port, middleware).

## Testing Strategy

- **Analysis phase**: No new production code; no new unit/integration tests required.
- **If follow-up implementation**: Testing strategy for that plan MUST include:
  - Unit tests for transport selection and server bootstrap.
  - Integration tests: server starts with chosen transport; tools and resources respond over that transport.
  - Concurrency test: while one long tool runs, ReadResource requests complete without client timeout (when client supports concurrent requests).
  - Minimum 95% coverage for new code; AAA pattern; no blanket skips.

## Risks & Mitigation

- **Risk**: Primary client (Cursor) does not support HTTP/SSE for local MCP → limited benefit.  
  **Mitigation**: Document in compatibility matrix; recommendation may be "no-go" or "defer until client support exists."
- **Risk**: Exposing Cortex over HTTP introduces network/security concerns.  
  **Mitigation**: Design options must address binding (localhost-only, port), auth, and deployment context.
- **Risk**: Maintaining two code paths (stdio + HTTP) increases complexity.  
  **Mitigation**: Design for shared handler layer; transport as pluggable entry point only.

## Timeline

- Analysis (Steps 1–5): 1–2 sprints (estimate).
- Implementation: Not in scope; follow-up plan if recommendation is go.

## Notes

- This plan was created in response to the note in `docs/mcp-tool-timeouts.md`: "Real concurrency would require a different transport (e.g. HTTP/SSE); for stdio, caching and the recommendations above are the available mitigations."
- **Promotion rationale (2026-02-07)**: Stdio is a poor fit for Cortex MCP. The connection-closed investigation showed the client closing the connection after ~56 s during `fix_markdown_lint` despite server progress/heartbeat—a client-side timeout over a single stdio channel. Promoting this analysis plan ensures we explicitly evaluate HTTP/SSE (or Streamable HTTP) and either roadmap implementation or document a no-go with clear rationale.
- Related: Phase 68 (connection closed / fix_quality_issues), investigation `investigate-mcp-connection-closed-2026-02-07` (archived), Phase 19 (stdio BrokenResourceError), and resource read timeouts / "unknown message ID" behavior are all constrained by sequential stdio processing; alternative transport is the only way to achieve true request concurrency and more robust long-running tools at the server.
