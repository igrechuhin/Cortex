"""Unit tests for compression file-type detection."""

from pathlib import Path

from cortex.tools.compress.detect import detect_file_type


def test_detect_file_type_uses_extension_map_for_markdown(tmp_path: Path) -> None:
    # Arrange
    path = tmp_path / "notes.md"
    _ = path.write_text("# Title\nSome prose.\n", encoding="utf-8")

    # Act
    result = detect_file_type(path)

    # Assert
    assert result == "natural_language"


def test_detect_file_type_uses_extension_map_for_code(tmp_path: Path) -> None:
    # Arrange
    path = tmp_path / "module.py"
    _ = path.write_text("def run() -> None:\n    return None\n", encoding="utf-8")

    # Act
    result = detect_file_type(path)

    # Assert
    assert result == "code"


def test_detect_file_type_uses_extension_map_for_config(tmp_path: Path) -> None:
    # Arrange
    path = tmp_path / "settings.json"
    _ = path.write_text('{"mode":"test"}\n', encoding="utf-8")

    # Act
    result = detect_file_type(path)

    # Assert
    assert result == "config"


def test_detect_file_type_fallback_marks_code_when_ratio_above_threshold(
    tmp_path: Path,
) -> None:
    # Arrange
    path = tmp_path / "snippet.txt"
    code_like_text = "\n".join(
        [
            "def build():",
            "    return value",
            "if ready:",
            "    execute();",
            "class Runner:",
            "plain language line",
        ]
    )
    _ = path.write_text(f"{code_like_text}\n", encoding="utf-8")

    # Act
    result = detect_file_type(path)

    # Assert
    assert result == "code"


def test_detect_file_type_fallback_marks_natural_language_when_ratio_low(
    tmp_path: Path,
) -> None:
    # Arrange
    path = tmp_path / "brief.txt"
    prose_text = "\n".join(
        [
            "This document explains the workflow.",
            "It keeps technical guidance concise.",
            "importantly this is still prose.",
            "Another sentence for context.",
        ]
    )
    _ = path.write_text(f"{prose_text}\n", encoding="utf-8")

    # Act
    result = detect_file_type(path)

    # Assert
    assert result == "natural_language"
