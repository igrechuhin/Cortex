from __future__ import annotations

from pathlib import Path

from cortex.setup.post_edit_hook_detection import detect_post_edit_hook_language


def test_detect_post_edit_hook_language_returns_unknown_when_no_markers(
    tmp_path: Path,
) -> None:
    assert detect_post_edit_hook_language(tmp_path) == "unknown"


def test_detect_post_edit_hook_language_detects_python(tmp_path: Path) -> None:
    _ = (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'x'\n", encoding="utf-8"
    )
    assert detect_post_edit_hook_language(tmp_path) == "python"


def test_detect_post_edit_hook_language_detects_swift(tmp_path: Path) -> None:
    _ = (tmp_path / "Package.swift").write_text(
        "// swift-tools-version:5.9\nimport PackageDescription\n", encoding="utf-8"
    )
    assert detect_post_edit_hook_language(tmp_path) == "swift"


def test_detect_post_edit_hook_language_detects_java(tmp_path: Path) -> None:
    _ = (tmp_path / "pom.xml").write_text("<project></project>\n", encoding="utf-8")
    assert detect_post_edit_hook_language(tmp_path) == "java"
