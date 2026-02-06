"""
Tests for Plan Operations Tools

Tests for create_plan and register_plan_in_roadmap tools.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from cortex.tools.plan_operations import (
    CreatePlanResult,
    RegisterPlanResult,
    register_plan_in_roadmap,
)

# Import private functions with public aliases for testing
from cortex.tools.plan_operations import (
    _create_plan_file as create_plan_file,  # type: ignore[private-usage]
)
from cortex.tools.plan_operations import (
    _find_insertion_line_for_section as find_insertion_line,  # type: ignore[private-usage]
)
from cortex.tools.plan_operations import (
    _is_completed_status as is_completed_status,  # type: ignore[private-usage]
)
from cortex.tools.plan_operations import (
    _parse_roadmap_sections as parse_roadmap_sections,  # type: ignore[private-usage]
)
from cortex.tools.plan_operations import (
    _register_plan_entry as register_plan_entry,  # type: ignore[private-usage]
)
from cortex.tools.plan_operations import (
    _sanitize_plan_slug as sanitize_plan_slug,  # type: ignore[private-usage]
)


class TestIsCompletedStatus:
    """Test that completed status is rejected for roadmap (future/upcoming only)."""

    def test_completed_returns_true(self) -> None:
        """COMPLETED status is considered completed."""
        assert is_completed_status("COMPLETED") is True

    def test_complete_returns_true(self) -> None:
        """COMPLETE status is considered completed."""
        assert is_completed_status("COMPLETE") is True

    def test_done_returns_true(self) -> None:
        """DONE status is considered completed."""
        assert is_completed_status("DONE") is True

    def test_case_insensitive(self) -> None:
        """Completed status check is case-insensitive."""
        assert is_completed_status("completed") is True
        assert is_completed_status("Complete") is True

    def test_pending_returns_false(self) -> None:
        """PENDING status is not completed."""
        assert is_completed_status("PENDING") is False

    def test_in_progress_returns_false(self) -> None:
        """IN PROGRESS status is not completed."""
        assert is_completed_status("IN PROGRESS") is False

    def test_whitespace_stripped(self) -> None:
        """Whitespace around status is stripped."""
        assert is_completed_status("  COMPLETED  ") is True


class TestRegisterPlanInRoadmapRejectsCompleted:
    """register_plan_in_roadmap must reject COMPLETED status (roadmap = future only)."""

    @pytest.mark.asyncio
    async def test_register_plan_in_roadmap_rejects_completed_status(
        self, tmp_path: Path
    ) -> None:
        """Calling with status=COMPLETED returns error and mentions activeContext."""
        with patch(
            "cortex.tools.plan_operations.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=tmp_path,
        ):
            result_str = await register_plan_in_roadmap(
                plan_title="Done plan",
                description="Already done",
                status="COMPLETED",
                section="pending",
            )
        result = json.loads(result_str)
        assert result["status"] == "error"
        assert "activeContext" in result.get("error", "")

    @pytest.mark.asyncio
    async def test_register_plan_in_roadmap_accepts_pending_status(
        self, tmp_path: Path
    ) -> None:
        """Calling with status=PENDING proceeds (may fail later for missing roadmap)."""
        (tmp_path / ".cortex" / "memory-bank").mkdir(parents=True)
        roadmap = tmp_path / ".cortex" / "memory-bank" / "roadmap.md"
        _ = roadmap.write_text(
            "# Roadmap\n\n## Blockers (ASAP Priority)\nNone\n\n"
            + "## Active Work (in progress)\n\n## Future Enhancements\n\n"
            + "## Pending plans (from .cortex/plans)\n- **Other** - PENDING\n"
        )
        with patch(
            "cortex.tools.plan_operations.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=tmp_path,
        ):
            result_str = await register_plan_in_roadmap(
                plan_title="New plan",
                description="Description",
                status="PENDING",
                section="pending",
            )
        result = json.loads(result_str)
        assert result["status"] == "success"


class TestSanitizePlanSlug:
    """Test slug sanitization."""

    def test_simple_title(self) -> None:
        """Test sanitizing a simple title."""
        assert sanitize_plan_slug("Phase One Feature") == "phase-one-feature"

    def test_title_with_special_chars(self) -> None:
        """Test sanitizing title with special characters."""
        assert (
            sanitize_plan_slug("Phase 45: Add MCP Annotations")
            == "phase-45-add-mcp-annotations"
        )

    def test_title_with_multiple_spaces(self) -> None:
        """Test sanitizing title with multiple consecutive spaces."""
        assert sanitize_plan_slug("Phase   Test   Title") == "phase-test-title"

    def test_empty_title(self) -> None:
        """Test sanitizing empty title."""
        assert sanitize_plan_slug("") == ""

    def test_title_with_hyphens(self) -> None:
        """Test title that already has hyphens."""
        assert sanitize_plan_slug("Phase-One-Feature") == "phase-one-feature"


class TestParseRoadmapSections:
    """Test roadmap section parsing."""

    def test_parse_standard_roadmap(self) -> None:
        """Test parsing standard roadmap structure."""
        content = """# Roadmap

