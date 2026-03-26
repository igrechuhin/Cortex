import pytest

from cortex.setup.hook_templates import HookTemplates


@pytest.mark.parametrize(
    ("language", "expected"),
    [
        ("python", "python3 -m pytest tests/ --timeout=30 -x -q 2>&1 | tail -20"),
        ("swift", "swift build 2>&1 | tail -20"),
        ("typescript", "npm test --if-present 2>&1 | tail -20"),
        ("javascript", "npm test --if-present 2>&1 | tail -20"),
        ("rust", "cargo test 2>&1 | tail -20"),
        ("go", "go test ./... 2>&1 | tail -20"),
        ("java", "./mvnw test -q 2>&1 | tail -20"),
        ("  PYTHON  ", "python3 -m pytest tests/ --timeout=30 -x -q 2>&1 | tail -20"),
    ],
)
def test_get_post_edit_hook_supported_languages(language: str, expected: str) -> None:
    result = HookTemplates.get_post_edit_hook(language)
    assert result == expected


def test_get_post_edit_hook_unknown_language_returns_none() -> None:
    assert HookTemplates.get_post_edit_hook("kotlin") is None
