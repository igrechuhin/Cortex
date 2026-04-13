---
title: "FastMCP v3 — Phase 2: Replace Internal Handler Patches with Official APIs"
component: "server"
work_type: "migration"
status: PENDING
priority: high
created: 2026-04-13
depends_on:
  - fastmcp-v3-phase1-dependency-and-imports
---

## FastMCP v3 — Phase 2: Replace Internal Handler Patches with Official APIs

## Goal

Remove all three `mcp._mcp_server.*` monkey-patches from `server.py` and
`main.py` that bypass FastMCP's public API. Replace each with the official
FastMCP v3 mechanism:

| Current patch | What it does | v3 replacement |
|---------------|-------------|----------------|
| `mcp._mcp_server.request_handlers[ListPromptsRequest]` | Lazy prompt registration on first `list_prompts` | Server lifespan hook |
| `mcp._mcp_server.notification_handlers[RootsListChangedNotification]` | Invalidate root cache on `roots/list_changed` | v3 notification API or lifespan |
| `mcp._mcp_server._handle_request` (MethodType wrap) | Absorb `ClosedResourceError` on disconnect | Middleware (Phase 3) |

## Context

All three patches were necessary workarounds for FastMCP v2's lack of public
extension points. FastMCP v3 introduces:

1. **Server lifespan hooks** — run once at server startup (ideal for
   `ensure_prompts_registered`, which must run before the first
   `list_prompts` response).
2. **`@mcp.on_notification()`** (or equivalent notification handler API) —
   official route for reacting to client notifications.
3. **Middleware** — pipeline-level interception without MethodType wrapping
   (Phase 3).

**Critical risk**: the lazy prompt registration logic (`lazy_prompt_registration.py`)
depends on `mcp.get_context()` to obtain the MCP `ctx` for `roots/list`. In
v3, the lifespan context provides the server instance but not a per-request
`Context`. The plan must preserve root resolution.

## Implementation Steps

### Step 1 — Read all affected files

Read in full:

- `src/cortex/server.py`
- `src/cortex/main.py` (lines 234–276, the `_patch_mcp_server_handle_request` fn)
- `src/cortex/setup/lazy_prompt_registration.py`
- `src/cortex/core/project_root_resolver.py`

Map the exact callsite where `mcp.get_context()` is used inside
`_lazy_list_prompts_handler` and confirm what it's used for (obtaining the
MCP root via `roots/list`).

### Verification checklist 1

- [ ] Root resolution code path is fully understood
- [ ] `ensure_prompts_registered(ctx)` signature and ctx usage documented

### Step 2 — Investigate FastMCP v3 lifespan and notification APIs

Check the fastmcp v3 docs/source for:

1. How to register a startup lifespan hook: `@mcp.on_startup()` or
   context-manager `lifespan=` parameter on `FastMCP()`.
2. How to register notification handlers: `@mcp.on_notification(...)` or
   equivalent.
3. Whether lifespan context provides access to a session or root-capable
   object, or whether `roots/list` must still be done on first live session.

If lifespan cannot resolve MCP roots (roots come from connected clients, not
server startup), the lazy pattern remains appropriate but should use an
official per-session hook rather than `request_handlers` patching.

### Verification checklist 2

- [ ] v3 lifespan API signature confirmed
- [ ] v3 notification handler API confirmed
- [ ] Decision recorded: lifespan vs per-session hook for prompt registration

### Step 3 — Replace `ListPromptsRequest` patch with v3 hook

**If FastMCP v3 provides a per-prompt-list hook or before-list hook:**
Replace the `request_handlers` patch with the official hook.

**If no such hook exists, but v3 lifespan is available:**
Adapt `ensure_prompts_registered` to run at lifespan startup by separating the
"register prompts on the mcp instance" step from the "resolve root from live
context" step:

- At lifespan startup: register all Synapse prompts that don't need the root
  (static path prompts).
- On first `roots/list_changed` notification (Step 4): resolve root and
  register root-dependent setup prompts.

Either way, delete the `_lazy_list_prompts_handler` function and the
`request_handlers[ListPromptsRequest]` assignment from `server.py`.

Update `lazy_prompt_registration.py` and its callers accordingly.

### Verification checklist 3

- [ ] `server.py` contains no `request_handlers[ListPromptsRequest]` line
- [ ] Prompts still appear correctly on `list_prompts`
- [ ] Setup prompts (initialize, migrate) conditionally registered when needed
- [ ] Unit tests for lazy registration still pass or are updated

### Step 4 — Replace `RootsListChangedNotification` patch with official API

FastMCP v3 notification handler registration (likely `@mcp.on_notification()`)
should replace:

```python
mcp._mcp_server.notification_handlers[RootsListChangedNotification] = (
    _roots_list_changed_notification_handler
)
```

New form (verify exact API):

```python
@mcp.on_notification(RootsListChangedNotification)
async def _on_roots_changed(notification: RootsListChangedNotification) -> None:
    await handle_roots_list_changed()
```

Or if using the v3 client-event API:

```python
@mcp.on_roots_changed()
async def _on_roots_changed() -> None:
    await handle_roots_list_changed()
```

Delete the old assignment from `server.py`.

### Verification checklist 4

- [ ] `server.py` contains no `notification_handlers[RootsListChangedNotification]` line
- [ ] Root cache is still invalidated when client sends `roots/list_changed`
- [ ] Unit tests for `project_root_resolver` still pass

### Step 5 — Remove `_patch_mcp_server_handle_request` from main.py

The `ClosedResourceError` suppression is moved to middleware in Phase 3. For
this phase, simply verify the patch is still needed or if FastMCP v3 already
handles `ClosedResourceError` gracefully.

Run the test suite and check if any tests simulate disconnect scenarios. If
FastMCP v3 absorbs this error internally, delete `_patch_mcp_server_handle_request`
entirely. If not, leave it in place as a temporary shim until Phase 3.

### Verification checklist 5

- [ ] Determined whether v3 handles `ClosedResourceError` natively
- [ ] `_patch_mcp_server_handle_request` either deleted or marked TODO-Phase3

### Step 6 — Remove `# type: ignore[index]` suppressions

The `request_handlers` and `notification_handlers` patches use `# type: ignore`
because they access private internals. Once replaced with official APIs, all
`# type: ignore` comments added for those patches should be removed.

Search for `type: ignore` in `server.py` and clean up any that are no longer
needed.

### Verification checklist 6

- [ ] `rg "type: ignore" src/cortex/server.py` shows only legitimately needed suppressions
- [ ] Pyright strict clean on server.py

### Step 7 — Quality gate

`run_quality_gate()`. All tests pass, no regressions.

### Verification checklist 7

- [ ] All tests pass
- [ ] No new pyright errors
- [ ] Server starts on all three transports

## Dependencies

- Phase 1 complete (fastmcp v3 installed).

## Success Criteria

1. `server.py` contains zero `mcp._mcp_server.*` attribute accesses.
2. Prompt lazy registration works via official v3 API.
3. `roots/list_changed` notification handled via official v3 API.
4. All tests pass, quality gate green.

## Testing Strategy

- **Existing tests**: all `lazy_prompt_registration` and `project_root_resolver`
  unit tests must pass (or be minimally updated if API signatures change).
- **Integration**: start server, send `list_prompts` — assert Synapse prompts
  are listed. Send `roots/list_changed` — assert root cache cleared.
- **New tests** (if behaviour changes): add targeted tests for the new hook
  registration paths.

Coverage target: 95% for changed modules.
