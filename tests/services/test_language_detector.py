"""Tests for cortex.services.language_detector (services package)."""

import tempfile
from pathlib import Path

from cortex.services.language_detector import LanguageDetector, LanguageInfo


class TestLanguageDetectorServices:
    """Test LanguageDetector public API from services package."""

    def test_detect_language_returns_none_for_empty_dir(self) -> None:
        """detect_language returns None when no language markers present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = LanguageDetector(tmpdir)
            result = detector.detect_language()
            assert result is None

    def test_detect_language_returns_language_info_for_python(self) -> None:
        """detect_language returns LanguageInfo for Python project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _ = (root / "pyproject.toml").write_text("[project]\nname = 'x'")
            detector = LanguageDetector(str(root))
            result = detector.detect_language()
            assert result is not None
            assert isinstance(result, LanguageInfo)
            assert result.language == "python"
            assert 0 <= result.confidence <= 1

    def test_detect_language_with_none_project_root_uses_cwd(self) -> None:
        """Detector with project_root=None uses current directory."""
        detector = LanguageDetector(None)
        assert detector.project_root == Path.cwd()
