from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import cast

import pytest

from cortex.setup.post_edit_hook_runtime import apply_project_post_edit_hook


def _read_hook_command(project_root: Path) -> str | None:
    settings_path = project_root / ".claude" / "settings.json"
    settings = cast(
        dict[str, object], json.loads(settings_path.read_text(encoding="utf-8"))
    )
    hooks_value = settings.get("hooks")
    if not isinstance(hooks_value, dict):
        return None
    hooks = cast(dict[str, object], hooks_value)
    post_tool_use_value = hooks.get("PostToolUse")
    if not isinstance(post_tool_use_value, list) or not post_tool_use_value:
        return None
    post_tool_use = cast(list[object], post_tool_use_value)
    first_entry_value = post_tool_use[0]
    if not isinstance(first_entry_value, dict):
        return None
    entry = cast(dict[str, object], first_entry_value)
    inner_hooks = entry.get("hooks")
    if not isinstance(inner_hooks, list) or not inner_hooks:
        return None
    hook_items = cast(list[object], inner_hooks)
    first_hook_value = hook_items[0]
    if not isinstance(first_hook_value, dict):
        return None
    hook = cast(dict[str, object], first_hook_value)
    command = hook.get("command")
    return command if isinstance(command, str) else None


def test_apply_project_post_edit_hook_writes_python_hook(tmp_path: Path) -> None:
    _ = (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'myapp'\n", encoding="utf-8"
    )

    detected_language, changed = apply_project_post_edit_hook(tmp_path)

    assert detected_language == "python"
    assert changed is True
    assert (
        _read_hook_command(tmp_path)
        == "python3 -m pytest tests/ --timeout=30 -x -q 2>&1 | tail -20"
    )


def test_apply_project_post_edit_hook_is_idempotent(tmp_path: Path) -> None:
    _ = (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'myapp'\n", encoding="utf-8"
    )

    first_language, first_changed = apply_project_post_edit_hook(tmp_path)
    second_language, second_changed = apply_project_post_edit_hook(tmp_path)

    assert first_language == "python"
    assert first_changed is True
    assert second_language == "python"
    assert second_changed is False


def test_apply_project_post_edit_hook_unknown_language_no_write(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING):
        detected_language, changed = apply_project_post_edit_hook(tmp_path)

    assert detected_language == "unknown"
    assert changed is False
    assert not (tmp_path / ".claude" / "settings.json").exists()
