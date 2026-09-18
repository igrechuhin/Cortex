"""Unit tests for detect_or_use_language (project language detection)."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

from cortex.tools.execution.pre_commit_helpers_language import detect_or_use_language


def test_language_detected_by_walking_up_from_subdir() -> None:
    """When root_str is a subdir of a Python project, language is detected by walking up."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _ = (root / "pyproject.toml").write_text("[project]\nname = 'test'")
        subdir = root / "src" / "app"
        subdir.mkdir(parents=True)

        result = detect_or_use_language(language=None, root_str=str(subdir))

        assert not isinstance(
            result, str
        ), "Expected (LanguageInfo, root), not error JSON"
        language_info, root_to_use = result
        assert language_info.language == "python"
        assert Path(root_to_use).resolve() == root.resolve()


def test_error_when_no_language_markers_found() -> None:
    """Returns an error string when no language markers exist anywhere up the tree."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch(
            "cortex.tools.execution.pre_commit_helpers_language.detect_language_at_path",
            return_value=None,
        ):
            result = detect_or_use_language(language=None, root_str=tmpdir)

        assert isinstance(
            result, str
        ), "Expected error string, not (LanguageInfo, root)"
        assert "Could not detect project language" in result
