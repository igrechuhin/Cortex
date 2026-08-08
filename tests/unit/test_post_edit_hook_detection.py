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


def test_detect_post_edit_hook_language_detects_php(tmp_path: Path) -> None:
    _ = (tmp_path / "composer.json").write_text('{"name":"acme/app"}', encoding="utf-8")
    _ = (tmp_path / "package.json").write_text('{"name":"assets"}', encoding="utf-8")
    assert detect_post_edit_hook_language(tmp_path) == "php"


def test_detect_post_edit_hook_language_returns_unknown_for_swift(
    tmp_path: Path,
) -> None:
    """Swift's only check is a whole-project build, so it gets no per-edit hook."""
    _ = (tmp_path / "Package.swift").write_text(
        "// swift-tools-version:5.9\nimport PackageDescription\n", encoding="utf-8"
    )
    assert detect_post_edit_hook_language(tmp_path) == "unknown"


def test_detect_post_edit_hook_language_returns_unknown_for_java(
    tmp_path: Path,
) -> None:
    """Maven builds are too slow for a per-edit hook."""
    _ = (tmp_path / "pom.xml").write_text("<project></project>\n", encoding="utf-8")
    assert detect_post_edit_hook_language(tmp_path) == "unknown"


def test_detect_post_edit_hook_language_detects_typescript(tmp_path: Path) -> None:
    _ = (tmp_path / "tsconfig.json").write_text("{}", encoding="utf-8")
    _ = (tmp_path / "package.json").write_text(
        '{"name":"x","devDependencies":{"typescript":"^5.0.0"}}\n',
        encoding="utf-8",
    )
    assert detect_post_edit_hook_language(tmp_path) == "typescript"


def test_detect_post_edit_hook_language_returns_unknown_for_kotlin(
    tmp_path: Path,
) -> None:
    _ = (tmp_path / "build.gradle.kts").write_text("plugins {}\n", encoding="utf-8")
    _ = (tmp_path / "Main.kt").write_text(
        'fun main() = println("hi")\n', encoding="utf-8"
    )
    assert detect_post_edit_hook_language(tmp_path) == "unknown"
