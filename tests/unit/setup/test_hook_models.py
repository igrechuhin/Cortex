from __future__ import annotations

import pytest

from cortex.setup.hook_models import CommandHookEntry, HookCondition, HookType


def test_to_matcher_string_no_pattern() -> None:
    condition = HookCondition(tool="Edit")

    result = condition.to_matcher_string()

    assert result == "Edit"


def test_to_matcher_string_with_pattern() -> None:
    condition = HookCondition(tool="Bash", pattern="git *")

    result = condition.to_matcher_string()

    assert result == "Bash(git *)"


def test_to_matcher_string_rejects_blank_tool_at_runtime() -> None:
    condition = HookCondition.model_construct(tool="  ", pattern=None)

    with pytest.raises(ValueError, match="tool must be non-empty"):
        _ = condition.to_matcher_string()


def test_hook_entry_omits_once_when_false() -> None:
    entry = CommandHookEntry(type=HookType.COMMAND, command="python3 -m pytest")

    dumped = entry.model_dump()

    assert dumped == {"type": "command", "command": "python3 -m pytest"}
    assert "once" not in dumped


def test_hook_entry_includes_once_when_true() -> None:
    entry = CommandHookEntry(
        type=HookType.COMMAND, command="python3 -m pytest", once=True
    )

    dumped = entry.model_dump()

    assert dumped["type"] == "command"
    assert dumped["command"] == "python3 -m pytest"
    assert dumped["once"] is True
