"""Tests for cortex.guides.usage."""

from cortex.guides.usage import GUIDE


class TestUsageGuide:
    """Tests for usage guide content and formatting."""

    def test_guide_is_non_empty_string(self) -> None:
        """GUIDE is a non-empty string."""
        assert isinstance(GUIDE, str)
        assert len(GUIDE) > 0

    def test_guide_has_markdown_heading(self) -> None:
        """GUIDE starts with a level-2 markdown heading."""
        assert GUIDE.strip().startswith("## ")

    def test_guide_contains_usage_content(self) -> None:
        """GUIDE contains expected usage-related content."""
        assert "Using Memory Bank" in GUIDE
        assert "Memory Bank" in GUIDE
        assert "update" in GUIDE or "updates" in GUIDE

    def test_guide_contains_numbered_list(self) -> None:
        """GUIDE includes numbered items."""
        assert "1." in GUIDE
