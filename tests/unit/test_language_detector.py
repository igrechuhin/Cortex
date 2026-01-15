"""Tests for language detection service."""

import json
import tempfile
from pathlib import Path

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
            assert result["confidence"] > 0.8

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
