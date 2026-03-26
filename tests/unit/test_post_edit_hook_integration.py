"""Integration tests for post-edit hook emission during project setup.

Verifies that ensure_post_edit_hook_in_project_claude_settings writes the
correct language-specific hook command into a temporary project directory,
simulating what the migrate/initialize prompts instruct agents to do.
"""

import json
from pathlib import Path
from typing import cast

import pytest

from cortex.setup.claude_settings import (
    ensure_post_edit_hook_in_project_claude_settings,
)
from cortex.setup.hook_templates import HookTemplates


def _read_settings(project_root: Path) -> dict[str, object]:
    settings_path = project_root / ".claude" / "settings.json"
    return json.loads(settings_path.read_text(encoding="utf-8"))


def _hook_command(settings: dict[str, object]) -> str | None:
    hooks_value = settings.get("hooks")
    if not isinstance(hooks_value, dict):
        return None
    hooks = cast(dict[str, object], hooks_value)
    post_tool_use_value = hooks.get("PostToolUse")
    if not isinstance(post_tool_use_value, list) or not post_tool_use_value:
        return None
    post_tool_use = cast(list[object], post_tool_use_value)
    entry_value = post_tool_use[0]
    if not isinstance(entry_value, dict):
        return None
    entry = cast(dict[str, object], entry_value)
    hook_list_value = entry.get("hooks")
    if not isinstance(hook_list_value, list) or not hook_list_value:
        return None
    hook_list = cast(list[object], hook_list_value)
    first_hook_value = hook_list[0]
    if not isinstance(first_hook_value, dict):
        return None
    first_hook = cast(dict[str, object], first_hook_value)
    command = first_hook.get("command")
    return command if isinstance(command, str) else None


class TestPythonProjectHookEmission:
    def test_python_project_gets_pytest_hook(self, tmp_path: Path) -> None:
        _ = (tmp_path / "pyproject.toml").write_text(
            "[project]\nname = 'myapp'\n", encoding="utf-8"
        )

        command = HookTemplates.get_post_edit_hook("python")
        assert command is not None
        changed = ensure_post_edit_hook_in_project_claude_settings(
            tmp_path, command=command
        )

        assert changed is True
        settings = _read_settings(tmp_path)
        assert (
            _hook_command(settings)
            == "python3 -m pytest tests/ --timeout=30 -x -q 2>&1 | tail -20"
        )

    def test_python_hook_idempotent_on_second_call(self, tmp_path: Path) -> None:
        command = HookTemplates.get_post_edit_hook("python")
        assert command is not None
        _ = ensure_post_edit_hook_in_project_claude_settings(tmp_path, command=command)

        changed = ensure_post_edit_hook_in_project_claude_settings(
            tmp_path, command=command
        )

        assert changed is False

    def test_python_hook_preserves_existing_permissions_key(
        self, tmp_path: Path
    ) -> None:
        settings_path = tmp_path / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        _ = settings_path.write_text(
            json.dumps({"permissions": {"allow": ["Bash(pytest:*)"]}}),
            encoding="utf-8",
        )

        command = HookTemplates.get_post_edit_hook("python")
        assert command is not None
        _ = ensure_post_edit_hook_in_project_claude_settings(tmp_path, command=command)

        settings = _read_settings(tmp_path)
        assert settings.get("permissions") == {"allow": ["Bash(pytest:*)"]}
        assert _hook_command(settings) == command


class TestSwiftProjectHookEmission:
    def test_swift_project_gets_build_hook(self, tmp_path: Path) -> None:
        _ = (tmp_path / "Package.swift").write_text(
            "// swift-tools-version:5.9\nimport PackageDescription\n", encoding="utf-8"
        )

        command = HookTemplates.get_post_edit_hook("swift")
        assert command is not None
        changed = ensure_post_edit_hook_in_project_claude_settings(
            tmp_path, command=command
        )

        assert changed is True
        settings = _read_settings(tmp_path)
        assert _hook_command(settings) == "swift build 2>&1 | tail -20"

    def test_swift_hook_idempotent_on_second_call(self, tmp_path: Path) -> None:
        command = HookTemplates.get_post_edit_hook("swift")
        assert command is not None
        _ = ensure_post_edit_hook_in_project_claude_settings(tmp_path, command=command)

        changed = ensure_post_edit_hook_in_project_claude_settings(
            tmp_path, command=command
        )

        assert changed is False


class TestUnknownLanguageFallback:
    def test_unknown_language_returns_none_from_templates(self) -> None:
        assert HookTemplates.get_post_edit_hook("kotlin") is None
        assert HookTemplates.get_post_edit_hook("elixir") is None
        assert HookTemplates.get_post_edit_hook("") is None

    def test_no_settings_file_written_when_no_command(self, tmp_path: Path) -> None:
        command = HookTemplates.get_post_edit_hook("kotlin")
        assert command is None
        settings_path = tmp_path / ".claude" / "settings.json"
        assert not settings_path.exists()


@pytest.mark.parametrize(
    ("language", "expected_fragment"),
    [
        ("typescript", "npm test"),
        ("javascript", "npm test"),
        ("rust", "cargo test"),
        ("go", "go test"),
        ("java", "mvnw test"),
    ],
)
def test_all_supported_languages_produce_valid_hook_in_project(
    tmp_path: Path, language: str, expected_fragment: str
) -> None:
    command = HookTemplates.get_post_edit_hook(language)
    assert command is not None, f"Expected a command for {language}"

    changed = ensure_post_edit_hook_in_project_claude_settings(
        tmp_path, command=command
    )

    assert changed is True
    settings = _read_settings(tmp_path)
    hook_cmd = _hook_command(settings)
    assert hook_cmd is not None
    assert expected_fragment in hook_cmd
