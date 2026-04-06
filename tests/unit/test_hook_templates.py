import pytest

from cortex.setup.hook_models import HookCondition
from cortex.setup.hook_templates import HookTemplates


@pytest.mark.parametrize(
    ("language", "expected_command", "expected_condition"),
    [
        (
            "python",
            "python3 -m pytest tests/ --timeout=30 -x -q 2>&1 | tail -20",
            HookCondition(tool="Edit", pattern="**/*.py"),
        ),
        ("swift", "swift build 2>&1 | tail -20", HookCondition(tool="Edit")),
        (
            "typescript",
            "npm test --if-present 2>&1 | tail -20",
            HookCondition(tool="Edit", pattern="**/*.ts"),
        ),
        (
            "javascript",
            "npm test --if-present 2>&1 | tail -20",
            HookCondition(tool="Edit"),
        ),
        ("rust", "cargo test 2>&1 | tail -20", HookCondition(tool="Edit")),
        ("go", "go test ./... 2>&1 | tail -20", HookCondition(tool="Edit")),
        ("java", "./mvnw test -q 2>&1 | tail -20", HookCondition(tool="Edit")),
        ("csharp", "dotnet test 2>&1 | tail -20", HookCondition(tool="Edit")),
        (
            "  PYTHON  ",
            "python3 -m pytest tests/ --timeout=30 -x -q 2>&1 | tail -20",
            HookCondition(tool="Edit", pattern="**/*.py"),
        ),
    ],
)
def test_get_post_edit_hook_supported_languages(
    language: str, expected_command: str, expected_condition: HookCondition
) -> None:
    result = HookTemplates.get_post_edit_hook(language)
    assert result == (expected_command, expected_condition)


def test_get_post_edit_hook_unknown_language_returns_none() -> None:
    assert HookTemplates.get_post_edit_hook("kotlin") is None
