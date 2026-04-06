---
title: "Conditional Hook Execution DSL"
component: hooks
work_type: feature
status: PENDING
priority: high
created: 2026-04-06
depends_on: []
---

## Conditional Hook Execution DSL

## Goal

Extend Cortex's `ensure_post_edit_hook_in_project_claude_settings()` to write `matcher`-pattern entries that use a wildcard DSL — e.g. `FileEdit(/src/*)`, `Bash(git *)` — so hooks only fire when a specific tool+pattern matches, instead of every tool event.

Claude Code already evaluates these patterns natively. Cortex just needs to generate the right `settings.json` entries.

## Context

- Current hook writing: `src/cortex/setup/claude_settings.py` — `merge_post_tool_use_edit_hook()` always writes `"matcher": "Edit"` with no sub-pattern.
- Claude Code `settings.json` schema supports `matcher` values like `Edit`, `Bash`, `Write` and a glob sub-pattern embedded in the hook `command` invocation condition (via `hooks[].conditions[]`).
- Claude Code (claude-code-main) uses a permission rule DSL: `Bash(git *)`, `FileEdit(/src/*)` applied as `if` conditions on hook entries.
- Target: Cortex should be able to write hooks that only activate when a matched pattern is satisfied, reducing hook noise and avoiding false quality-gate triggers.

## Implementation Steps

### Step 1: Define `HookCondition` model

**File**: `src/cortex/setup/hook_models.py` (new file, ≤ 80 lines)

- Pydantic `BaseModel` with fields: `tool: str`, `pattern: str | None = None`
- Method `to_matcher_string() -> str` — returns `"Edit"`, `"Bash(git *)"`, `"FileEdit(/src/*)"` etc.
- `HookEntry` model: `type: Literal["command", "prompt", "agent"]`, `command: str`, `condition: HookCondition | None = None`
- `PostToolUseBlock` model: `matcher: str`, `hooks: list[HookEntry]`

**Verification**: grep `HookCondition` in `src/cortex/setup/`; read `hook_models.py`.

### Step 2: Update `merge_post_tool_use_edit_hook()`

**File**: `src/cortex/setup/claude_settings.py`

- Accept optional `condition: HookCondition | None = None` parameter.
- When `condition` is provided, write `matcher` using `condition.to_matcher_string()`.
- Dedup logic: compare existing entries by both `matcher` string AND `command` (not just command).
- Keep backward compat: when `condition=None`, behavior identical to today.

**Verification**: read updated function; grep `condition` in `claude_settings.py`.

### Step 3: Expose condition in hook templates

**File**: `src/cortex/setup/hook_templates.py`

- `HookTemplates.get_post_edit_hook(language)` → return `tuple[str, HookCondition]` instead of `str`.
- Python template default condition: `HookCondition(tool="Edit", pattern="**/*.py")`.
- TypeScript template default condition: `HookCondition(tool="Edit", pattern="**/*.ts")`.
- Generic/None language: `HookCondition(tool="Edit", pattern=None)` (matches all edits).

**Verification**: grep return types in `hook_templates.py`; check callers are updated.

### Step 4: Update callers

**Files**: `src/cortex/setup/post_edit_hook_runtime.py`, `src/cortex/setup/claude_settings.py`

- Update `ensure_post_edit_hook_in_project_claude_settings()` to unpack the `(command, condition)` tuple and pass `condition` to `merge_post_tool_use_edit_hook()`.
- No changes to public MCP tool signatures.

**Verification**: grep `get_post_edit_hook` across `src/`; confirm all callers updated.

### Step 5: Add `conditions` field support (future-compat)

**File**: `src/cortex/setup/claude_settings.py`

- When serializing hook entries to `settings.json`, if `condition.pattern` is set, add a `conditions` key matching Claude Code's expected schema: `[{"tool": "<tool>", "pattern": "<glob>"}]`.
- This is forward-compatible: Claude Code ignores unknown keys gracefully if conditions aren't supported.

**Verification**: write a small test fixture and assert `settings.json` output contains `conditions` key when pattern is set.

### Step 6: Tests

**File**: `tests/unit/setup/test_hook_models.py` (new)

- `TestHookCondition::test_to_matcher_string_no_pattern` — returns bare tool name.
- `TestHookCondition::test_to_matcher_string_with_pattern` — returns `"Bash(git *)"`.
- `TestMergeHook::test_dedup_by_matcher_and_command` — same matcher+command → no duplicate.
- `TestMergeHook::test_different_matcher_same_command` — different matcher → two entries.
- `TestEnsureHook::test_condition_written_to_settings_json` — integration: assert file on disk.
- `TestHookTemplates::test_python_returns_condition` — tuple unpacking works.

Coverage target: 95%+.

## Dependencies

- No external dependencies.
- Internal: `src/cortex/setup/claude_settings.py`, `src/cortex/setup/hook_templates.py`, `src/cortex/setup/post_edit_hook_runtime.py`.

## Success Criteria

1. `settings.json` written by Cortex contains `matcher` values with glob sub-patterns when language is detected.
2. Hook does not fire for non-matching files (verified by Claude Code behavior — Cortex cannot directly test Claude Code's hook execution, but can assert correct JSON output).
3. Backward compat: existing tests still pass with no condition.
4. All 6 new unit tests pass; coverage ≥ 95%.
5. `HookCondition` model has 100% type coverage (pyright strict).

## Testing Strategy

- Unit tests: `tests/unit/setup/test_hook_models.py` — pure model + serialization logic, no I/O.
- Integration tests: use `tmp_path` fixture to write real `settings.json` and assert contents.
- No mocking of `open()` — use real temp files.
- AAA pattern throughout.
- Run via `run_quality_gate()` after implementation.