## Blockers (ASAP Priority)

- Block 1

## Active Work (in progress)

- Work 1

## Future Enhancements

- Future 1

## Pending plans (from .cortex/plans)

- Pending 1
"""
        sections = parse_roadmap_sections(content)
        assert "blockers" in sections
        assert "active_work" in sections
        assert "future" in sections
        assert "pending" in sections

    def test_parse_roadmap_with_subsections(self) -> None:
        """Test parsing roadmap with subsections."""
        content = """# Roadmap

## Blockers (ASAP Priority)

### Critical Issues

- Issue 1

## Pending plans (from .cortex/plans)

- Plan 1
"""
        sections = parse_roadmap_sections(content)
        assert "blockers" in sections
        assert "pending" in sections


class TestFindInsertionLine:
    """Test finding insertion points."""

    def test_insert_after_first_bullet(self) -> None:
        """Test finding insertion point after first bullet."""
        lines = [
            "## Section",
            "",
            "- First bullet",
            "- Second bullet",
        ]
        insert_line = find_insertion_line(lines, 0, 3, position="first")
        assert insert_line == 2

    def test_insert_after_last_bullet(self) -> None:
        """Test finding insertion point after last bullet."""
        lines = [
            "## Section",
            "",
            "- First bullet",
            "- Second bullet",
        ]
        insert_line = find_insertion_line(lines, 0, 3, position="last")
        assert insert_line == 4

    def test_insert_in_empty_section(self) -> None:
        """Test finding insertion point in empty section."""
        lines = [
            "## Section",
            "",
            "Some text",
        ]
        insert_line = find_insertion_line(lines, 0, 2, position="last")
        assert insert_line == 1


class TestRegisterPlanEntry:
    """Test plan entry registration."""

    def test_register_plan_in_pending_section(self) -> None:
        """Test registering plan in pending section."""
        content = """# Roadmap

## Blockers (ASAP Priority)

- Block 1

## Pending plans (from .cortex/plans)

- Existing 1
"""
        updated, line = register_plan_entry(
            content,
            plan_title="Test Plan",
            description="Test description",
            status="PENDING",
            section_id="pending",
        )

        assert line is not None
        assert "Test Plan" in updated
        assert "Test description" in updated
        assert "Existing 1" in updated  # Ensure existing entry preserved

    def test_register_plan_preserves_other_sections(self) -> None:
        """Test that registering plan preserves other sections."""
        content = """# Roadmap

## Blockers (ASAP Priority)

- Block 1

## Pending plans (from .cortex/plans)

- Existing plan
"""
        updated, _ = register_plan_entry(
            content,
            plan_title="New Plan",
            description="Description",
            status="PENDING",
            section_id="pending",
        )

        # Verify original section is preserved
        assert "- Block 1" in updated
        assert "Blockers (ASAP Priority)" in updated


class TestCreatePlanFile:
    """Test plan file creation."""

    def test_create_plan_with_explicit_slug(self) -> None:
        """Test creating plan file with explicit slug."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            content = "# Test Plan\n\nTest content"

            path, error = create_plan_file(
                root,
                title="Test Plan",
                slug="test-plan",
                content=content,
            )

            assert error is None
            assert path is not None
            assert path.name == "test-plan.md"
            assert path.read_text() == content

    def test_create_plan_with_generated_slug(self) -> None:
        """Test creating plan file with generated slug from title."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            content = "# Generated Slug Plan\n\nContent"

            path, error = create_plan_file(
                root,
                title="Generated Slug Plan",
                slug=None,
                content=content,
            )

            assert error is None
            assert path is not None
            assert "generated-slug-plan" in path.name
            assert path.read_text() == content

    def test_create_plan_creates_directory(self) -> None:
        """Test that create_plan_file creates plans directory if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            plans_dir = root / ".cortex" / "plans"
            assert not plans_dir.exists()

            path, error = create_plan_file(
                root,
                title="Test",
                slug="test",
                content="# Test",
            )

            assert error is None
            assert plans_dir.exists()
            assert path is not None


