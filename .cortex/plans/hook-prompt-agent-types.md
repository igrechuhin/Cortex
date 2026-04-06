---
title: "Prompt and Agent Hook Types"
component: hooks
work_type: feature
status: PENDING
priority: medium
created: 2026-04-06
depends_on: ["hook-conditional-dsl.md"]
---

## Prompt and Agent Hook Types

## Goal

Extend `HookEntry` to support `"type": "prompt"` and `"type": "agent"` hook entries — not just `"type": "command"`. Claude Code executes these natively: prompt hooks evaluate an LLM prompt after a tool fires; agent hooks spin up a small verification agent. Cortex needs to write these entries correctly into `settings.json`.

## Context

- Claude Code (claude-code-main `src/schemas/hooks.ts`) defines three hook types: `CommandHook`, `PromptHook`, `AgentHook`.
- `PromptHook`: `{ type: "prompt", prompt: string, model?: string, timeout?: number, statusMessage?: string }`.
- `AgentHook`: `{ type: "agent", prompt: string, ... }` — same shape; difference is Claude Code runs it inside a full agentic loop.
- Use cases: post-edit prompt hook for lightweight contract checks; post-edit agent hook for regression verification.
- Cortex cannot control execution — it only writes the hook entries. Claude Code/Cursor harness runs them.

## Implementation Steps

### Step 1: Extend `HookEntry` with discriminated union

**File**: `src/cortex/setup/hook_models.py`

Replace `HookEntry` with a discriminated union:

```python
class CommandHookEntry(BaseModel):
    type: Literal["command"] = "command"
    command: str
    once: bool = False
    timeout: int | None = None

class PromptHookEntry(BaseModel):
    type: Literal["prompt"] = "prompt"
    prompt: str
    model: str | None = None
    timeout: int | None = None
    status_message: str | None = None

class AgentHookEntry(BaseModel):
    type: Literal["agent"] = "agent"
    prompt: str
    model: str | None = None
    timeout: int | None = None
    status_message: str | None = None

HookEntry = CommandHookEntry | PromptHookEntry | AgentHookEntry
```

- Use `model_dump(exclude_none=True)` for all three.
- Alias `status_message` → `statusMessage` via `alias_generator` for correct Claude Code JSON key.

**Verification**: grep `PromptHookEntry`; assert `model_dump(by_alias=True)` produces `statusMessage`.

### Step 2: Add `write_prompt_hook()` and `write_agent_hook()` helpers

**File**: `src/cortex/setup/claude_settings.py`

- `write_prompt_hook(settings_path, matcher, prompt, model=None, timeout=None, status_message=None) -> None`
- `write_agent_hook(settings_path, matcher, prompt, model=None, timeout=None, status_message=None) -> None`
- Dedup: skip if entry with same `type` AND same `prompt` already exists under that matcher.

**Verification**: grep both helpers in `claude_settings.py`.

### Step 3: Default model constant

**File**: `src/cortex/core/constants.py`

- Add `HOOK_DEFAULT_MODEL = "claude-haiku-4-5"` for lightweight hook evaluation.
- Both helpers default to this when `model=None`.

**Verification**: grep `HOOK_DEFAULT_MODEL`; confirm it appears in serialized JSON output.

### Step 4: Tests

**File**: `tests/unit/setup/test_hook_prompt_agent.py` (new)

- `TestPromptHookEntry::test_serializes_type_prompt`
- `TestPromptHookEntry::test_status_message_alias` — `statusMessage` key in output
- `TestPromptHookEntry::test_none_fields_excluded`
- `TestAgentHookEntry::test_serializes_type_agent`
- `TestWritePromptHook::test_writes_to_settings_json`
- `TestWritePromptHook::test_dedup_same_prompt`
- `TestWritePromptHook::test_dedup_different_prompt` — two distinct prompts → two entries
- `TestWriteAgentHook::test_writes_agent_entry`
- `TestDefaultModel::test_default_model_written_when_none`

Coverage target: 95%+.

## Dependencies

- `hook-conditional-dsl.md` — `HookEntry` discriminated union extends the base model defined there.

## Success Criteria

1. `settings.json` entries contain `"type": "prompt"` or `"type": "agent"` with correct JSON keys.
2. Dedup logic prevents duplicate prompt/agent hooks.
3. Default model is `claude-haiku-4-5` unless overridden.
4. All 9 unit tests pass; coverage ≥ 95%.
5. Existing command hook tests unaffected.

## Testing Strategy

- All file I/O tests use `tmp_path`.
- Model serialization tests are pure in-memory.
- AAA pattern throughout.
- Run via `run_quality_gate()` after implementation.
