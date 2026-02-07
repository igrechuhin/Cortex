# Plan: Gradual Migration to Option C — HTTP/SSE Default Where Client Supports It; Stdio Fallback

## Status

- **Status**: PENDING
- **Priority**: **Blocker (ASAP)**
- **Created**: 2026-02-07
- **Updated**: 2026-02-07 (reframed as Option C gradual migration)
- **Depends on**: [docs/mcp-transport-http-sse-analysis.md](../docs/mcp-transport-http-sse-analysis.md) (completed)

## Goal

**End state (Option C)**: Prefer HTTP/SSE (or Streamable HTTP) as default when running in “server mode” (e.g. when a port is configured); use stdio only when no port is set or when explicitly requested. Achieve this via a **gradual migration** so existing users keep stdio behavior until they opt in or adopt server mode.

## Context

- **Analysis**: [docs/mcp-transport-http-sse-analysis.md](../docs/mcp-transport-http-sse-analysis.md) documents Option A (stdio only), Option B (optional HTTP/SSE alongside stdio), and **Option C** (switch default to HTTP/SSE where client supports it; stdio fallback). This plan implements Option C through two phases.
- **Why Option C**: Maximizes concurrency for URL-based clients (Cursor, Inspector), removes resource read timeouts and "unknown message ID" when clients use server/URL mode, while preserving stdio for CLI and environments where no port is configured.
- **SDK**: `FastMCP.run(transport="stdio"|"sse"|"streamable-http", mount_path=...)`; optional deps `uvicorn`, `starlette` in pyproject `[server]`. Cursor supports SSE URL and Streamable HTTP.

## Approach

Two-phase gradual migration:

- **Phase 1 (Option B)**: Add optional HTTP/SSE (or Streamable HTTP) alongside stdio; keep stdio as default. No behavior change for current users.
- **Phase 2 (Option C)**: Switch default to HTTP/SSE when “server mode” is active (e.g. port configured); use stdio when no port or when explicitly requested. Document client support and fallback behavior.

## Implementation Steps (implementation sequence)

Execute in order; each step builds on the previous.

### Phase 1: Optional HTTP/SSE alongside stdio (Option B)

1. **Entry point and config**
   - Add env (e.g. `CORTEX_MCP_TRANSPORT=stdio|sse|streamable-http`, `CORTEX_MCP_PORT`, `CORTEX_MCP_HOST`) or CLI flags to choose transport and bind address.
   - Default: `stdio` when `CORTEX_MCP_PORT` is unset; no breaking change.

2. **Server bootstrap**
   - When transport is `sse` or `streamable-http`: run HTTP server (uvicorn + Starlette) with MCP app mounted at a path (e.g. `/sse` or `/mcp`).
   - Reuse existing `cortex.server.mcp` (FastMCP instance); no handler API changes.

3. **Security (Phase 1)**
   - Bind to localhost by default; optional auth (e.g. query token for SSE URL).
   - Document binding and auth in deployment/configuration docs.

4. **Tests (Phase 1)**
   - Unit: transport selection and server bootstrap from config/env.
   - Integration: server starts with chosen transport; tools and resources respond over HTTP.
   - Concurrency: ReadResource completes while a long CallTool runs over HTTP (mock client or Inspector).
   - Coverage: ≥95% for new code; AAA; no blanket skips.

5. **Docs (Phase 1)**
   - Update `docs/mcp-tool-timeouts.md`: describe HTTP/SSE option and when it helps; add deployment/configuration section.
   - Reference analysis doc.

### Phase 2: Default to HTTP/SSE in server mode; stdio fallback (Option C)

1. **Default behavior (Option C)**
   - When `CORTEX_MCP_PORT` (or equivalent) is set: default transport to `sse` (or `streamable-http`) instead of stdio, unless `CORTEX_MCP_TRANSPORT=stdio` is set.
   - When port is not set: keep stdio as default (no change for CLI / subprocess clients).
   - Explicit override: `CORTEX_MCP_TRANSPORT=stdio` forces stdio even when port is set (fallback for clients that do not support URL).

