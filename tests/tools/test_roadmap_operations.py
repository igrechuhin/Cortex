"""
Tests for roadmap_operations module.

Tests for roadmap entry addition, parsing, and insertion logic.
"""

from pathlib import Path

import pytest
from pydantic import ValidationError

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.roadmap_operations import (  # type: ignore[import-not-found]
    RoadmapSection,
    _entry_text_looks_completed,  # type: ignore[name-defined]
    _execute_roadmap_insertion,  # type: ignore[name-defined]
    _execute_roadmap_removal,  # type: ignore[name-defined]
    _find_bullet_line_containing,  # type: ignore[name-defined]
    _get_section_bullet_lines,  # type: ignore[name-defined]
    _insert_roadmap_entry,  # type: ignore[name-defined]
    _parse_roadmap_sections,  # type: ignore[name-defined]
    _remove_line_at,  # type: ignore[name-defined]
)


class TestEntryTextLooksCompleted:
    """Roadmap must not contain COMPLETED entries (future/upcoming only)."""

    def test_completed_detected(self) -> None:
        """Entry with ' - COMPLETED' is detected as completed."""
        assert _entry_text_looks_completed("- **Phase 50** - COMPLETED - Done.") is True

    def test_complete_detected(self) -> None:
        """Entry with ' - COMPLETE' is detected as completed."""
        assert _entry_text_looks_completed("**Foo** - COMPLETE - Summary") is True

    def test_done_detected(self) -> None:
        """Entry with ' - DONE' is detected as completed."""
        assert _entry_text_looks_completed("- **Bar** - DONE - x") is True

    def test_case_insensitive(self) -> None:
        """Detection is case-insensitive."""
        assert _entry_text_looks_completed("- **X** - completed - y") is True

    def test_pending_not_detected(self) -> None:
        """Entry with PENDING is not detected as completed."""
        assert _entry_text_looks_completed("- **Plan** - PENDING - Plan: x") is False

    def test_in_progress_not_detected(self) -> None:
        """Entry with IN PROGRESS is not detected as completed."""
        assert (
            _entry_text_looks_completed("- **Plan** - IN PROGRESS - Plan: x") is False
        )

    def test_plain_text_not_detected(self) -> None:
        """Plain text without status is not detected as completed."""
        assert _entry_text_looks_completed("Some task description") is False


class TestExecuteRoadmapInsertionRejectsCompleted:
    """_execute_roadmap_insertion rejects completed-looking entry_text."""

    @pytest.mark.asyncio
    async def test_insertion_rejects_completed_entry(self, tmp_path: Path) -> None:
        """Adding a COMPLETED entry returns error result."""
        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True)
        _ = (memory_bank_dir / "roadmap.md").write_text(
            "# Roadmap\n\n## Blockers (ASAP Priority)\nNone\n\n"
            + "## Active Work (in progress)\n\n## Future Enhancements\n\n"
            + "## Pending plans (from .cortex/plans)\n- **Other** - PENDING\n"
        )
        result = await _execute_roadmap_insertion(
            tmp_path,
            section="pending",
            entry_text="- **Phase 51** - COMPLETED - Summary",
            position="last",
        )
        assert result.status == "error"
        assert "activeContext" in (result.error or "")

    @pytest.mark.asyncio
    async def test_insertion_accepts_pending_entry(self, tmp_path: Path) -> None:
        """Adding a PENDING entry succeeds."""
        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True)
        _ = (memory_bank_dir / "roadmap.md").write_text(
            "# Roadmap\n\n## Blockers (ASAP Priority)\nNone\n\n"
            + "## Active Work (in progress)\n\n## Future Enhancements\n\n"
            + "## Pending plans (from .cortex/plans)\n- **Other** - PENDING\n"
        )
        result = await _execute_roadmap_insertion(
            tmp_path,
            section="pending",
            entry_text="- **New plan** - PENDING - Plan: x",
            position="last",
        )
        assert result.status == "success"
        assert result.line_inserted is not None


class TestFindBulletLineContaining:
    """Tests for _find_bullet_line_containing (remove_roadmap_entry)."""

    def test_finds_bullet_containing_substring(self) -> None:
        content = "## Pending\n\n- **Phase 50** - PENDING - Plan: x.\n"
        assert _find_bullet_line_containing(content, "Phase 50") == 3

    def test_returns_none_when_not_found(self) -> None:
        content = "## Pending\n\n- **Other** - PENDING\n"
        assert _find_bullet_line_containing(content, "Phase 50") is None

    def test_ignores_non_bullet_lines(self) -> None:
        content = "## Phase 50\n\n- **Plan** - PENDING\n"
        assert _find_bullet_line_containing(content, "Phase 50") is None

    def test_first_bullet_match_wins(self) -> None:
        content = "- **A** - PENDING\n- **B** - PENDING\n"
        assert _find_bullet_line_containing(content, "PENDING") == 1


