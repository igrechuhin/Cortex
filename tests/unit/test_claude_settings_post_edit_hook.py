import json
from pathlib import Path
from typing import cast

import pytest

from cortex.setup.claude_settings import (
    ClaudeSettingsError,
    ensure_post_edit_hook_in_project_claude_settings,
    merge_post_tool_use_edit_hook,
    remove_once_hooks,
    write_once_hook,
)
from cortex.setup.hook_models import HookCondition


def _write_settings(settings_path: Path, payload: dict[str, object]) -> None:
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    _ = settings_path.write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )


def _settings_with_once_hooks() -> dict[str, object]:
    return {
        "hooks": {
            "PostToolUse": [
                {
                    "matcher": "Edit",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "python3 -m pytest tests/ -q",
                            "once": True,
                        },
                        {
                            "type": "command",
                            "command": "python3 -m pytest tests/unit -q",
                        },
                    ],
                },
                {
                    "matcher": "Bash",
                    "hooks": [
                        {"type": "command", "command": "echo one-time", "once": True}
                    ],
                },
            ]
        }
    }


def test_merge_adds_hook_to_empty_settings() -> None:
    settings: dict[str, object] = {}

    merged, changed = merge_post_tool_use_edit_hook(
        settings, command="swift build 2>&1 | tail -20"
    )

    assert changed is True
    assert merged["hooks"] == {
        "PostToolUse": [
            {
                "matcher": "Edit",
                "hooks": [
                    {"type": "command", "command": "swift build 2>&1 | tail -20"}
                ],
            }
        ]
    }


def test_merge_preserves_unrelated_keys() -> None:
    settings: dict[str, object] = {"foo": {"bar": 1}}

    merged, _changed = merge_post_tool_use_edit_hook(
        settings, command="go test ./... 2>&1 | tail -20"
    )

    assert merged["foo"] == {"bar": 1}


def test_merge_does_not_add_duplicate_command_hook() -> None:
    settings: dict[str, object] = {
        "hooks": {
            "PostToolUse": [
                {
                    "matcher": "Edit",
                    "hooks": [
                        {"type": "command", "command": "cargo test 2>&1 | tail -20"}
                    ],
                }
            ]
        }
    }

    merged, changed = merge_post_tool_use_edit_hook(
        settings, command="cargo test 2>&1 | tail -20"
    )

    assert changed is False
    assert merged == settings


def test_merge_adds_distinct_once_hook_for_same_command() -> None:
    settings: dict[str, object] = {
        "hooks": {
            "PostToolUse": [
                {
                    "matcher": "Edit",
                    "hooks": [
                        {"type": "command", "command": "cargo test 2>&1 | tail -20"}
                    ],
                }
            ]
        }
    }

    merged, changed = merge_post_tool_use_edit_hook(
        settings, command="cargo test 2>&1 | tail -20", once=True
    )

    assert changed is True
    hooks = cast(dict[str, object], merged["hooks"])
    post_tool_use = cast(list[object], hooks["PostToolUse"])
    entry = cast(dict[str, object], post_tool_use[0])
    command_hooks = cast(list[object], entry["hooks"])
    assert command_hooks == [
        {"type": "command", "command": "cargo test 2>&1 | tail -20"},
        {"type": "command", "command": "cargo test 2>&1 | tail -20", "once": True},
    ]


def test_merge_deduplicates_command_when_once_matches() -> None:
    settings: dict[str, object] = {}

    merged, first_changed = merge_post_tool_use_edit_hook(
        settings, command="cargo test 2>&1 | tail -20", once=True
    )
    merged, second_changed = merge_post_tool_use_edit_hook(
        merged, command="cargo test 2>&1 | tail -20", once=True
    )

    assert first_changed is True
    assert second_changed is False
    hooks = cast(dict[str, object], merged["hooks"])
    post_tool_use = cast(list[object], hooks["PostToolUse"])
    entry = cast(dict[str, object], post_tool_use[0])
    command_hooks = cast(list[object], entry["hooks"])
    assert command_hooks == [
        {"type": "command", "command": "cargo test 2>&1 | tail -20", "once": True}
    ]


