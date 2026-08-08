import pytest

from cortex.core.constants import LANGUAGE_POST_EDIT_HOOK_COMMANDS
from cortex.setup.hook_models import HookCondition
from cortex.setup.hook_templates import HookTemplates

_LANGUAGES_WITH_HOOKS = [
    language
    for language, command in LANGUAGE_POST_EDIT_HOOK_COMMANDS.items()
    if command is not None
]


@pytest.mark.parametrize("language", _LANGUAGES_WITH_HOOKS)
def test_get_post_edit_hook_uses_command_table(language: str) -> None:
    """Every mapped language yields its table command plus an Edit condition."""
    result = HookTemplates.get_post_edit_hook(language)

    assert result is not None
    command, condition = result
    assert command == LANGUAGE_POST_EDIT_HOOK_COMMANDS[language]
    assert condition.tool == "Edit"


@pytest.mark.parametrize(
    ("language", "expected_condition"),
    [
        ("python", HookCondition(tool="Edit", pattern="**/*.py")),
        ("typescript", HookCondition(tool="Edit", pattern="**/*.ts")),
        ("php", HookCondition(tool="Edit", pattern="**/*.php")),
        ("  PYTHON  ", HookCondition(tool="Edit", pattern="**/*.py")),
        ("go", HookCondition(tool="Edit")),
    ],
)
def test_get_post_edit_hook_conditions(
    language: str, expected_condition: HookCondition
) -> None:
    """File-scoped conditions apply to Python/TypeScript/PHP; others match all edits."""
    result = HookTemplates.get_post_edit_hook(language)

    assert result is not None
    assert result[1] == expected_condition


@pytest.mark.parametrize("language", ["kotlin", "java", "swift", "csharp", "nonesuch"])
def test_get_post_edit_hook_returns_none_without_a_fast_check(language: str) -> None:
    """Languages whose only check is a whole-project build get no per-edit hook."""
    assert HookTemplates.get_post_edit_hook(language) is None
