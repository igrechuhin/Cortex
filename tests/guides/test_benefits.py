"""Tests for cortex.guides.benefits."""

from cortex.guides.benefits import GUIDE


class TestBenefitsGuide:
    """Tests for benefits guide content and formatting."""

    def test_guide_is_non_empty_string(self) -> None:
        """GUIDE is a non-empty string."""
        assert isinstance(GUIDE, str)
        assert len(GUIDE) > 0

    def test_guide_has_markdown_heading(self) -> None:
        """GUIDE starts with a level-2 markdown heading."""
        assert GUIDE.strip().startswith("## ")

    def test_guide_contains_benefits_content(self) -> None:
        """GUIDE contains expected benefits-related content."""
        assert "Benefits of Memory Bank" in GUIDE
        assert "Context" in GUIDE or "context" in GUIDE

    def test_guide_contains_bullet_points(self) -> None:
        """GUIDE uses markdown list format."""
        assert "- " in GUIDE or "**" in GUIDE
