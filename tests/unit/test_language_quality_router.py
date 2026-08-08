from __future__ import annotations

import pytest

from cortex.core.constants import LANGUAGE_POST_EDIT_HOOK_COMMANDS
from cortex.services.framework_adapters.python_adapter import PythonAdapter
from cortex.services.language_quality_router import LanguageQualityRouter


def test_supported_languages_include_quality_and_hook_routed_languages() -> None:
    supported = LanguageQualityRouter.supported_languages()
    for language in (
        "python",
        "typescript",
        "javascript",
        "rust",
        "go",
        "java",
        "swift",
        "kotlin",
        "csharp",
        "php",
    ):
        assert language in supported


def test_get_adapter_returns_expected_adapter_for_python() -> None:
    adapter = LanguageQualityRouter.get_adapter("python", project_root=None)
    assert isinstance(adapter, PythonAdapter)


@pytest.mark.parametrize(
    ("language", "expected"),
    [
        ("  PYTHON  ", LANGUAGE_POST_EDIT_HOOK_COMMANDS["python"]),
        ("kotlin", None),
        ("unknown", None),
    ],
)
def test_get_post_edit_hook_command(language: str, expected: str | None) -> None:
    """Lookup normalizes case/whitespace; unmapped languages yield None."""
    assert LanguageQualityRouter.get_post_edit_hook_command(language) == expected


def test_post_edit_hook_commands_never_run_a_full_test_suite() -> None:
    """Per-edit hooks must stay fast: no suite runners in the command table.

    A full suite per Edit stalls the agent loop for minutes and fails edits on
    unrelated red tests; suites belong in run_quality_gate() at commit time.
    """
    banned = ("pytest", "npm test", "cargo test", "go test", "dotnet test", "mvn")
    for language, command in LANGUAGE_POST_EDIT_HOOK_COMMANDS.items():
        if command is None:
            continue
        assert not any(b in command for b in banned), f"{language}: {command}"


def test_post_edit_hook_commands_are_sourced_from_constants() -> None:
    for language, expected in LANGUAGE_POST_EDIT_HOOK_COMMANDS.items():
        assert LanguageQualityRouter.get_post_edit_hook_command(language) == expected
