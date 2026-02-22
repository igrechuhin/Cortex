"""Tests for guide module content (generation, structure, formatting)."""

import pytest

from cortex.guides import benefits, setup, structure, usage

_GUIDES: list[tuple[str, str]] = [
    ("benefits", benefits.GUIDE),
    ("setup", setup.GUIDE),
    ("structure", structure.GUIDE),
    ("usage", usage.GUIDE),
]


class TestGuideConstants:
    """Each guide module exposes a GUIDE constant."""

    @pytest.mark.parametrize("name,guide", _GUIDES, ids=[n for n, _ in _GUIDES])
    def test_guide_is_string(self, name: str, guide: str) -> None:
        """GUIDE is a string."""
        assert isinstance(guide, str)

    @pytest.mark.parametrize("name,guide", _GUIDES, ids=[n for n, _ in _GUIDES])
    def test_guide_non_empty(self, name: str, guide: str) -> None:
        """GUIDE is non-empty."""
        assert len(guide.strip()) > 0

    @pytest.mark.parametrize("name,guide", _GUIDES, ids=[n for n, _ in _GUIDES])
    def test_guide_has_top_level_heading(self, name: str, guide: str) -> None:
        """GUIDE starts with a ## heading."""
        stripped = guide.strip()
        assert stripped.startswith(
            "## "
        ), f"Expected '## ' heading, got: {stripped[:50]!r}"


class TestBenefitsGuide:
    """Content and formatting for benefits guide."""

    def test_contains_expected_sections(self) -> None:
        """Benefits guide mentions key benefits."""
        g = benefits.GUIDE
        assert "Context Preservation" in g or "context" in g.lower()
        assert "Memory Bank" in g

    def test_formatting_no_leading_trailing_whitespace_lines(self) -> None:
        """Content has no leading/trailing blank lines (single newline ok)."""
        g = benefits.GUIDE
        lines = g.splitlines()
        if lines:
            assert lines[0].strip() != "" or len(lines) == 1
            assert lines[-1].strip() != "" or len(lines) == 1


class TestSetupGuide:
    """Content and formatting for setup guide."""

    def test_contains_setup_steps(self) -> None:
        """Setup guide mentions directory and core files."""
        g = setup.GUIDE
        assert "memory-bank" in g or "memory bank" in g.lower()
        assert "Setting Up" in g or "Setting up" in g

    def test_has_list_like_content(self) -> None:
        """Setup guide has numbered or list content."""
        g = setup.GUIDE
        assert "1." in g or "2." in g or "-" in g or "*" in g


class TestStructureGuide:
    """Content and formatting for structure guide."""

    def test_contains_core_files(self) -> None:
        """Structure guide mentions core file names."""
        g = structure.GUIDE
        assert "projectBrief" in g or "project" in g.lower()
        assert "activeContext" in g or "active" in g.lower()
        assert "Memory Bank" in g

    def test_mentions_required_files(self) -> None:
        """Structure guide indicates required/core files."""
        g = structure.GUIDE
        assert "Core" in g or "required" in g.lower() or "7 files" in g


class TestUsageGuide:
    """Content and formatting for usage guide."""

    def test_contains_usage_guidance(self) -> None:
        """Usage guide mentions when to update or use memory bank."""
        g = usage.GUIDE
        assert "Memory Bank" in g
        assert "update" in g.lower() or "read" in g.lower() or "context" in g.lower()

    def test_has_actionable_content(self) -> None:
        """Usage guide has at least one list or numbered item."""
        g = usage.GUIDE
        assert "1." in g or "2." in g or "-" in g or "**" in g
