from __future__ import annotations

import json
from pathlib import Path

from cortex.core.constants import HOOK_DEFAULT_MODEL
from cortex.setup.claude_settings import write_agent_hook, write_prompt_hook
from cortex.setup.hook_models import AgentHookEntry, HookType, PromptHookEntry


def test_prompt_hook_entry_serializes_type_prompt() -> None:
    entry = PromptHookEntry(type=HookType.PROMPT, prompt="Check output")

    dumped = entry.model_dump()

    assert dumped["type"] == "prompt"
    assert dumped["prompt"] == "Check output"


def test_prompt_hook_entry_status_message_alias() -> None:
    entry = PromptHookEntry(
        type=HookType.PROMPT,
        prompt="Check output",
        status_message="Running prompt validation",
    )

    dumped = entry.model_dump(by_alias=True)

    assert dumped["statusMessage"] == "Running prompt validation"
    assert "status_message" not in dumped


def test_prompt_hook_entry_none_fields_excluded() -> None:
    entry = PromptHookEntry(type=HookType.PROMPT, prompt="Check output")

    dumped = entry.model_dump()

    assert dumped == {"type": "prompt", "prompt": "Check output"}


def test_agent_hook_entry_serializes_type_agent() -> None:
    entry = AgentHookEntry(type=HookType.AGENT, prompt="Validate behavior")

    dumped = entry.model_dump()

    assert dumped["type"] == "agent"
    assert dumped["prompt"] == "Validate behavior"


def test_write_prompt_hook_writes_to_settings_json(tmp_path: Path) -> None:
    settings_path = tmp_path / ".claude" / "settings.json"

    write_prompt_hook(
        settings_path,
        matcher="Edit",
        prompt="Review changed file",
        model="claude-sonnet-4-5",
        timeout=45,
        status_message="Prompt hook running",
    )

    data = json.loads(settings_path.read_text(encoding="utf-8"))
    hook_entry = data["hooks"]["PostToolUse"][0]["hooks"][0]
    assert hook_entry == {
        "type": "prompt",
        "prompt": "Review changed file",
        "model": "claude-sonnet-4-5",
        "timeout": 45,
        "statusMessage": "Prompt hook running",
    }


def test_write_prompt_hook_dedup_same_prompt(tmp_path: Path) -> None:
    settings_path = tmp_path / ".claude" / "settings.json"

    write_prompt_hook(settings_path, matcher="Edit", prompt="Dedup me")
    write_prompt_hook(settings_path, matcher="Edit", prompt="Dedup me")

    data = json.loads(settings_path.read_text(encoding="utf-8"))
    hooks = data["hooks"]["PostToolUse"][0]["hooks"]
    assert len(hooks) == 1
    assert hooks[0]["type"] == "prompt"
    assert hooks[0]["prompt"] == "Dedup me"


def test_write_prompt_hook_dedup_different_prompt(tmp_path: Path) -> None:
    settings_path = tmp_path / ".claude" / "settings.json"

    write_prompt_hook(settings_path, matcher="Edit", prompt="Prompt A")
    write_prompt_hook(settings_path, matcher="Edit", prompt="Prompt B")

    data = json.loads(settings_path.read_text(encoding="utf-8"))
    hooks = data["hooks"]["PostToolUse"][0]["hooks"]
    assert len(hooks) == 2
    assert hooks[0]["prompt"] == "Prompt A"
    assert hooks[1]["prompt"] == "Prompt B"


def test_write_agent_hook_writes_agent_entry(tmp_path: Path) -> None:
    settings_path = tmp_path / ".claude" / "settings.json"

    write_agent_hook(settings_path, matcher="Edit", prompt="Run deeper verification")

    data = json.loads(settings_path.read_text(encoding="utf-8"))
    hook_entry = data["hooks"]["PostToolUse"][0]["hooks"][0]
    assert hook_entry["type"] == "agent"
    assert hook_entry["prompt"] == "Run deeper verification"
    assert hook_entry["model"] == HOOK_DEFAULT_MODEL


def test_default_model_written_when_none(tmp_path: Path) -> None:
    settings_path = tmp_path / ".claude" / "settings.json"

    write_prompt_hook(settings_path, matcher="Edit", prompt="Use default model")

    data = json.loads(settings_path.read_text(encoding="utf-8"))
    hook_entry = data["hooks"]["PostToolUse"][0]["hooks"][0]
    assert hook_entry["model"] == HOOK_DEFAULT_MODEL
