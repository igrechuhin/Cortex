---
title: "project_root_resolver.py: Handle roots/list_changed notification to invalidate stale cached root"
component: cortex/core
work_type: fix
status: PENDING
priority: low
created: 2026-03-29
depends_on: []
---

## Goal

`project_root_resolver.py` caches the resolved project root after the first
successful `list_roots()` call and never invalidates it. If the IDE sends a
`roots/list_changed` notification mid-session (because the user switched
workspace), all subsequent tool calls will operate on the stale (wrong) root
for the rest of the server process lifetime.

Add a handler for the MCP `roots/list_changed` notification that clears the
cached root, so the next tool call re-resolves it.

## Context

Current cache implementation in `project_root_resolver.py`:

```python
cached_root: Path | None = None          # module-level
_root_cache_lock: asyncio.Lock | None = None

def clear_cached_root() -> None:
    """Reset the root cache (used in tests and on explicit project-root override)."""
    global cached_root
    cached_root = None
```

`clear_cached_root()` exists for tests and explicit override, but nothing in
the MCP server wires it to the `roots/list_changed` notification. The MCP
specification includes a `notifications/roots/list_changed` message that
clients send when their workspace root list changes.

FastMCP (used by the Cortex server) exposes a way to register notification
handlers. The exact API depends on the `mcp` package version in use.

**Why this is low priority**: The scenario requires:

1. A client that supports the roots capability (already checked) AND
2. A workspace switch mid-session (unusual — most sessions are single-project).

When it does occur, the failure mode is silent: tool calls succeed but return
data for the wrong project. This is hard to diagnose because no error is raised.

## Implementation Steps

### Step 1: Audit FastMCP / mcp package for notification handler API

Read `src/cortex/server.py` and the installed `mcp` package to determine:

1. What API FastMCP provides for registering notification handlers (e.g.
   `mcp.server.notification_handlers`, `@mcp.on_notification`, or similar).
2. What the exact notification type/method string is for
   `notifications/roots/list_changed`.
3. Whether the notification is delivered to the session object, the server
   object, or via a global handler.

Also check:

- `src/cortex/core/constants.py` for any existing notification constants.
- `tests/` for any existing notification handler tests.

#### Verification Checklist — Step 1

| What to check | Where | Files |
|---------------|-------|-------|
| FastMCP notification handler API identified | Read `server.py` and mcp source | `src/cortex/server.py`, mcp package |
| Notification method string confirmed | mcp types or spec | mcp package |
| No existing `roots/list_changed` handler | Grep `list_changed` | `src/` |

### Step 2: Implement `_handle_roots_list_changed` in `project_root_resolver.py`

Add a new async function:

```python
async def _handle_roots_list_changed() -> None:
    """Clear the cached root when the client reports a roots change.

    Called by the MCP server when the client sends
    notifications/roots/list_changed. The next call to
    resolve_project_root_async() will issue a fresh list_roots() request.
    """
    global cached_root
    if cached_root is not None:
        logger.info(
            "project_root_resolver: roots/list_changed received, "
            "clearing cached root %s",
            cached_root,
        )
        cached_root = None
```

This function:

- Clears `cached_root` only if it was set (avoids noisy log on first call).
- Does NOT clear `_root_cache_lock` — the lock itself is reusable.
- Does NOT attempt to immediately re-resolve — resolution is lazy on next use.
- Logs at `INFO` level (not `DEBUG`) because this is a meaningful session
  event that could explain later behaviour if root changes unexpectedly.

**Note**: Do NOT import this function at module level in `server.py`. Wire it
through the notification handler registration (Step 3) to keep the module
boundary clean.

#### Verification Checklist — Step 2

| What to check | Where | Files |
|---------------|-------|-------|
| Function signature matches FastMCP notification handler signature | Compare with API from Step 1 | `src/cortex/core/project_root_resolver.py` |
| `global cached_root` correct (not `_root_cache_lock`) | Read function | — |
| Log level is `INFO`, not `DEBUG` | Read function | — |
| Function ≤ 30 lines | Count | — |
| No `Any` type | pyright | — |

### Step 3: Register the handler in `server.py`

In `src/cortex/server.py`, after the existing lazy prompt handler hook, add:

```python
from cortex.core.project_root_resolver import _handle_roots_list_changed

# Wire roots/list_changed notification to invalidate the cached root.
# (Use the exact FastMCP/mcp API identified in Step 1)
```

The exact wiring depends on the FastMCP API found in Step 1. Likely options:

