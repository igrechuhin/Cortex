# Plan: MCP Idempotent Resource for Project Root Path

**Status**: PENDING  
**Created**: 2026-02-09

## Goal

Add an idempotent MCP **resource** that resolves and provides the **project root path** as a **centralized entry point**. Clients and agents can read this single resource to obtain the project root without calling `get_structure_info` and interpreting `structure_info.paths` (where `paths.root` is the Cortex data directory, not the repo root).

## Context

- **Current state**: Project root is resolved internally in tools via `resolve_project_root_async(None, ctx)` or `get_or_resolve_project_root(ctx)`. There is no MCP resource that exposes only the project root. `get_structure_info` (and resource `cortex://structure/info`) returns structure paths; `structure_info.paths.root` is the `.cortex` directory, not the workspace/project root.
- **User need**: A single, idempotent resource that returns the project root path so that:
  - Clients have one clear URI to read for "where is the project?"
  - Agents can use it as a centralized entry point before other operations.
  - Behavior is idempotent: repeated reads in the same context return the same path.

## Approach

1. **Define a new MCP resource** with a stable URI (e.g. `cortex://project/root`).
2. **Implement the resource handler** to resolve project root using existing logic (`resolve_project_root_async(None, ctx)` or equivalent with session context), then return a minimal, stable JSON payload containing the project root path (e.g. `{"project_root": "/absolute/path"}`).
3. **Keep the resource read-only and idempotent**: no parameters; same resolution context yields same result.
4. **Reuse existing resolution** so behavior matches tools (MCP roots when available, fallback to `get_project_root(None)`).
5. **Register the resource** alongside existing resources (e.g. in the same module as structure/resources or a small dedicated module) with appropriate timeout and caching if applicable.

## Implementation Steps

1. **Choose URI and response shape**
   - Pick canonical URI (e.g. `cortex://project/root`).
   - Define response schema: at minimum `project_root` (absolute path string). Optionally include `resolved_via` (e.g. `"mcp_roots"` | `"fallback"`) for transparency.

2. **Implement resource handler**
   - Add an async handler that:
     - Receives MCP context (for roots/list when needed).
     - Calls existing project root resolution (e.g. `resolve_project_root_async(None, ctx)` or `get_or_resolve_project_root(ctx)`).
     - Returns JSON string with project root path (and optional metadata).
   - Decorate with `@mcp.resource(uri="cortex://project/root")` and any existing resource wrapper (e.g. `@mcp_resource_wrapper(timeout=...)`) per project conventions.

3. **Wire context into resource**
   - MCP resources may not receive `ctx` by default; ensure the handler can access session/context for `resolve_project_root_async(None, ctx)`. If the framework does not inject context into resources, use the same pattern as other resources that need context (e.g. `get_structure_info_resource`).

4. **Optional: caching**
   - If session-scoped project root is already cached (e.g. in usage context), the resource can return the cached value so repeated reads are cheap and idempotent.

5. **Documentation**
   - Document the new resource in the appropriate docs (e.g. list of Cortex resources, or docs describing project root resolution).
   - State that it is idempotent and the single recommended entry point for obtaining project root via MCP.

6. **Tests**
   - Unit tests: handler returns valid JSON with `project_root`; path is absolute; with mocked context, resolution is invoked and result matches.
   - Integration test (if applicable): read resource via MCP and assert payload shape and that path exists and contains `.cortex`.

## Dependencies

- Existing project root resolution (`project_root_resolver`, `get_project_root`, `get_or_resolve_project_root`).
- MCP resource registration and context injection patterns already used by `cortex://structure/info` and other resources.

## Success Criteria

- A resource with a stable URI (e.g. `cortex://project/root`) is registered.
- Reading the resource returns JSON containing the resolved project root path (absolute).
- The resource is idempotent (repeated reads return the same path in the same context).
- No breaking changes to existing tools or resources.
- Documentation updated; tests added and passing.

## Technical Design

- **URI**: `cortex://project/root` (or team-standard equivalent).
- **Method**: GET (resource read).
- **Response**: `{"project_root": "/absolute/path"}` with optional `resolved_via` for debugging.
- **Resolution**: Reuse `resolve_project_root_async(None, ctx)` so behavior matches tools (MCP roots when available, else cwd/script-based fallback).

## Testing Strategy

- **Coverage target**: Minimum 95% for new code (handler and any small helpers).
- **Unit tests**:
  - Handler returns JSON with `project_root` key and absolute path.
  - With mocked context that provides roots, returned path matches first file root.
  - With no context or fallback, returned path comes from `get_project_root(None)` and contains `.cortex` or equivalent.
  - Idempotency: two consecutive reads return the same path.
- **Integration** (if supported): Read resource via MCP client and assert payload shape and path validity.
- **AAA pattern**: All tests follow Arrange–Act–Assert.
- **Pydantic v2**: If validating response shape in tests, use `BaseModel` and `model_validate_json()` where appropriate.

## Risks & Mitigation

- **Context in resources**: If resources don’t receive MCP context, resolution might always fall back to cwd/script. Mitigation: use the same context-injection pattern as `get_structure_info_resource` or other resources that need context.
- **Caching vs freshness**: Caching project root per session is acceptable (idempotent); document that root is session-stable.

## Timeline

- Small feature; estimate 1–2 days including tests and docs.

## Notes

- Aligns with “do not pass project_root to tools”; the resource provides the root for clients that need it without adding a tool parameter.
- Complements `get_structure_info` / `cortex://structure/info` by offering a single-purpose, lightweight entry point for project root only.
