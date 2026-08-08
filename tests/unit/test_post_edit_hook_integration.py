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


def _matcher(settings: dict[str, object]) -> str | None:
    hooks_value = settings.get("hooks")
    if not isinstance(hooks_value, dict):
        return None
    hooks = cast(dict[str, object], hooks_value)
    post_tool_use_value = hooks.get("PostToolUse")
    if not isinstance(post_tool_use_value, list) or not post_tool_use_value:
        return None
    post_tool_use = cast(list[object], post_tool_use_value)
    first_entry = post_tool_use[0]
    if not isinstance(first_entry, dict):
        return None
    entry = cast(dict[str, object], first_entry)
    matcher = entry.get("matcher")
    return matcher if isinstance(matcher, str) else None


def _conditions(settings: dict[str, object]) -> list[object] | None:
    hooks_value = settings.get("hooks")
    if not isinstance(hooks_value, dict):
        return None
    hooks = cast(dict[str, object], hooks_value)
    post_tool_use_value = hooks.get("PostToolUse")
    if not isinstance(post_tool_use_value, list) or not post_tool_use_value:
        return None
    post_tool_use = cast(list[object], post_tool_use_value)
    first_entry = post_tool_use[0]
    if not isinstance(first_entry, dict):
        return None
    entry = cast(dict[str, object], first_entry)
    hook_list_value = entry.get("hooks")
    if not isinstance(hook_list_value, list) or not hook_list_value:
        return None
    hook_list = cast(list[object], hook_list_value)
    first_hook = hook_list[0]
    if not isinstance(first_hook, dict):
        return None
    hook = cast(dict[str, object], first_hook)
    conditions = hook.get("conditions")
    if not isinstance(conditions, list):
        return None
    return cast(list[object], conditions)


class TestPythonProjectHookEmission:
    def test_python_project_gets_pytest_hook(self, tmp_path: Path) -> None:
        _ = (tmp_path / "pyproject.toml").write_text(
            "[project]\nname = 'myapp'\n", encoding="utf-8"
        )

        hook_spec = HookTemplates.get_post_edit_hook("python")
        assert hook_spec is not None
        command, condition = hook_spec
        changed = ensure_post_edit_hook_in_project_claude_settings(
            tmp_path, command=command, condition=condition
        )

        assert changed is True
        settings = _read_settings(tmp_path)
        assert _hook_command(settings) == command
        assert _matcher(settings) == "Edit(**/*.py)"
        assert _conditions(settings) == [{"tool": "Edit", "pattern": "**/*.py"}]

    def test_python_hook_idempotent_on_second_call(self, tmp_path: Path) -> None:
        hook_spec = HookTemplates.get_post_edit_hook("python")
        assert hook_spec is not None
        command, condition = hook_spec
        _ = ensure_post_edit_hook_in_project_claude_settings(
            tmp_path, command=command, condition=condition
        )

        changed = ensure_post_edit_hook_in_project_claude_settings(
            tmp_path, command=command, condition=condition
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

        hook_spec = HookTemplates.get_post_edit_hook("python")
        assert hook_spec is not None
        command, condition = hook_spec
        _ = ensure_post_edit_hook_in_project_claude_settings(
            tmp_path, command=command, condition=condition
        )

        settings = _read_settings(tmp_path)
        assert settings.get("permissions") == {"allow": ["Bash(pytest:*)"]}
        assert _hook_command(settings) == command


class TestPhpProjectHookEmission:
    def test_php_project_gets_phpstan_hook(self, tmp_path: Path) -> None:
        _ = (tmp_path / "composer.json").write_text(
            '{"name":"acme/app"}', encoding="utf-8"
        )

        hook_spec = HookTemplates.get_post_edit_hook("php")
        assert hook_spec is not None
        command, condition = hook_spec
        changed = ensure_post_edit_hook_in_project_claude_settings(
            tmp_path, command=command, condition=condition
        )

        assert changed is True
        settings = _read_settings(tmp_path)
        assert _hook_command(settings) == command
        assert _matcher(settings) == "Edit(**/*.php)"

    def test_php_hook_idempotent_on_second_call(self, tmp_path: Path) -> None:
        hook_spec = HookTemplates.get_post_edit_hook("php")
        assert hook_spec is not None
        command, condition = hook_spec
        _ = ensure_post_edit_hook_in_project_claude_settings(
            tmp_path, command=command, condition=condition
        )

        changed = ensure_post_edit_hook_in_project_claude_settings(
            tmp_path, command=command, condition=condition
        )

        assert changed is False


class TestUnknownLanguageFallback:
    def test_unknown_language_returns_none_from_templates(self) -> None:
        assert HookTemplates.get_post_edit_hook("kotlin") is None
        assert HookTemplates.get_post_edit_hook("elixir") is None
        assert HookTemplates.get_post_edit_hook("") is None

    def test_build_only_languages_get_no_per_edit_hook(self) -> None:
        """Swift/Java/C# have no sub-second check, so no hook is emitted."""
        for language in ("swift", "java", "csharp"):
            assert HookTemplates.get_post_edit_hook(language) is None

    def test_no_settings_file_written_when_no_command(self, tmp_path: Path) -> None:
        command = HookTemplates.get_post_edit_hook("kotlin")
        assert command is None
        settings_path = tmp_path / ".claude" / "settings.json"
        assert not settings_path.exists()


@pytest.mark.parametrize(
    ("language", "expected_fragment"),
    [
        ("typescript", "tsc"),
        ("javascript", "eslint"),
        ("rust", "cargo check"),
        ("go", "go vet"),
        ("php", "phpstan"),
    ],
)
def test_all_supported_languages_produce_valid_hook_in_project(
    tmp_path: Path, language: str, expected_fragment: str
) -> None:
    hook_spec = HookTemplates.get_post_edit_hook(language)
    assert hook_spec is not None, f"Expected a command for {language}"
    command, condition = hook_spec

    changed = ensure_post_edit_hook_in_project_claude_settings(
        tmp_path, command=command, condition=condition
    )

    assert changed is True
    settings = _read_settings(tmp_path)
    hook_cmd = _hook_command(settings)
    assert hook_cmd is not None
    assert expected_fragment in hook_cmd