2. **Client support detection (optional, best-effort)**
   - Document that “client supports it” means URL-based connection (e.g. Cursor with SSE URL). No runtime client detection required; “server mode” (port set) is the proxy for URL-based clients.
   - Optional: log or document recommended Cursor/IDE config when running in server mode.

3. **Tests (Phase 2)**
   - Unit: default transport selection when port set vs unset; override via `CORTEX_MCP_TRANSPORT=stdio`.
   - Integration: default behavior with port set uses HTTP transport; with port unset uses stdio.
   - Regression: existing stdio-only usage paths unchanged when port not set.

4. **Docs (Phase 2)**
   - Update docs to state Option C: default is HTTP/SSE when server mode (port configured), stdio when not; document fallback and override.
   - Update `docs/mcp-tool-timeouts.md` and deployment section accordingly.

## Dependencies

- Completed: [docs/mcp-transport-http-sse-analysis.md](../docs/mcp-transport-http-sse-analysis.md).
- No other plan blockers.

## Success Criteria

- **Phase 1**: Stdio remains default when port unset; with transport set to `sse`/`streamable-http` and port set, Cortex serves MCP over HTTP; concurrency test passes; docs updated.
- **Phase 2**: When port is set, default transport is HTTP/SSE unless overridden to stdio; when port is unset, default remains stdio; docs describe Option C and fallback; all tests pass.

## Technical Design

- **Config precedence**: Port set → default transport `sse` (or `streamable-http`); port unset → default transport `stdio`. Env `CORTEX_MCP_TRANSPORT` overrides in both cases.
- **No handler changes**: Tool and resource handlers remain transport-agnostic; only entry point and transport selection logic change.
- **Backward compatibility**: Existing stdio-only deployments (no port, no env) unchanged. Explicit `CORTEX_MCP_TRANSPORT=stdio` preserves stdio when port is set.

## Testing Strategy (MANDATORY)

- **Coverage target**: Minimum 95% for all new/affected code (transport selection, server bootstrap, default behavior).
- **Unit tests**: Transport selection from env/config; default when port set vs unset; override to stdio.
- **Integration tests**: Server starts with sse/streamable-http when port set; tools and resources respond; concurrency (ReadResource during long CallTool); stdio path unchanged when port unset.
- **Edge cases**: Invalid transport value; missing optional deps when HTTP chosen; bind failure handling.
- **Regression**: Existing stdio-only tests and flows pass; no blanket skips; AAA pattern; Pydantic v2 for any JSON response assertions where applicable.

## Risks & Mitigation

- **Deployment complexity**: Phase 1 introduces port and optional server deps; mitigate with clear docs and localhost-only default.
- **Default change in Phase 2**: Users who set port but expect stdio can set `CORTEX_MCP_TRANSPORT=stdio`; document in release notes and migration note.
- **Client support**: Option C assumes URL-based clients when port is set; document Cursor/Inspector support; stdio fallback covers others.

## Timeline

- Phase 1: Implement and ship Option B (optional HTTP/SSE), then validate in real use.
- Phase 2: Enable Option C default (HTTP/SSE when port set) after Phase 1 is stable; communicate default change and fallback.

## Notes

- Option C from analysis: “Prefer HTTP/SSE as default when running in server mode (e.g. when a port is configured), and use stdio only when no port is set or when explicitly requested.”
- This plan replaces the previous “optional only” scope with the full gradual migration to Option C and is registered as a **blocker** for ASAP implementation.

## References

- Analysis: [docs/mcp-transport-http-sse-analysis.md](../docs/mcp-transport-http-sse-analysis.md)
- Timeouts and connection behavior: [docs/mcp-tool-timeouts.md](../docs/mcp-tool-timeouts.md)
- Connection-closed investigation (archived): `.cortex/plans/archive/Investigations/2026-02-07/investigate-mcp-connection-closed-2026-02-07.md`
