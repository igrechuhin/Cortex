---
title: "FastMCP v3 — Phase 4: Transport Configuration Cleanup"
component: "server"
work_type: migration
status: PENDING
priority: Medium
created: 2026-04-13
depends_on:
  - fastmcp-v3-phase2-official-lifecycle-apis
---

## FastMCP v3 — Phase 4: Transport Configuration Cleanup

## Goal

Migrate transport configuration to the FastMCP v3 pattern (transport kwargs on
`run()`/`run_http_async()` instead of constructor) and remove the now-redundant
`apply_cortex_env_to_fastmcp()` env-var forwarding that existed only because
FastMCP v2 read host/port from constructor Settings.

## Context

In FastMCP v2, `host` and `port` were constructor kwargs read from the
`FASTMCP_HOST` / `FASTMCP_PORT` env vars. In v3, transport parameters are
passed directly to `run()` / `run_http_async()` / `http_app()`.

Current flow in Cortex:

1. `apply_cortex_env_to_fastmcp()` copies `CORTEX_MCP_PORT` → `FASTMCP_PORT`
   and `CORTEX_MCP_HOST` → `FASTMCP_HOST` (in `main.py` before server import).
2. `mcp.run(transport="sse", mount_path=...)` is called but `host`/`port` are
   not explicitly passed — they were read from Settings via env vars.

In v3 the explicit form is:

```python
mcp.run(transport="sse", host=get_host(), port=get_port(), mount_path=...)
```

This phase makes the transport configuration explicit, removes the env-var
forwarding hack, and confirms/updates `transport_config.py` to match v3.

## Implementation Steps

### Step 1 — Read transport_config.py and main.py transport section

Read:

- `src/cortex/transport_config.py` (full)
- `src/cortex/main.py` lines 279–315 (`_run_mcp_with_transport_handlers`)

Identify every `mcp.run()` callsite and what kwargs are currently passed.

### Verification checklist 1

- [ ] All `mcp.run()` callsites listed with current kwargs
- [ ] `get_host()` and `get_port()` helper signatures confirmed

### Step 2 — Investigate FastMCP v3 transport API

Confirm the v3 `run()` signature:

```python
mcp.run(
    transport="sse",
    host="127.0.0.1",
    port=8081,
    mount_path="/sse",
    # other v3 params?
)
```

Check if `streamable-http` is the preferred transport in v3 (v3 docs indicate
a shift toward HTTP streaming over SSE). If SSE is deprecated in v3, plan
the default transport upgrade here.

### Verification checklist 2

- [ ] `mcp.run()` kwargs for each transport confirmed
- [ ] SSE status in v3 (deprecated / still supported) documented
- [ ] `streamable-http` default consideration recorded

### Step 3 — Update `_run_mcp_with_transport_handlers` to pass explicit kwargs

Update `main.py`:

```python
def _run_mcp_with_transport_handlers(transport: str) -> None:
    try:
        if transport == "stdio":
            mcp.run(transport="stdio")
        elif transport == TRANSPORT_SSE:
            mcp.run(
                transport="sse",
                host=get_host(),
                port=get_port() or 8080,
                mount_path=get_mount_path(transport),
            )
        else:
            mcp.run(
                transport="streamable-http",
                host=get_host(),
                port=get_port() or 8080,
            )
    except ...
```

### Verification checklist 3

- [ ] `host` and `port` explicitly passed to `run()` for HTTP transports
- [ ] No reliance on env-var forwarding for transport config

### Step 4 — Remove `apply_cortex_env_to_fastmcp()`

Once host/port are passed explicitly to `run()`, the
`apply_cortex_env_to_fastmcp()` function in `transport_config.py` is
unnecessary. Delete it and its call site in `main.py`.

Also check: if FastMCP v3 Settings still read `FASTMCP_*` env vars for
_other_ purposes (log level, debug mode), keep the relevant mappings.
Delete only what's truly dead.

### Verification checklist 4

- [ ] `apply_cortex_env_to_fastmcp` deleted from `transport_config.py`
- [ ] Call site in `main.py` removed
- [ ] No `FASTMCP_PORT` / `FASTMCP_HOST` env var dependencies remain

### Step 5 — Consider promoting `streamable-http` as default for port-based mode

In FastMCP v2, the default when `CORTEX_MCP_PORT` was set was `sse`. In v3
`streamable-http` is the preferred transport. Update `get_effective_transport()`
in `transport_config.py`:

```python
if port is not None:
    return TRANSPORT_STREAMABLE_HTTP  # was TRANSPORT_SSE
```

Update docs, README, and CI workflow comments accordingly. Add a deprecation
notice in the `sse` transport selection path so users know to migrate their
config.

### Verification checklist 5

- [ ] `get_effective_transport()` returns `streamable-http` when port is set
  (unless explicitly overridden)
- [ ] README offline/network-resilience section updated
- [ ] Existing SSE configuration still works via explicit `CORTEX_MCP_TRANSPORT=sse`

### Step 6 — Update unit tests for transport_config

Tests for `transport_config.py` currently expect `sse` as the default when
port is set. Update them to expect `streamable-http` (if Step 5 is
implemented).

### Verification checklist 6

- [ ] `tests/unit/test_transport_config.py` (or equivalent) updated
- [ ] All transport tests pass

### Step 7 — Quality gate

`run_quality_gate()`.

### Verification checklist 7

- [ ] All tests pass
- [ ] No `apply_cortex_env_to_fastmcp` references remain
- [ ] Coverage ≥90%

## Dependencies

- Phase 2 complete.
- Phase 1 complete (v3 installed).

## Success Criteria

1. `apply_cortex_env_to_fastmcp()` deleted.
2. Host/port explicitly passed to `mcp.run()`.
3. `streamable-http` is the default for port-based mode.
4. All transport tests pass, quality gate green.

## Testing Strategy

- **Unit**: update `test_transport_config.py` for new default.
- **Smoke tests**: start server with each transport mode; verify endpoints.
- No new test files required.

Coverage target: maintain ≥90% baseline.