class TestRemoveLineAtRoadmap:
    """Tests for _remove_line_at in roadmap_operations."""

    def test_removes_line(self) -> None:
        content = "line1\nline2\nline3"
        out = _remove_line_at(content, 2)
        assert out == "line1\nline3"

    def test_removes_first_line(self) -> None:
        content = "a\nb\nc"
        assert _remove_line_at(content, 1) == "b\nc"


class TestExecuteRoadmapRemoval:
    """Tests for _execute_roadmap_removal."""

    @pytest.mark.asyncio
    async def test_removal_success(self, tmp_path: Path) -> None:
        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True)
        content = "# Roadmap\n\n## Pending\n\n- **Phase 50** - PENDING - Plan: x.\n"
        _ = (memory_bank_dir / "roadmap.md").write_text(content)
        result = await _execute_roadmap_removal(tmp_path, "Phase 50")
        assert result.status == "success"
        assert result.line_removed is not None
        assert result.line_removed >= 1
        assert "Phase 50" not in (memory_bank_dir / "roadmap.md").read_text()

    @pytest.mark.asyncio
    async def test_removal_not_found_returns_error(self, tmp_path: Path) -> None:
        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True)
        _ = (memory_bank_dir / "roadmap.md").write_text(
            "# Roadmap\n\n## Pending\n\n- **Other** - PENDING\n"
        )
        result = await _execute_roadmap_removal(tmp_path, "Phase 50")
        assert result.status == "error"
        assert result.line_removed is None

    @pytest.mark.asyncio
    async def test_removal_file_not_found_returns_error(self, tmp_path: Path) -> None:
        get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK).mkdir(parents=True)
        result = await _execute_roadmap_removal(tmp_path, "Phase 50")
        assert result.status == "error"
        assert "not found" in (result.error or "").lower()


class TestParseRoadmapSections:
    """Tests for _parse_roadmap_sections function."""

    def test_parse_basic_sections(self) -> None:
        """Test parsing basic roadmap sections."""
        content = """# Roadmap: MCP Memory Bank

## Blockers (ASAP Priority)

None

## Active Work (in progress)

- **Phase 43** - IN PROGRESS

## Future Enhancements

## Pending plans (from .cortex/plans)

- **Plan A** - PENDING
"""
        sections = _parse_roadmap_sections(content)

        assert "blockers" in sections
        assert "active_work" in sections
        assert "future" in sections
        assert "pending" in sections

    def test_parse_section_boundaries(self) -> None:
        """Test that section boundaries are correctly identified."""
        content = """## Blockers (ASAP Priority)

- Item 1

## Active Work (in progress)

- Item 2
- Item 3
"""
        sections = _parse_roadmap_sections(content)

        blockers_section = sections["blockers"]
        active_work_section = sections["active_work"]

        # Blockers should end before Active Work starts
        assert blockers_section.end_line < active_work_section.start_line

    def test_parse_empty_sections(self) -> None:
        """Test parsing with empty sections."""
        content = """## Blockers (ASAP Priority)

None

## Active Work (in progress)

## Future Enhancements

"""
        sections = _parse_roadmap_sections(content)

        assert "blockers" in sections
        assert "active_work" in sections
        assert "future" in sections

    def test_parse_missing_section(self) -> None:
        """Test parsing when a section is missing."""
        content = """## Blockers (ASAP Priority)

None

## Future Enhancements

"""
        sections = _parse_roadmap_sections(content)

        # Should have blockers and future, but not active_work or pending
        assert "blockers" in sections
        assert "future" in sections
        assert "active_work" not in sections
        assert "pending" not in sections