- `mcp.server.notification_handlers["notifications/roots/list_changed"] = _handle_roots_list_changed`
- `@mcp.on_notification("notifications/roots/list_changed")` decorator pattern

If FastMCP does not support notification handlers, add a TODO comment and
document the limitation in `docs/` instead — do not introduce a workaround
that bypasses FastMCP's protocol handling.

#### Verification Checklist — Step 3

| What to check | Where | Files |
|---------------|-------|-------|
| Handler is registered using FastMCP's official API | Read `server.py` after edit | `src/cortex/server.py` |
| Import is present and correct | Grep `_handle_roots_list_changed` in `server.py` | — |
| No circular import introduced | `python3 -c "import cortex.server"` | — |

### Step 4: Write unit tests

Add tests in `tests/core/test_project_root_resolver.py`:

**Test A** — `test_roots_list_changed_clears_cache`:

```text
Arrange:
  - Set module-level `cached_root` to a fake Path
Act:
  - Call `_handle_roots_list_changed()`
Assert:
  - `cached_root` is None after the call
```

**Test B** — `test_roots_list_changed_noop_when_no_cache`:

```text
Arrange:
  - Ensure `cached_root` is None
Act:
  - Call `_handle_roots_list_changed()`
Assert:
  - No exception raised; `cached_root` remains None
```

**Test C** — `test_roots_list_changed_triggers_re_resolve` (integration):

```text
Arrange:
  - Set cached_root to fake path A
  - Prepare a mock ctx with session that returns path B from list_roots()
Act:
  - Call _handle_roots_list_changed()
  - Call resolve_project_root_async(None, ctx)
Assert:
  - Returns path B (re-resolved, not stale path A)
```

#### Verification Checklist — Step 4

| What to check | Where | Files |
|---------------|-------|-------|
| All 3 tests present and passing | `run_quality_gate()` | `tests/core/test_project_root_resolver.py` |
| AAA pattern followed | Read tests | — |
| No shared state leakage (teardown resets `cached_root`) | Read fixture/teardown | — |
| Coverage ≥ 95% for new lines | quality gate output | — |

### Step 5: Quality gate

Run `fix_quality_issues()` then `run_quality_gate()` (full run, because Python
source files changed).

#### Verification Checklist — Step 5

| What to check | Where | Files |
|---------------|-------|-------|
| `preflight_passed: true` | `run_quality_gate()` result | — |
| Zero type errors | type_check output | — |
| All 3 new tests pass | test output | — |
| Coverage ≥ 90% global | coverage output | — |

## Dependencies

- `src/cortex/core/project_root_resolver.py` (edit target)
- `src/cortex/server.py` (registration hook)
- `tests/core/test_project_root_resolver.py` (new/edit tests)
- `mcp` package source (audit for notification handler API)
- `run_quality_gate()` and `fix_quality_issues()` MCP tools

## Success Criteria

1. `_handle_roots_list_changed()` function exists in `project_root_resolver.py`
   and clears `cached_root` when called.
2. The handler is registered with the MCP server for
   `notifications/roots/list_changed` using the official FastMCP API.
3. Three unit tests pass: clear-cache, noop-when-no-cache, re-resolve.
4. `run_quality_gate()` passes: zero type errors, all tests green, ≥ 90%
   coverage.
5. No `Any` type; all new functions ≤ 30 lines.
6. If FastMCP does not support notification handlers, a TODO + docs entry is
   left and this plan is marked BLOCKED with that as the blocker.

## Testing Strategy

- **Unit tests** (3 tests as described above) in
  `tests/core/test_project_root_resolver.py` following AAA pattern.
- **Integration**: `run_quality_gate()` confirms zero regressions in the full
  suite.
- **Type safety**: pyright strict — no new `Any`, no `# type: ignore`.
- **Regression guard**: existing `test_clear_cached_root` (if present) must
  still pass; new tests must not rely on module-level state without explicit
  setup/teardown.

Coverage target: ≥ 95% for new/modified lines; ≥ 90% global.

## Known Risk

If the `mcp` package FastMCP version in use does not expose a public
notification handler registration API, Step 3 cannot be implemented cleanly.
In that case:

- Document the limitation in `docs/troubleshooting/` (section on workspace
  switches).
- Add a `CORTEX_USE_FALLBACK_ROOT=1` recommendation for users who switch
  workspaces mid-session.
- Mark plan as BLOCKED with blocker: "FastMCP lacks notification handler API".
