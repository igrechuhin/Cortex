from __future__ import annotations

from pathlib import Path

from cortex.setup.migration_language_detection import detect_languages_for_migration


def test_detect_languages_for_migration_returns_empty_when_no_markers(
    tmp_path: Path,
) -> None:
    assert detect_languages_for_migration(tmp_path) == []


def test_detect_languages_for_migration_detects_swift_first(tmp_path: Path) -> None:
    _ = (tmp_path / "Package.swift").write_text(
        "// swift-tools-version:5.9\nimport PackageDescription\n",
        encoding="utf-8",
    )
    _ = (tmp_path / "pyproject.toml").write_text(
        "[project]\nname='x'\n", encoding="utf-8"
    )

    assert detect_languages_for_migration(tmp_path) == ["swift", "python"]


def test_detect_languages_for_migration_prefers_typescript_over_javascript(
    tmp_path: Path,
) -> None:
    _ = (tmp_path / "package.json").write_text('{"name":"x"}\n', encoding="utf-8")
    _ = (tmp_path / "tsconfig.json").write_text("{}\n", encoding="utf-8")

    assert detect_languages_for_migration(tmp_path) == ["typescript"]


def test_detect_languages_for_migration_detects_javascript_when_no_tsconfig(
    tmp_path: Path,
) -> None:
    _ = (tmp_path / "package.json").write_text('{"name":"x"}\n', encoding="utf-8")

    assert detect_languages_for_migration(tmp_path) == ["javascript"]


def test_detect_languages_for_migration_detects_multiple_languages_in_priority_order(
    tmp_path: Path,
) -> None:
    _ = (tmp_path / "Package.swift").write_text(
        "// swift-tools-version:5.9\nimport PackageDescription\n",
        encoding="utf-8",
    )
    _ = (tmp_path / "build.gradle").write_text("plugins {}\n", encoding="utf-8")
    _ = (tmp_path / "Cargo.toml").write_text("[package]\nname='x'\n", encoding="utf-8")
    _ = (tmp_path / "go.mod").write_text("module x\n", encoding="utf-8")
    _ = (tmp_path / "main.py").write_text("print('x')\n", encoding="utf-8")

    assert detect_languages_for_migration(tmp_path) == [
        "swift",
        "java",
        "rust",
        "go",
        "python",
    ]