class TestGetSectionBulletLines:
    """Tests for _get_section_bullet_lines function."""

    def test_get_bullet_lines_with_content(self) -> None:
        """Test getting bullet lines from a section with content."""
        lines = [
            "## Blockers (ASAP Priority)",
            "",
            "- Item 1",
            "- Item 2",
            "",
            "## Other Section",
        ]
        section = RoadmapSection(
            name="blockers",
            header="## Blockers (ASAP Priority)",
            start_line=0,
            end_line=4,
        )

        first, last = _get_section_bullet_lines(lines, section)

        assert first == 2
        assert last == 3

    def test_get_bullet_lines_empty_section(self) -> None:
        """Test getting bullet lines from an empty section."""
        lines = [
            "## Blockers (ASAP Priority)",
            "",
            "None",
            "",
            "## Other Section",
        ]
        section = RoadmapSection(
            name="blockers",
            header="## Blockers (ASAP Priority)",
            start_line=0,
            end_line=3,
        )

        first, last = _get_section_bullet_lines(lines, section)

        assert first == -1
        assert last == -1

    def test_get_bullet_lines_single_bullet(self) -> None:
        """Test getting bullet lines when section has single bullet."""
        lines = [
            "## Active Work (in progress)",
            "",
            "- **Phase 43** - IN PROGRESS",
            "",
            "## Other Section",
        ]
        section = RoadmapSection(
            name="active_work",
            header="## Active Work (in progress)",
            start_line=0,
            end_line=3,
        )

        first, last = _get_section_bullet_lines(lines, section)

        assert first == 2
        assert last == 2


class TestInsertRoadmapEntry:
    """Tests for _insert_roadmap_entry function."""

    def test_insert_at_last_position(self) -> None:
        """Test inserting entry at last position in a section."""
        content = """## Blockers (ASAP Priority)

- **Issue 1** - PENDING

## Other Section

- Item
"""
        updated_content, line_inserted = _insert_roadmap_entry(
            content,
            "blockers",
            "- **Issue 2** - PENDING",
            position="last",
        )

        lines = updated_content.split("\n")
        assert any("**Issue 2**" in line for line in lines)
        assert line_inserted is not None
        assert line_inserted > 0

    def test_insert_at_first_position(self) -> None:
        """Test inserting entry at first position in a section."""
        content = """## Pending plans (from .cortex/plans)

- **Plan A** - PENDING

## Other Section
"""
        updated_content, _ = _insert_roadmap_entry(
            content,
            "pending",
            "- **Plan Z** - PENDING",
            position="first",
        )

        lines = updated_content.split("\n")
        # Find the section
        pending_idx = None
        for i, line in enumerate(lines):
            if "Pending plans" in line:
                pending_idx = i
                break

        assert pending_idx is not None
        # Plan Z should be first bullet after header
        first_bullet_idx = None
        for i in range(pending_idx + 1, len(lines)):
            if lines[i].startswith("- "):
                first_bullet_idx = i
                break

        assert first_bullet_idx is not None
        assert "**Plan Z**" in lines[first_bullet_idx]

    def test_insert_into_empty_section(self) -> None:
        """Test inserting entry into an empty section."""
        content = """## Future Enhancements

## Other Section

- Item
"""
        updated_content, line_inserted = _insert_roadmap_entry(
            content,
            "future",
            "- **New Feature** - PENDING",
            position="last",
        )

        lines = updated_content.split("\n")
        assert any("**New Feature**" in line for line in lines)
        assert line_inserted is not None

    def test_insert_unknown_section(self) -> None:
        """Test inserting into unknown section returns error."""
        content = """## Blockers (ASAP Priority)

- Item 1
"""
        updated_content, line_inserted = _insert_roadmap_entry(
            content,
            "nonexistent",
            "- **Item 2**",
            position="last",
        )

        # Should return unchanged content and None
        assert updated_content == content
        assert line_inserted is None

    def test_insert_entry_without_dash_prefix(self) -> None:
        """Test that entry without dash prefix is auto-formatted."""
        content = """## Pending plans (from .cortex/plans)

- **Plan A** - PENDING

## Other Section
"""
        updated_content, _ = _insert_roadmap_entry(
            content,
            "pending",
            "**Plan B** - PENDING",  # No leading dash
            position="last",
        )

        lines = updated_content.split("\n")
        assert any("- **Plan B**" in line for line in lines)

    def test_insert_preserves_other_sections(self) -> None:
        """Test that inserting into one section preserves others."""
        content = """## Blockers (ASAP Priority)

- Item 1

## Active Work (in progress)

- **Phase 43** - IN PROGRESS

## Pending plans (from .cortex/plans)

- Plan 1
"""
        original_blockers_count = content.count("Item 1")
        original_active_work_count = content.count("**Phase 43**")

        updated_content, _ = _insert_roadmap_entry(
            content,
            "pending",
            "- **Plan 2** - PENDING",
            position="last",
        )

        # Original content in other sections should be preserved
        assert updated_content.count("Item 1") == original_blockers_count
        assert updated_content.count("**Phase 43**") == original_active_work_count
        assert "**Plan 2**" in updated_content

    def test_insert_maintains_line_count_integrity(self) -> None:
        """Test that insertion adds exactly one line."""
        content = """## Pending plans (from .cortex/plans)

- **Plan A** - PENDING

## Other Section
"""
        original_lines = content.count("\n")

        updated_content, _ = _insert_roadmap_entry(
            content,
            "pending",
            "- **Plan B** - PENDING",
            position="last",
        )

        updated_lines = updated_content.count("\n")
        assert updated_lines == original_lines + 1

    def test_insert_multiple_entries_sequentially(self) -> None:
        """Test inserting multiple entries in sequence."""
        content = """## Pending plans (from .cortex/plans)

## Other Section
"""
        # Insert first entry
        updated_content1, _ = _insert_roadmap_entry(
            content,
            "pending",
            "- **Plan 1** - PENDING",
            position="last",
        )

        # Insert second entry
        updated_content2, _ = _insert_roadmap_entry(
            updated_content1,
            "pending",
            "- **Plan 2** - PENDING",
            position="last",
        )

        # Both should be present
        assert "**Plan 1**" in updated_content2
        assert "**Plan 2**" in updated_content2


