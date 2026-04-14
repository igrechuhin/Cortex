---
title: "FastMCP v3 — Phase 5: Adopt New v3 Features (Lifespan, Visibility, Auth, Transforms)"
component: "server"
work_type: "enhancement"
status: COMPLETE
priority: medium
created: 2026-04-13
depends_on:
  - fastmcp-v3-phase3-middleware
  - fastmcp-v3-phase4-transport-cleanup
---

## FastMCP v3 — Phase 5: Adopt New v3 Features (Lifespan, Visibility, Auth, Transforms)

## Goal

Once Cortex is fully on FastMCP v3 (Phases 1–4), adopt the v3 features that
directly improve Cortex's reliability, security, and developer experience:

1. **Server lifespan** — clean startup/shutdown instead of ad-hoc globals.
2. **Component visibility** — dynamic enable/disable of tools per session
   or context (e.g. hide setup tools after initialisation is complete).
3. **Per-component auth** — gate sensitive tools (write_artifact, manage_file,
   ingest) to authorised callers.
4. **`ResourcesAsTools` / `PromptsAsTools` transforms** — expose resources
   and prompts through the tools interface for clients that only speak tools.
5. **Hot-reload dev mode** — `fastmcp dev` for faster iteration.

## Context

Cortex registers 15+ tools, 6 resources, and 7+ prompts. Several cross-cutting
concerns currently require ad-hoc code:

- **Setup tools** (initialize, migrate, populate_tiktoken_cache) are
  conditionally registered via lazy registration — v3 visibility provides a
  cleaner mechanism.
- **write_artifact and manage_file** carry `allowed_callers` metadata but no
  server-enforced access control — v3 per-component auth fills this gap.
- **Resources are invisible to tool-only clients** — `ResourcesAsTools`
  transform solves this.

## Implementation Steps

### Step 1 — Add server lifespan for dependency initialisation

FastMCP v3 lifespan hooks run once per server process:

```python
from contextlib import asynccontextmanager
from fastmcp import FastMCP

@asynccontextmanager
async def lifespan(server: FastMCP):
    # Startup: initialise ManagerRegistry, inject SequentialThinkingCore, etc.
    _inject_sequential_thinking_core()
    yield
    # Shutdown: flush logs, close connections

mcp = FastMCP("cortex", lifespan=lifespan)
```

Move from `main.py`:

- `_inject_sequential_thinking_core()` call
- Any other one-time initialisation that currently runs in `main()` before
  `mcp.run()`

This makes the server self-contained: `FastMCP("cortex", lifespan=lifespan)`
carries its own initialisation without relying on the caller to sequence
setup before `run()`.

### Verification checklist 1

- [ ] `lifespan=` parameter accepted by FastMCP v3 constructor (verify API)
- [ ] `SequentialThinkingCore` still injected before first tool call
- [ ] `main.py` startup sequence simplified

### Step 2 — Dynamic component visibility for setup tools

Currently, setup tools (initialize, migrate, populate_tiktoken_cache) are
conditionally registered at startup via lazy prompt registration. In v3:

1. Register all setup prompts unconditionally at startup.
2. Use `mcp.disable("initialize")` etc. when the project is already
   initialised (check `get_project_config_status()`).
3. Use `mcp.enable("initialize")` on `roots/list_changed` if the root
   switched to an uninitialised project.

```python
status = get_project_config_status(project_root)
if status.is_initialised:
    mcp.disable("initialize")
    mcp.disable("migrate")
```

v3 automatically sends `ToolListChangedNotification` to connected clients
when visibility changes, so IDE clients see the updated tool list without
reconnecting.

### Verification checklist 2

- [ ] Setup prompts/tools hidden for already-initialised projects
- [ ] Setup prompts/tools appear after `roots/list_changed` if new project
- [ ] `ToolListChangedNotification` sent to clients on visibility change
- [ ] Lazy registration module simplified or removed

### Step 3 — Per-component auth for write operations

Tools that modify state or the file system warrant server-enforced access
control. Currently `allowed_callers` is metadata only — not enforced at the
MCP layer.

Implement an auth callable that checks the `user_agent` or `clientInfo` from
the MCP session context:

```python
def _cortex_agent_only(ctx) -> bool:
    """Allow only Cortex pipeline callers (not raw user queries)."""
    client = getattr(ctx, "client_info", None) or {}
    return bool(client.get("name", "").startswith("cortex"))
```

Apply to high-risk tools:

```python
@mcp.tool(auth=_cortex_agent_only)
async def write_artifact(...): ...

@mcp.tool(auth=_cortex_agent_only)
async def manage_file(...) -> ...: ...
```

For `ingest`, apply a similar callable that allows the commit-pipeline caller.

Adjust auth strategy if `clientInfo` is unavailable or unreliable — in that
case, document the limitation and use a token/header approach instead.

### Verification checklist 3

- [ ] `write_artifact`, `manage_file`, `ingest` have `auth=` callables
- [ ] Unauthorised callers receive a clear `PermissionError` response
- [ ] Pipeline callers still work end-to-end
- [ ] Unit tests mock auth context and assert allow/deny behavior

### Step 4 — `ResourcesAsTools` transform for tool-only clients

Some MCP clients (particularly lightweight ones) only invoke `tools/call` and
never read resources. Cortex's six resources — especially `cortex://context`
and `cortex://rules` — are then invisible.

Add a `ResourcesAsTools` transform so clients can call `read_resource` as a
tool:

```python
from fastmcp.transforms import ResourcesAsTools  # verify exact import
mcp.add_transform(ResourcesAsTools())
```

This auto-generates `list_resources` and `read_resource` tool wrappers.
Gate this behind an opt-in config key `tool_compat.expose_resources_as_tools`
in `.cortex/config/optimization.json` to avoid polluting the tool list for
clients that support native resource reading.

### Verification checklist 4

- [ ] `ResourcesAsTools` available in fastmcp v3 (verify import)
- [ ] `cortex://context` readable via tool call when feature is enabled
- [ ] Tool list is unchanged when feature is disabled (default off)
- [ ] Config key documented in `docs/guides/`

### Step 5 — `PromptsAsTools` transform for tool-only clients

Similarly, expose Synapse prompts as callable tools:

```python
from fastmcp.transforms import PromptsAsTools  # verify exact import
mcp.add_transform(PromptsAsTools())
```

Gate behind `tool_compat.expose_prompts_as_tools` config key (default off).

### Verification checklist 5

- [ ] Synapse prompts callable via tool interface when enabled
- [ ] Prompt list unchanged when disabled
- [ ] Config key documented

### Step 6 — Dev mode hot-reload support

Add a `--dev` flag to the Cortex CLI / `main.py` that launches the server
via `fastmcp dev` for hot-reloading during development:

```bash
CORTEX_DEV=1 uvx cortex  # or: fastmcp dev src/cortex/server.py
```

Update `main.py` to check `CORTEX_DEV=1` and delegate to `fastmcp dev` if
set. Update the Makefile with a `dev` target:

```makefile
dev:  ## Start MCP server in hot-reload dev mode
	CORTEX_DEV=1 uv run cortex
```

Update the contributing guide with the dev workflow.

### Verification checklist 6

- [ ] `make dev` starts server with hot reload
- [ ] File changes cause server to restart without manual kill
- [ ] Dev mode is clearly distinct from production (log prefix, etc.)

### Step 7 — Quality gate and end-to-end validation

`run_quality_gate()`. Run the full test suite. Perform an end-to-end session
with an MCP client against the migrated server.

### Verification checklist 7

- [ ] All tests pass
- [ ] Auth callables tested with mock ctx
- [ ] Visibility toggle tested with mock project status
- [ ] Coverage ≥90%
- [ ] No regressions in any Phase 1–4 work

## Dependencies

- Phases 3 and 4 complete.
- fastmcp v3 `ResourcesAsTools` / `PromptsAsTools` transforms available
  (verify at implementation time; if not available, Steps 4–5 are deferred).

## Success Criteria

1. Server lifespan manages startup/shutdown cleanly.
2. Setup tools hidden/shown dynamically via v3 visibility API.
3. `write_artifact`, `manage_file`, `ingest` have server-enforced auth.
4. `ResourcesAsTools` and `PromptsAsTools` available behind config flag.
5. `make dev` starts hot-reload mode.
6. Quality gate green.

## Testing Strategy

- **Unit tests**:
  - `test_server_lifespan.py`: lifespan hook runs at startup/shutdown.
  - `test_component_visibility.py`: tools hidden for initialised project,
    shown for uninitialised.
  - `test_server_auth.py`: auth callables allow/deny correctly.
  - `test_transforms.py`: `ResourcesAsTools` exposes resources as tools.
- **Integration**: end-to-end session covering tool call, resource read,
  prompt list, auth rejection.

Coverage target: 95% for new code in this phase.
