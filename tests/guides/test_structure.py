"""Tests for cortex.guides.structure."""

from cortex.guides.structure import GUIDE


class TestStructureGuide:
    """Tests for structure guide content and formatting."""

    def test_guide_is_non_empty_string(self) -> None:
        """GUIDE is a non-empty string."""
        assert isinstance(GUIDE, str)
        assert len(GUIDE) > 0

    def test_guide_has_markdown_heading(self) -> None:
        """GUIDE starts with a level-2 markdown heading."""
        assert GUIDE.strip().startswith("## ")

    def test_guide_contains_structure_content(self) -> None:
        """GUIDE contains expected structure-related content."""
        assert "Memory Bank Structure" in GUIDE
        assert "Core Files" in GUIDE or "core files" in GUIDE
        assert "projectBrief" in GUIDE or "projectBrief.md" in GUIDE

    def test_guide_lists_required_files(self) -> None:
        """GUIDE mentions required files."""
        assert "activeContext" in GUIDE or "activeContext.md" in GUIDE
        assert "progress" in GUIDE or "progress.md" in GUIDE