class TestCreatePlanResult:
    """Test CreatePlanResult model."""

    def test_success_result(self) -> None:
        """Test success result serialization."""
        result = CreatePlanResult(
            status="success",
            file_path="/path/to/plan.md",
            message="Plan created successfully",
            error=None,
        )

        json_str = result.model_dump_json()
        data = json.loads(json_str)

        assert data["status"] == "success"
        assert data["file_path"] == "/path/to/plan.md"
        assert data["message"] == "Plan created successfully"
        assert data["error"] is None

    def test_error_result(self) -> None:
        """Test error result serialization."""
        result = CreatePlanResult(
            status="error",
            file_path=None,
            message="Failed to create plan",
            error="Directory does not exist",
        )

        json_str = result.model_dump_json()
        data = json.loads(json_str)

        assert data["status"] == "error"
        assert data["file_path"] is None
        assert "directory" in data.get("error", "").lower()


class TestRegisterPlanResult:
    """Test RegisterPlanResult model."""

    def test_success_result(self) -> None:
        """Test success result serialization."""
        result = RegisterPlanResult(
            status="success",
            file_name="roadmap.md",
            message="Plan registered",
            line_inserted=42,
            section="pending",
            error=None,
        )

        json_str = result.model_dump_json()
        data = json.loads(json_str)

        assert data["status"] == "success"
        assert data["file_name"] == "roadmap.md"
        assert data["line_inserted"] == 42
        assert data["section"] == "pending"

    def test_error_result(self) -> None:
        """Test error result serialization."""
        result = RegisterPlanResult(
            status="error",
            file_name="roadmap.md",
            message="Failed to register",
            line_inserted=None,
            section=None,
            error="Section not found",
        )

        json_str = result.model_dump_json()
        data = json.loads(json_str)

        assert data["status"] == "error"
        assert data["error"] == "Section not found"


class TestRoadmapIntegration:
    """Integration tests for roadmap operations."""

    def test_full_plan_registration_workflow(self) -> None:
        """Test complete workflow of parsing, finding, and registering."""
        content = """# Roadmap

## Blockers (ASAP Priority)

None

## Active Work

## Future Enhancements

## Pending plans (from .cortex/plans)

- Existing Plan 1
- Existing Plan 2
"""

        # Register a new plan
        updated, line = register_plan_entry(
            content,
            plan_title="New Infrastructure Plan",
            description="Critical infrastructure work",
            status="PENDING",
            section_id="pending",
        )

        # Verify new entry was added
        assert line is not None
        assert "New Infrastructure Plan" in updated
        assert "Critical infrastructure work" in updated

        # Verify existing entries are preserved
        assert "Existing Plan 1" in updated
        assert "Existing Plan 2" in updated

        # Verify section headers are preserved
        assert "## Pending plans (from .cortex/plans)" in updated

    def test_register_multiple_plans_sequentially(self) -> None:
        """Test registering multiple plans sequentially."""
        content = """# Roadmap

## Pending plans (from .cortex/plans)

- Plan 1
"""

        # Add first new plan
        updated1, line1 = register_plan_entry(
            content,
            plan_title="Plan 2",
            description="Description 2",
            status="PENDING",
            section_id="pending",
        )
        assert line1 is not None

        # Add second new plan
        updated2, line2 = register_plan_entry(
            updated1,
            plan_title="Plan 3",
            description="Description 3",
            status="PENDING",
            section_id="pending",
        )
        assert line2 is not None

        # Verify all plans are present
        assert "Plan 1" in updated2
        assert "Plan 2" in updated2
        assert "Plan 3" in updated2
