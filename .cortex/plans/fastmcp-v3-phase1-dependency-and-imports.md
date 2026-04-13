---
title: "FastMCP v3 — Phase 1: Dependency Swap and Import Migration"
component: "server"
work_type: "migration"
status: DONE
priority: high
created: 2026-04-13
depends_on: []
---

## FastMCP v3 — Phase 1: Dependency Swap and Import Migration

## Goal

Replace the bundled `mcp>=1.26.0` FastMCP (from `mcp.server.fastmcp`) with the
standalone `fastmcp>=3.0` package. This is the prerequisite for all subsequent
FastMCP v3 phases. The objective is a green quality gate with zero behaviour
change.

## Context

Cortex currently imports FastMCP from the Anthropic MCP SDK:

```python
from mcp.server.fastmcp import FastMCP   # server.py:22
from mcp.server.fastmcp import Context   # core/context_logging.py:14
from mcp.server.session import ServerSession  # core/context_logging.py:15
```

The standalone `fastmcp>=3.0` package ships its own `FastMCP` and `Context`
classes. The `mcp` SDK package can remain as a peer dependency for low-level
types (`mcp.types.*`, `mcp.shared.*`) that FastMCP v3 still re-exports.

Key facts from the audit:

- `FastMCP("cortex")` is called with no kwargs — constructor is trivially
  compatible.
- No `ctx.get_state` / `ctx.set_state` — no async-state migration needed.
- No `enabled=`, `on_duplicate_*` — no removed-kwarg migration needed.
- Three low-level `mcp._mcp_server` patches exist — addressed in Phase 2.
- Two `@mcp.resource(meta=...)` with cache-control — verify meta API in v3.
- `apply_cortex_env_to_fastmcp()` copies `CORTEX_MCP_*` → `FASTMCP_*` env
  vars; verify env-var names are unchanged in v3 Settings.

## Implementation Steps

### Step 1 — Pin and install fastmcp v3

1. Read `pyproject.toml` in full.
2. Replace `"mcp>=1.26.0"` with:

   ```toml
   "fastmcp>=3.0,<4",
   "mcp>=1.26.0",   # keep for mcp.types.*, mcp.shared.* low-level types
   ```

3. Run `uv lock` and `uv sync` to update `uv.lock`.
4. Confirm `fastmcp` appears in the lock file at 3.x.

### Verification checklist 1

- [ ] `uv pip show fastmcp` → version 3.x
- [ ] `uv pip show mcp` → still present (for `mcp.types.*`)
- [ ] `uv lock` exits 0

### Step 2 — Update FastMCP and Context imports

Files to change (all import sites identified in the audit):

| File | Old import | New import |
|------|-----------|------------|
| `src/cortex/server.py:22` | `from mcp.server.fastmcp import FastMCP` | `from fastmcp import FastMCP` |
| `src/cortex/core/context_logging.py:14` | `from mcp.server.fastmcp import Context` | `from fastmcp import Context` |

Leave all `mcp.types.*`, `mcp.shared.*`, `mcp.server.session.*` imports
unchanged — those come from the `mcp` SDK which remains as a dependency.

### Verification checklist 2

- [ ] `rg "from mcp.server.fastmcp" src/` → zero results
- [ ] `rg "from fastmcp import" src/` → shows new imports
- [ ] Pyright reports no import errors on changed files

### Step 3 — Verify `ServerSession` import path

`core/context_logging.py:15` and `core/project_root_resolver.py:34` import
`ServerSession` from `mcp.server.session`. Check whether fastmcp v3 re-exports
this or whether it must still come from `mcp`:

```python
python -c "from fastmcp import Context; print(type(Context))"
python -c "from mcp.server.session import ServerSession; print(ServerSession)"
```

If `mcp.server.session.ServerSession` is still the correct source, leave those
imports unchanged. Document the decision with an `# AI:` comment.

### Verification checklist 3

- [ ] `ServerSession` import path confirmed (fastmcp or mcp)
- [ ] No `ImportError` at runtime for context_logging or project_root_resolver

### Step 4 — Verify `meta=` on `@mcp.resource()`

FastMCP v3 changed how resource metadata is passed. The two resources that use
`meta=` are:

- `cortex://context` — `meta={"cache_control": {"type": "ephemeral", "ttl": "5m"}}`
- `cortex://rules` — `meta={"cache_control": {"type": "ephemeral", "ttl": "1h"}}`

Check the fastmcp v3 `Resource` signature for the `meta` parameter. If the
parameter name or structure changed, update `src/cortex/core/constants.py`
(`CORTEX_CONTEXT_RESOURCE_READ_META`, `CORTEX_RULES_RESOURCE_READ_META`) and
the decorator calls in `handlers.py` and `rules_operations.py`.

Also check `@mcp.tool(meta={...})` in `crud_operations.py:113`.

### Verification checklist 4

- [ ] `meta=` parameter accepted by v3 `@mcp.resource()` decorator
- [ ] Cache-control metadata structure confirmed or updated
- [ ] No `TypeError` on server startup

### Step 5 — Verify FASTMCP_* env var names

`transport_config.py:apply_cortex_env_to_fastmcp()` copies:

- `CORTEX_MCP_PORT` → `FASTMCP_PORT`
- `CORTEX_MCP_HOST` → `FASTMCP_HOST`

In FastMCP v3 the Settings class may have different env-var names or the
transport config may have moved entirely (transport kwargs are now on `run()`
not the constructor). Investigate and update accordingly.

If the port/host env vars are no longer consumed by `FastMCP()` constructor
settings (because transport config moved to `run()`), then
`apply_cortex_env_to_fastmcp()` becomes a no-op and can be simplified.
See Phase 4 for the full transport cleanup.

### Verification checklist 5

- [ ] No `UserWarning` or `DeprecationWarning` about unrecognised env vars
- [ ] Server starts successfully with `CORTEX_MCP_PORT=8080` set

### Step 6 — Smoke test all three transports

Start the server with each transport and confirm basic handshake works:

```bash
echo '{"jsonrpc":"2.0","method":"initialize","params":{...},"id":1}' | \
  uv run cortex  # stdio

CORTEX_MCP_TRANSPORT=sse CORTEX_MCP_PORT=8081 uv run cortex &
curl http://localhost:8081/sse

CORTEX_MCP_TRANSPORT=streamable-http CORTEX_MCP_PORT=8082 uv run cortex &
curl http://localhost:8082/mcp
```

### Verification checklist 6

- [ ] stdio transport: server initialises and returns tool list
- [ ] SSE transport: `/sse` endpoint returns event stream
- [ ] Streamable-HTTP transport: `/mcp` endpoint responds

### Step 7 — Quality gate

Run `run_quality_gate()`. Fix any type-checker errors from the import path
changes. Do not change any behaviour.

### Verification checklist 7

- [ ] All tests pass
- [ ] Pyright strict clean on changed files
- [ ] Coverage baseline maintained (≥90%)

## Dependencies

- pyproject.toml / uv.lock writable.
- fastmcp 3.x available on PyPI (confirmed).
- Phases 2–5 depend on this phase completing.

## Success Criteria

1. `fastmcp>=3.0` is the active FastMCP package.
2. Zero `from mcp.server.fastmcp` import sites remain.
3. All three transports start successfully.
4. All tests pass, quality gate green.
5. No behaviour change visible to MCP clients.

## Testing Strategy

- **Unit**: all existing unit tests must pass unchanged.
- **Transport smoke tests** (Step 6): manual startup validation for each
  transport.
- **Import verification** (Steps 2–3): `python -c "from fastmcp import FastMCP"`
  and `python -c "import cortex.server"` must not raise.
- No new test code required; this is a dependency swap.

Coverage target: maintain ≥90% baseline.

## Partial Progress Log

- 2026-04-13: Dependency swap/import migration baseline completed; quality-gate blockers identified and triaged — files: pyproject.toml, uv.lock, src/cortex/server.py, src/cortex/core/context_logging.py, src/cortex/core/project_root_resolver.py, src/cortex/core/mcp_stability.py
- 2026-04-13: Phase 1 DONE — all 7 steps verified: fastmcp 3.2.3 installed; zero mcp.server.fastmcp import sites; meta= param confirmed; env-var migration confirmed no-op; mount_path→path fix in main.py for SSE transport; all three transports smoke-tested (stdio/sse/streamable-http); 6505 tests pass, pyright clean.