class TestRoadmapSectionModel:
    """Tests for RoadmapSection model."""

    def test_section_model_creation(self) -> None:
        """Test creating a RoadmapSection model."""
        section = RoadmapSection(
            name="blockers",
            header="## Blockers (ASAP Priority)",
            start_line=0,
            end_line=10,
        )

        assert section.name == "blockers"
        assert section.header == "## Blockers (ASAP Priority)"
        assert section.start_line == 0
        assert section.end_line == 10

    def test_section_model_validation(self) -> None:
        """Test RoadmapSection model validation."""
        # Should not allow negative line numbers due to Field constraints
        with pytest.raises(ValidationError):  # Pydantic validation error
            _ = RoadmapSection(
                name="blockers",
                header="## Blockers",
                start_line=-1,  # Invalid
                end_line=10,
            )

    def test_section_model_field_descriptions(self) -> None:
        """Test that section model has proper field descriptions."""
        section = RoadmapSection(
            name="blockers",
            header="## Blockers",
            start_line=0,
            end_line=10,
        )

        # Verify model_config is set correctly
        assert section.model_config.get("extra") == "forbid"
        assert section.model_config.get("validate_assignment") is True


class TestComplexRoadmapScenarios:
    """Tests for complex roadmap scenarios."""

    def test_insert_into_real_roadmap_structure(self) -> None:
        """Test insertion with real-like roadmap structure."""
        content = """# Roadmap: MCP Memory Bank

## Blockers (ASAP Priority)

None - MCP annotations blocker resolved 2026-02-05

## Active Work (in progress)

- **Phase 43: Reconsider tools registration** - IN PROGRESS

## Future Enhancements

## Pending plans (from .cortex/plans)

### Critical Infrastructure (HIGH PRIORITY - Next after Phase 43)

- **Add add_roadmap_entry MCP tool** - PENDING - Plan: .cortex/plans/add-roadmap-entry-mcp-tool.md.
"""
        updated_content, _ = _insert_roadmap_entry(
            content,
            "pending",
            "- **New Infrastructure Tool** - PENDING - Plan: .cortex/plans/new-tool.md.",
            position="last",
        )

        lines = updated_content.split("\n")
        assert any("**New Infrastructure Tool**" in line for line in lines)
        assert "**Add add_roadmap_entry MCP tool**" in updated_content

    def test_parse_real_roadmap_structure(self) -> None:
        """Test parsing with real-like roadmap structure."""
        content = """# Roadmap: MCP Memory Bank

## Blockers (ASAP Priority)

None

## Active Work (in progress)

- **Phase 43** - IN PROGRESS

## Future Enhancements

## Pending plans (from .cortex/plans)

### Critical Infrastructure

- **Tool 1** - PENDING
"""
        sections = _parse_roadmap_sections(content)

        # All sections should be found
        assert "blockers" in sections
        assert "active_work" in sections
        assert "future" in sections
        assert "pending" in sections

        # Section boundaries should be reasonable
        for _section_id, section in sections.items():
            assert section.start_line < section.end_line
            assert section.start_line >= 0
