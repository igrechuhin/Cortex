"""Tests for cortex.guides.setup."""

from cortex.guides.setup import GUIDE


class TestSetupGuide:
    """Tests for setup guide content and formatting."""

    def test_guide_is_non_empty_string(self) -> None:
        """GUIDE is a non-empty string."""
        assert isinstance(GUIDE, str)
        assert len(GUIDE) > 0

    def test_guide_has_markdown_heading(self) -> None:
        """GUIDE starts with a level-2 markdown heading."""
        assert GUIDE.strip().startswith("## ")

    def test_guide_contains_setup_content(self) -> None:
        """GUIDE contains expected setup-related content."""
        assert "Setting Up Memory Bank" in GUIDE
        assert "memory-bank" in GUIDE or "Memory Bank" in GUIDE
        assert "directory" in GUIDE

    def test_guide_contains_numbered_steps(self) -> None:
        """GUIDE includes numbered steps."""
        assert "1." in GUIDE
        assert "2." in GUIDE
