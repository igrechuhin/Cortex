from __future__ import annotations

import pytest

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
    ):
        assert language in supported


def test_get_adapter_returns_expected_adapter_for_python() -> None:
    adapter = LanguageQualityRouter.get_adapter("python", project_root=None)
    assert isinstance(adapter, PythonAdapter)


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
        ("kotlin", None),
        ("unknown", None),
    ],
)
def test_get_post_edit_hook_command(language: str, expected: str | None) -> None:
    assert LanguageQualityRouter.get_post_edit_hook_command(language) == expected
