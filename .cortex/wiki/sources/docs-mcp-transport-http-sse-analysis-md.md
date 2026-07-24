# MCP Transport HTTP/SSE Analysis

**Status**: Completed (2026-02-07)  
**Plan**: [.cortex/plans/mcp-transport-http-sse-analysis.md](../.cortex/plans/archive/Design/mcp-transport-http-sse-analysis.md)

## Summary

This document analyzes whether moving the Cortex MCP server from **stdio** to an alternative transport (**HTTP + SSE** or **Streamable HTTP**) is feasible and desirable to achieve real request concurrency and eliminate resource read timeouts and "unknown message ID" errors.

**Recommendation**: **Go** — Add optional HTTP/SSE (or Streamable HTTP) server alongside stdio; keep stdio as default. See [Recommendation and roadmap](#5-recommendation-and-roadmap) and [Design options](#4-design-options-document).

---

## 1. SDK transport survey

### 1.1 MCP Python SDK (Cortex dependency)

- **Package**: `mcp>=1.26.0` (pyproject.toml)
- **Server surface**: Cortex uses `FastMCP` from `mcp.server.fastmcp` and runs via `mcp.run(transport=..., mount_path=...)` in `src/cortex/main.py`.

### 1.2 Supported transports

| Transport            | Literal value          | Description |
|----------------------|------------------------|-------------|
| **Stdio**            | `'stdio'`              | Default. Single process, stdin/stdout. One request at a time over one connection. |
| **SSE**              | `'sse'`                 | HTTP + Server-Sent Events. Can be mounted on an ASGI app (e.g. Starlette). |
| **Streamable HTTP**  | `'streamable-http'`     | Recommended by MCP (protocol 2025-03-26). HTTP with streaming; supports concurrent request handling. |

**API** (from installed SDK):

```python
# FastMCP.run signature
def run(
    self,
    transport: Literal['stdio', 'sse', 'streamable-http'] = 'stdio',
    mount_path: str | None = None,
) -> None: ...
```

- **Stdio**: No `mount_path`. Server runs as a single process; client spawns it and talks over stdin/stdout.
- **SSE / Streamable HTTP**: Typically use `mount_path` (e.g. `"/mcp"` or `"/sse"`). SDK modules: `mcp.server.sse`, `mcp.server.streamable_http`, `mcp.server.streamable_http_manager`, `mcp.server.transport_security`.

### 1.3 Concurrency behavior

- **Stdio**: Single bidirectional stream. The MCP Python SDK processes **one request at a time** over that stream. Long-running tools block all other traffic (ReadResource, ListTools, etc.). This is the root cause of resource read timeouts and "unknown message ID" when the client cancels queued requests.
- **HTTP-based (SSE / Streamable HTTP)**: Each HTTP request can be handled independently. The server can **process multiple requests concurrently** (e.g. one long CallTool and several ReadResource requests on separate connections or request contexts). Concurrency is transport-dependent and implementation-dependent; the SDK’s HTTP transports are designed to allow concurrent handling.

### 1.4 Handler API

- Tool and resource handlers are registered on the same `FastMCP` instance. There are **no breaking API differences** for handlers between stdio and HTTP transports; only the entry point and transport layer change.

---

## 2. Client compatibility matrix

| Client / context        | Stdio (command)     | SSE (URL)           | Streamable HTTP (URL) |
|-------------------------|---------------------|---------------------|------------------------|
| **VS Code-based MCP clients** | ✅ Supported (default). Configure command, args, env in MCP settings. | ✅ Supported. URL form: `http(s)://host:port/sse?token=...`. | ✅ Supported via MCP Inspector at `http://localhost:8000/mcp`; VS Code-based clients can connect to URL-based servers. |
| **MCP Inspector**       | ✅ Subprocess        | ✅ URL               | ✅ URL (e.g. `/mcp`)   |
| **Claude Desktop**      | ✅ Typical           | ❌ Not primary       | ❌ Not primary          |
| **Other IDEs / CLI**    | ✅ Common (subprocess) | Depends on client   | Depends on client      |

**Conclusion**: Common VS Code-based MCP clients support both stdio (command) and SSE/URL. Using HTTP/SSE or Streamable HTTP is **not blocked** by those clients; users can run Cortex as a long-lived server and connect via URL instead of a shell command.

---

## 3. Concurrency and behavior with HTTP/SSE

### 3.1 Expected behavior

- **ReadResource during CallTool**: With an HTTP-based transport, the server can handle **ReadResource** (and other requests) on separate HTTP connections or request contexts while a **CallTool** is in progress. This removes the “queued behind one long tool” behavior that causes client-side timeouts and "unknown message ID".
- **Connection lifecycle**: SSE typically uses a long-lived connection for server→client events; request/response can be request-scoped or multiplexed depending on implementation. Streamable HTTP is request-oriented. Both allow multiple concurrent requests compared to a single stdio pipe.
- **Timeouts and progress**: Existing tool timeouts (`@mcp_tool_wrapper`, constants in `cortex.core.constants`) and progress/heartbeat behavior remain valid; they are independent of transport. Usage tracking and analytics can remain as-is.

### 3.2 Impact on current mitigations

- **Short-TTL resource cache** (`cortex://structure/info`, `cortex://structure/health`): Still useful to reduce load; concurrency makes it less critical for avoiding timeouts.
- **Progress/heartbeat for long tools**: Still recommended to reduce client-side idle timeouts.
- **Recommendations in docs** (prefer tools over resources during long workflows, avoid resource-heavy UI during long tools): Remain good practice; with HTTP transport they are less mandatory to avoid "unknown message ID".

---

## 4. Design options document

### Option A: Stdio only (current)

- **Description**: Keep `mcp.run(transport="stdio")` as the only supported transport. Continue relying on caching, progress/heartbeat, and user-facing recommendations.
- **Pros**: No deployment or security changes; no extra process or port.  
- **Cons**: Single-request-at-a-time; resource read timeouts and "unknown message ID" remain when a long tool runs; client connection closed after ~60 s during long tools (as observed in connection-closed investigation).

### Option B: Add optional HTTP/SSE (or Streamable HTTP) alongside stdio

- **Description**: Introduce a second entry point or env-driven transport selection (e.g. `CORTEX_MCP_TRANSPORT=stdio|sse|streamable-http`). When not stdio, run an HTTP server (e.g. uvicorn + Starlette) with the MCP app mounted at a path (e.g. `/sse` or `/mcp`). Keep stdio as default.
- **Pros**: Real concurrency; VS Code-based MCP clients and Inspector can connect via URL; stdio remains for local/CLI and Claude Desktop.  
- **Cons**: Deployment complexity (port, process model); security (bind address, auth, token); optional dependencies (e.g. `uvicorn`, `starlette` already in `[server]` optional deps).
- **Trade-offs**: Binding to localhost-only and optional token mitigates exposure; documentation and defaults can keep stdio-first.

### Option C: Switch default to HTTP/SSE where client supports it; stdio fallback

- **Description**: Prefer HTTP/SSE (or Streamable HTTP) as default when running in “server mode” (e.g. when a port is configured), and use stdio only when no port is set or when explicitly requested.
- **Pros**: Maximizes concurrency for URL-based clients.  
- **Cons**: More complex default behavior; all Option B deployment/security considerations apply.

**Recommendation**: **Option B** — Add optional HTTP/SSE (or Streamable HTTP) alongside stdio, keep stdio as default. Option C can be a later refinement once Option B is in production.

---

## 5. Recommendation and roadmap

### 5.1 Recommendation: **Go**

- **Rationale**:
  - SDK supports `sse` and `streamable-http` out of the box; no new transport implementation required.
  - Common VS Code-based MCP clients support SSE/URL; adoption is not blocked by the primary client.
  - Concurrency would address resource read timeouts, "unknown message ID", and connection-closed issues during long tools.
  - Option B keeps backward compatibility and allows incremental rollout.

### 5.2 If go: follow-up implementation plan

A follow-up plan should cover:

- **Entry point / config**: Env (e.g. `CORTEX_MCP_TRANSPORT`, `CORTEX_MCP_PORT`, `CORTEX_MCP_HOST`) or CLI flag to choose transport and bind address.
- **Server bootstrap**: Use existing optional deps (`uvicorn`, `starlette`) to run ASGI app with MCP mounted; or document how to run with `mcp.run(transport="sse"|"streamable-http", mount_path=...)` in a custom ASGI app.
- **Security**: Default bind to localhost; optional auth (e.g. query token for SSE URL) and documentation.
- **Tests**: Unit tests for transport selection and server bootstrap; integration tests that server starts and tools/resources respond over chosen transport; concurrency test (e.g. ReadResource completes while a long tool runs when client supports concurrent requests).
- **Docs**: Update `docs/mcp-tool-timeouts.md` to describe HTTP/SSE option and when it helps; add a short deployment/configuration section.

This analysis does **not** implement the above; it only recommends adding a follow-up plan to the roadmap and, when implemented, updating the timeout doc accordingly.

### 5.3 If no-go (for reference)

Had the recommendation been no-go, the next step would be to update `docs/mcp-tool-timeouts.md` to state that stdio remains the only supported transport and to reference this analysis.

---

## References

- Plan: [.cortex/plans/mcp-transport-http-sse-analysis.md](../.cortex/plans/archive/Design/mcp-transport-http-sse-analysis.md)
- Current timeout and connection behavior: [docs/mcp-tool-timeouts.md](mcp-tool-timeouts.md)
- Connection-closed investigation (archived): `.cortex/plans/archive/Investigations/2026-02-07/investigate-mcp-connection-closed-2026-02-07.md`
- MCP Python SDK: [modelcontextprotocol.github.io/python-sdk](https://modelcontextprotocol.github.io/python-sdk/)
- MCP client transport support (stdio + SSE URL): client documentation and community resources
