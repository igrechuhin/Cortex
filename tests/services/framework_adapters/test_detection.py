"""Tests for cortex.services.framework_adapters.detection."""

import tempfile
from pathlib import Path

from cortex.services.framework_adapters.detection import detect_language_at_path


class TestDetectLanguageAtPath:
    """Test detect_language_at_path public API."""

    def test_returns_none_for_empty_directory(self) -> None:
        """Empty directory is not recognized by any adapter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)
            result = detect_language_at_path(path)
            assert result is None

    def test_returns_python_info_for_pyproject_root(self) -> None:
        """Directory with pyproject.toml is detected as Python."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)
            _ = (path / "pyproject.toml").write_text("[project]\nname = 'pkg'")
            result = detect_language_at_path(path)
            assert result is not None
            info, detected_path = result
            assert info.language == "python"
            assert detected_path == path

    def test_returns_typescript_info_for_tsconfig_root(self) -> None:
        """Directory with tsconfig.json is detected as TypeScript."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)
            _ = (path / "tsconfig.json").write_text("{}")
            result = detect_language_at_path(path)
            assert result is not None
            info, detected_path = result
            assert info.language == "typescript"
            assert detected_path == path

    def test_returns_rust_info_for_cargo_root(self) -> None:
        """Directory with Cargo.toml is detected as Rust."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)
            _ = (path / "Cargo.toml").write_text("[package]\nname = 'foo'")
            result = detect_language_at_path(path)
            assert result is not None
            info, detected_path = result
            assert info.language == "rust"
            assert detected_path == path

    def test_returns_go_info_for_go_mod_root(self) -> None:
        """Directory with go.mod is detected as Go."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)
            _ = (path / "go.mod").write_text("module example.com/foo\n")
            result = detect_language_at_path(path)
            assert result is not None
            info, detected_path = result
            assert info.language == "go"
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