def test_merge_adds_command_when_matcher_exists_but_command_missing() -> None:
    settings: dict[str, object] = {
        "hooks": {"PostToolUse": [{"matcher": "Edit", "hooks": []}]}
    }

    merged, changed = merge_post_tool_use_edit_hook(
        settings, command="npm test --if-present 2>&1 | tail -20"
    )

    assert changed is True
    hooks = cast(dict[str, object], merged["hooks"])
    post_tool_use = cast(list[object], hooks["PostToolUse"])
    entry = cast(dict[str, object], post_tool_use[0])
    assert cast(list[object], entry["hooks"]) == [
        {"type": "command", "command": "npm test --if-present 2>&1 | tail -20"}
    ]


def test_merge_raises_on_invalid_hooks_shape() -> None:
    settings: dict[str, object] = {"hooks": "not-a-dict"}
    with pytest.raises(ClaudeSettingsError):
        _ = merge_post_tool_use_edit_hook(settings, command="x")


def test_ensure_writes_settings_file_when_missing(tmp_path: Path) -> None:
    changed = ensure_post_edit_hook_in_project_claude_settings(
        tmp_path, command="python3 -m pytest tests/ --timeout=30 -x -q 2>&1 | tail -20"
    )

    assert changed is True
    settings_path = tmp_path / ".claude" / "settings.json"
    data = json.loads(settings_path.read_text(encoding="utf-8"))
    assert data["hooks"]["PostToolUse"][0]["matcher"] == "Edit"


def test_ensure_is_noop_when_command_already_present(tmp_path: Path) -> None:
    settings_path = tmp_path / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    _ = settings_path.write_text(
        json.dumps(
            {
                "hooks": {
                    "PostToolUse": [
                        {
                            "matcher": "Edit",
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "swift build 2>&1 | tail -20",
                                }
                            ],
                        }
                    ]
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    changed = ensure_post_edit_hook_in_project_claude_settings(
        tmp_path, command="swift build 2>&1 | tail -20"
    )

    assert changed is False


def test_merge_deduplicates_by_same_matcher_and_command_with_condition() -> None:
    settings: dict[str, object] = {
        "hooks": {
            "PostToolUse": [
                {
                    "matcher": "Edit(**/*.py)",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "python3 -m pytest tests/ -q",
                            "conditions": [{"tool": "Edit", "pattern": "**/*.py"}],
                        }
                    ],
                }
            ]
        }
    }

    merged, changed = merge_post_tool_use_edit_hook(
        settings,
        command="python3 -m pytest tests/ -q",
        condition=HookCondition(tool="Edit", pattern="**/*.py"),
    )

    assert changed is False
    assert merged == settings


def test_merge_allows_same_command_for_different_matchers() -> None:
    settings: dict[str, object] = {
        "hooks": {
            "PostToolUse": [
                {
                    "matcher": "Edit(**/*.py)",
                    "hooks": [
                        {"type": "command", "command": "python3 -m pytest tests/ -q"}
                    ],
                }
            ]
        }
    }

    merged, changed = merge_post_tool_use_edit_hook(
        settings,
        command="python3 -m pytest tests/ -q",
        condition=HookCondition(tool="Edit", pattern="**/*.ts"),
    )

    assert changed is True
    hooks = cast(dict[str, object], merged["hooks"])
    post_tool_use = cast(list[object], hooks["PostToolUse"])
    assert len(post_tool_use) == 2


def test_merge_writes_conditions_for_patterned_condition() -> None:
    settings: dict[str, object] = {}

    merged, changed = merge_post_tool_use_edit_hook(
        settings,
        command="python3 -m pytest tests/ -q",
        condition=HookCondition(tool="Edit", pattern="**/*.py"),
    )

    assert changed is True
    hooks = cast(dict[str, object], merged["hooks"])
    post_tool_use = cast(list[object], hooks["PostToolUse"])
    entry = cast(dict[str, object], post_tool_use[0])
    hook_list = cast(list[object], entry["hooks"])
    first_hook = cast(dict[str, object], hook_list[0])
    assert first_hook["conditions"] == [{"tool": "Edit", "pattern": "**/*.py"}]


