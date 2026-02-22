"""Tests for cortex.services.framework_adapters.detection."""

import tempfile
from pathlib import Path

import pytest

from cortex.services.framework_adapters.detection import detect_language_at_path

# Parametrized (language, relative_file_path, file_content) for detection tests.
# Order matches adapter detection order. Note: Java-only (pom.xml without .kt) is not
# detected by LanguageDetector; Kotlin is detected when (Maven/Gradle) and .kt exist.
_DETECTION_MARKERS: list[tuple[str, str, str]] = [
    ("python", "pyproject.toml", "[project]\nname = 'pkg'"),
    ("typescript", "tsconfig.json", "{}"),
    ("javascript", "package.json", "{}"),
    ("rust", "Cargo.toml", "[package]\nname = 'foo'"),
    ("go", "go.mod", "module example.com/foo\n"),
    ("swift", "Package.swift", "// swift-tools-version:5.0\n"),
    ("kotlin", "build.gradle.kts", ""),
]


def _setup_kotlin_project(path: Path) -> None:
    """Create minimal Kotlin project (gradle + .kt file)."""
    _ = (path / "build.gradle.kts").write_text("")
    (path / "src" / "main" / "kotlin").mkdir(parents=True)
    _ = (path / "src" / "main" / "kotlin" / "Main.kt").write_text("// kotlin\n")


class TestDetectLanguageAtPath:
    """Test detect_language_at_path public API."""

    def test_returns_none_for_empty_directory(self) -> None:
        """Empty directory is not recognized by any adapter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)
            result = detect_language_at_path(path)
            assert result is None

    @pytest.mark.parametrize(
        "language,rel_path,content",
        _DETECTION_MARKERS,
        ids=[m[0] for m in _DETECTION_MARKERS],
    )
    def test_detects_language_for_marker(
        self, language: str, rel_path: str, content: str
    ) -> None:
        """Directory with language marker is detected as that language."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)
            if language == "kotlin":
                _setup_kotlin_project(path)
            else:
                _ = (path / rel_path).write_text(content)
            result = detect_language_at_path(path)
            assert result is not None, f"Expected {language} to be detected"
            info, detected_path = result
            assert info.language == language
            assert detected_path == path

    def test_first_matching_adapter_wins(self) -> None:
        """When multiple markers exist, first in adapter order wins (Python before TS)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)
            _ = (path / "pyproject.toml").write_text("[project]\nname = 'pkg'")
            _ = (path / "tsconfig.json").write_text("{}")
            result = detect_language_at_path(path)
            assert result is not None
            info, _ = result
            assert info.language == "python"
