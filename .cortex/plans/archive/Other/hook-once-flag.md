---
title: "Once Flag on Hooks"
component: hooks
work_type: feature
status: PENDING
priority: high
created: 2026-04-06
depends_on: ["hook-conditional-dsl.md"]
---

## Once Flag on Hooks

## Goal

Allow Cortex to write hook entries with `"once": true` — a Claude Code-native flag that causes a hook to auto-remove itself after its first execution. This enables one-shot setup steps in pipelines without leaving stale hooks behind.

## Context

- Claude Code `settings.json` supports `"once": true` on any hook entry. After the hook fires once, Claude Code removes the entry from the active hook set for that session.
- Cortex currently has no way to write transient/one-shot hooks. All hooks it writes persist until manually removed.
- Use case: pipeline setup steps that should run exactly once per session (e.g., bootstrap a virtualenv, run `pip install`, verify a precondition), after which the hook should not re-fire.
- This builds on `HookEntry` from the `hook-conditional-dsl` plan — add `once: bool = False` to that model.

## Implementation Steps

### Step 1: Add `once` field to `HookEntry`

**File**: `src/cortex/setup/hook_models.py`

- Add `once: bool = False` to `HookEntry` Pydantic model.
- Serialization: when `once=True`, include `"once": true` in the JSON dict; omit the key when `False` (keep `settings.json` minimal).
- Add `model_serializer` or `model_dump(exclude_defaults=True)` to suppress `once=False`.

**Verification**: grep `once` in `hook_models.py`; confirm `HookEntry(command="...", once=False).model_dump()` does not include `"once"`.

### Step 2: Expose `once` in `merge_post_tool_use_edit_hook()`

**File**: `src/cortex/setup/claude_settings.py`

- Add `once: bool = False` parameter to `merge_post_tool_use_edit_hook()`.
- When `once=True`, pass through to `HookEntry` and ensure it appears in written JSON.
- Dedup logic update: two entries with same `command` but different `once` values are treated as distinct — one-shot and persistent hooks can coexist.

**Verification**: read updated function signature; grep `once` in `claude_settings.py`.

### Step 3: Add `write_once_hook()` convenience helper

**File**: `src/cortex/setup/claude_settings.py`

- New public function: `write_once_hook(settings_path: Path, command: str, matcher: str = "Edit", condition: HookCondition | None = None) -> None`
- Writes a single `once=True` hook entry, then immediately de-dupes (if the same `once` hook already exists for this session, skip).
- Intended for MCP tools that want to register a transient hook without touching the full hook management stack.

**Verification**: grep `write_once_hook` across `src/`; confirm it calls `merge_post_tool_use_edit_hook(once=True)`.

### Step 4: Cleanup helper — `remove_once_hooks()`

**File**: `src/cortex/setup/claude_settings.py`

- New function: `remove_once_hooks(settings_path: Path) -> int` — removes all entries where `"once": true`; returns count removed.
- Called by session teardown (`session(operation="deregister")`) to clean up any leftover once-hooks that did not auto-fire (e.g., session ended early).

**Verification**: read `session/dispatcher.py`; confirm `remove_once_hooks` is called on deregister.

### Step 5: Wire into session lifecycle

**File**: `src/cortex/tools/session/dispatcher.py`

- In the `deregister` branch, call `remove_once_hooks(settings_path)` if the settings file exists.
- Log count of removed hooks at DEBUG level.

**Verification**: grep `remove_once_hooks` in `dispatcher.py`.

### Step 6: Tests

**File**: `tests/unit/setup/test_hook_once.py` (new)

- `TestHookEntryOnce::test_once_false_not_serialized`
- `TestHookEntryOnce::test_once_true_serialized`
- `TestMergeHookOnce::test_once_and_persistent_coexist`
- `TestWriteOnceHook::test_writes_once_entry`
- `TestWriteOnceHook::test_dedup_skips_existing_once_hook`
- `TestRemoveOnceHooks::test_removes_once_entries`
- `TestRemoveOnceHooks::test_returns_count`
- `TestSessionDeregister::test_deregister_cleans_once_hooks`

Coverage target: 95%+.

## Dependencies

- `hook-conditional-dsl.md` — `HookEntry` model must exist before adding `once` to it.

## Success Criteria

1. `settings.json` entries written by Cortex include `"once": true` when requested.
2. `remove_once_hooks()` is called on session deregister.
3. Dedup logic distinguishes one-shot from persistent hooks for same command.
4. All 8 new unit tests pass; coverage ≥ 95%.
5. No regression in existing hook tests.

## Testing Strategy

- All tests use real temp files (`tmp_path`) — no mocking of file I/O.
- AAA pattern throughout.
- Session dispatcher test uses dependency injection to avoid real MCP calls.
- Run via `run_quality_gate()` after implementation.

## Partial Progress Log

- 2026-04-09: Add once flag serialization to HookEntry and unit tests — files: src/cortex/setup/hook_models.py, tests/unit/setup/test_hook_models.py
- 2026-04-09: Step 2 expose once in merge_post_tool_use_edit_hook and dedup by (command, once) — files: src/cortex/setup/claude_settings.py, tests/unit/test_claude_settings_post_edit_hook.py
- 2026-04-09: Step 3 add write_once_hook helper and once-hook dedup tests — files: src/cortex/setup/claude_settings.py, tests/unit/test_claude_settings_post_edit_hook.py