def test_merge_omits_conditions_for_unpatterned_condition() -> None:
    settings: dict[str, object] = {}

    merged, changed = merge_post_tool_use_edit_hook(
        settings,
        command="swift build 2>&1 | tail -20",
        condition=HookCondition(tool="Edit"),
    )

    assert changed is True
    hooks = cast(dict[str, object], merged["hooks"])
    post_tool_use = cast(list[object], hooks["PostToolUse"])
    entry = cast(dict[str, object], post_tool_use[0])
    hook_list = cast(list[object], entry["hooks"])
    first_hook = cast(dict[str, object], hook_list[0])
    assert "conditions" not in first_hook


def test_merge_backfills_conditions_on_legacy_matching_command_hook() -> None:
    settings: dict[str, object] = {
        "hooks": {
            "PostToolUse": [
                {
                    "matcher": "Edit(**/*.py)",
                    "hooks": [
                        {"type": "command", "command": "python3 -m pytest tests/ -q"}
                    ],
                }
            ]
        }
    }

    merged, changed = merge_post_tool_use_edit_hook(
        settings,
        command="python3 -m pytest tests/ -q",
        condition=HookCondition(tool="Edit", pattern="**/*.py"),
    )

    assert changed is True
    hooks = cast(dict[str, object], merged["hooks"])
    post_tool_use = cast(list[object], hooks["PostToolUse"])
    entry = cast(dict[str, object], post_tool_use[0])
    hook_list = cast(list[object], entry["hooks"])
    first_hook = cast(dict[str, object], hook_list[0])
    assert first_hook["conditions"] == [{"tool": "Edit", "pattern": "**/*.py"}]


def test_write_once_hook_writes_once_entry(tmp_path: Path) -> None:
    settings_path = tmp_path / ".claude" / "settings.json"

    write_once_hook(settings_path, command="python3 -m pytest tests/ -q")

    data = json.loads(settings_path.read_text(encoding="utf-8"))
    hook_entry = data["hooks"]["PostToolUse"][0]["hooks"][0]
    assert hook_entry == {
        "type": "command",
        "command": "python3 -m pytest tests/ -q",
        "once": True,
    }


def test_write_once_hook_dedups_existing_once_hook(tmp_path: Path) -> None:
    settings_path = tmp_path / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    _ = settings_path.write_text(
        json.dumps(
            {
                "hooks": {
                    "PostToolUse": [
                        {
                            "matcher": "Edit",
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "python3 -m pytest tests/ -q",
                                    "once": True,
                                }
                            ],
                        }
                    ]
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    before = settings_path.read_text(encoding="utf-8")

    write_once_hook(settings_path, command="python3 -m pytest tests/ -q")

    after = settings_path.read_text(encoding="utf-8")
    assert after == before


def test_remove_once_hooks_removes_all_once_entries(tmp_path: Path) -> None:
    settings_path = tmp_path / ".claude" / "settings.json"
    _write_settings(settings_path, _settings_with_once_hooks())

    removed_count = remove_once_hooks(settings_path)

    assert removed_count == 2
    data = json.loads(settings_path.read_text(encoding="utf-8"))
    assert data["hooks"]["PostToolUse"][0]["hooks"] == [
        {"type": "command", "command": "python3 -m pytest tests/unit -q"}
    ]
    assert data["hooks"]["PostToolUse"][1]["hooks"] == []


def test_remove_once_hooks_returns_zero_when_no_once_entries(tmp_path: Path) -> None:
    settings_path = tmp_path / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    _ = settings_path.write_text(
        json.dumps(
            {
                "hooks": {
                    "PostToolUse": [
                        {
                            "matcher": "Edit",
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "python3 -m pytest tests/ -q",
                                }
                            ],
                        }
                    ]
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    before = settings_path.read_text(encoding="utf-8")

    removed_count = remove_once_hooks(settings_path)

    assert removed_count == 0
    assert settings_path.read_text(encoding="utf-8") == before
