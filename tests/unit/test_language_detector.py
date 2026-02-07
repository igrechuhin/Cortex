"""Tests for language detection service."""

import json
import tempfile
from pathlib import Path
from typing import cast
from unittest.mock import patch

from cortex.core.path_resolver import get_venv_bin_path
from cortex.services.language_detector import LanguageDetector


class TestLanguageDetector:
    """Test language detection."""

    def test_detect_python_from_pyproject_toml(self) -> None:
        """Test Python detection from pyproject.toml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            _ = (project_root / "pyproject.toml").write_text("[project]\nname = 'test'")

            detector = LanguageDetector(str(project_root))
            result = detector.detect_language()

            assert result is not None
            assert result["language"] == "python"
            confidence = cast(float, result["confidence"])
            assert confidence > 0.8

    def test_detect_python_from_requirements_txt(self) -> None:
        """Test Python detection from requirements.txt."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            _ = (project_root / "requirements.txt").write_text("requests==2.0.0")

            detector = LanguageDetector(str(project_root))
            result = detector.detect_language()

            assert result is not None
            assert result["language"] == "python"

    def test_detect_python_from_pytest_ini(self) -> None:
        """Test Python detection with pytest.ini."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            _ = (project_root / "pyproject.toml").write_text("[project]\nname = 'test'")
            _ = (project_root / "pytest.ini").write_text("[pytest]")

            detector = LanguageDetector(str(project_root))
            result = detector.detect_language()

            assert result is not None
            assert result["language"] == "python"
            assert result["test_framework"] == "pytest"

    def test_detect_typescript_from_tsconfig(self) -> None:
        """Test TypeScript detection from tsconfig.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            _ = (project_root / "tsconfig.json").write_text("{}")

            detector = LanguageDetector(str(project_root))
            result = detector.detect_language()

            assert result is not None
            assert result["language"] == "typescript"
            assert result["type_checker"] == "tsc"

    def test_detect_typescript_from_package_json(self) -> None:
        """Test TypeScript detection from package.json with typescript dependency."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            package_json = {
                "dependencies": {"typescript": "^5.0.0"},
            }
            _ = (project_root / "package.json").write_text(json.dumps(package_json))

            detector = LanguageDetector(str(project_root))
            result = detector.detect_language()

            assert result is not None
            assert result["language"] == "typescript"

    def test_detect_javascript_from_package_json(self) -> None:
        """Test JavaScript detection from package.json without typescript."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            package_json = {
                "dependencies": {"express": "^4.0.0"},
            }
            _ = (project_root / "package.json").write_text(json.dumps(package_json))

            detector = LanguageDetector(str(project_root))
            result = detector.detect_language()

            assert result is not None
            assert result["language"] == "javascript"

    def test_detect_rust_from_cargo_toml(self) -> None:
        """Test Rust detection from Cargo.toml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            _ = (project_root / "Cargo.toml").write_text("[package]\nname = 'test'")

            detector = LanguageDetector(str(project_root))
            result = detector.detect_language()

            assert result is not None
            assert result["language"] == "rust"
            assert result["test_framework"] == "cargo test"
            assert result["build_tool"] == "cargo"

    def test_detect_go_from_go_mod(self) -> None:
        """Test Go detection from go.mod."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            _ = (project_root / "go.mod").write_text("module test")

            detector = LanguageDetector(str(project_root))
            result = detector.detect_language()

            assert result is not None
            assert result["language"] == "go"
            assert result["test_framework"] == "go test"

    def test_detect_swift_from_package_swift(self) -> None:
        """Test Swift detection from Package.swift."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            _ = (project_root / "Package.swift").write_text(
                "// swift-tools-version:5.9\nlet package = Package()"
            )

            detector = LanguageDetector(str(project_root))
            result = detector.detect_language()

            assert result is not None
            assert result["language"] == "swift"
            assert result["test_framework"] == "swift test"
            assert result["build_tool"] == "swift"

    def test_detect_kotlin_from_gradle_and_kt_files(self) -> None:
        """Test Kotlin detection from build.gradle.kts and .kt files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            _ = (project_root / "build.gradle.kts").write_text(
                'plugins { kotlin("jvm") }'
            )
            (project_root / "src").mkdir()
            (project_root / "src" / "main").mkdir()
            (project_root / "src" / "main" / "kotlin").mkdir(parents=True)
            _ = (project_root / "src" / "main" / "kotlin" / "Main.kt").write_text(
                "fun main() {}"
            )

            detector = LanguageDetector(str(project_root))
            result = detector.detect_language()

            assert result is not None
            assert result["language"] == "kotlin"
            assert result["build_tool"] == "gradle"

    def test_detect_none_for_empty_directory(self) -> None:
        """Test that empty directory returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = LanguageDetector(str(tmpdir))
            result = detector.detect_language()

            assert result is None

    def test_detect_js_test_framework_jest(self) -> None:
        """Test JavaScript test framework detection (jest)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            package_json = {
                "devDependencies": {"jest": "^29.0.0"},
            }
            _ = (project_root / "package.json").write_text(json.dumps(package_json))

            detector = LanguageDetector(str(project_root))
            result = detector.detect_language()

            assert result is not None
            assert result["language"] in ["javascript", "typescript"]
            assert result["test_framework"] == "jest"

    def test_detect_js_test_framework_vitest(self) -> None:
        """Test JavaScript test framework detection (vitest)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            package_json = {
                "devDependencies": {"vitest": "^1.0.0"},
            }
            _ = (project_root / "package.json").write_text(json.dumps(package_json))

            detector = LanguageDetector(str(project_root))
            result = detector.detect_language()

            assert result is not None
            assert result["language"] in ["javascript", "typescript"]
            assert result["test_framework"] == "vitest"

    def test_detect_js_test_framework_mocha(self) -> None:
        """Test JavaScript test framework detection (mocha)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            package_json = {
                "devDependencies": {"mocha": "^10.0.0"},
            }
            _ = (project_root / "package.json").write_text(json.dumps(package_json))

            detector = LanguageDetector(str(project_root))
            result = detector.detect_language()

            assert result is not None
            assert result["language"] in ["javascript", "typescript"]
            assert result["test_framework"] == "mocha"

    def test_detect_language_returns_none_when_no_project_files(self) -> None:
        """detect_language returns None when no project files (no package.json)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = LanguageDetector(str(tmpdir))
            assert detector.detect_language() is None

    def test_detect_language_returns_javascript_when_package_json_invalid(
        self,
    ) -> None:
        """detect_language returns javascript when package.json is invalid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "package.json").write_text("not valid json {")
            detector = LanguageDetector(str(tmpdir))
            result = detector.detect_language()
            assert result is not None
            assert result["language"] == "javascript"

    def test_detect_python_includes_formatter_when_black_in_path(self) -> None:
        """detect_language includes formatter when black in PATH (not in .venv)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "pyproject.toml").write_text("[project]\nname = 'x'")
            detector = LanguageDetector(str(tmpdir))
            with patch("shutil.which") as mock_which:
                mock_which.return_value = "/usr/bin/black"
                result = detector.detect_language()
                mock_which.assert_called()
            assert result is not None
            assert result["language"] == "python"
            assert result["formatter"] == "black"

    def test_detect_javascript_includes_formatter_when_prettier_in_path(
        self,
    ) -> None:
        """detect_language includes formatter when prettier in PATH."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _ = (Path(tmpdir) / "package.json").write_text(
                json.dumps({"dependencies": {"express": "1.0"}})
            )
            detector = LanguageDetector(str(tmpdir))
            with patch("shutil.which") as mock_which:
                mock_which.return_value = "/usr/bin/prettier"
                result = detector.detect_language()
                mock_which.assert_called()
            assert result is not None
            assert result["language"] == "javascript"
            assert result["formatter"] == "prettier"

    def test_detect_python_includes_formatter_when_black_in_venv(self) -> None:
        """detect_language includes formatter when black exists in .venv/bin."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _ = (root / "pyproject.toml").write_text("[project]\nname = 'x'")
            venv_bin = get_venv_bin_path(root)
            venv_bin.mkdir(parents=True)
            _ = (venv_bin / "black").write_text("")
            detector = LanguageDetector(str(root))
            result = detector.detect_language()
            assert result is not None
            assert result["language"] == "python"
            assert result["formatter"] == "black"

    def test_detect_javascript_includes_formatter_when_prettier_in_node_modules(
        self,
    ) -> None:
        """detect_language includes formatter when prettier in node_modules/.bin."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _ = (root / "package.json").write_text(
                json.dumps({"dependencies": {"express": "1.0"}})
            )
            (root / "node_modules" / ".bin").mkdir(parents=True)
            _ = (root / "node_modules" / ".bin" / "prettier").write_text("")
            detector = LanguageDetector(str(root))
            result = detector.detect_language()
            assert result is not None
            assert result["language"] == "javascript"
            assert result["formatter"] == "prettier"
