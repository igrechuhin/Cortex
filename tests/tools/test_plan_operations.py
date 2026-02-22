"""
Tests for Plan Operations Tools

Tests for create_plan and register_plan_in_roadmap tools.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.plan_crud import (
    _create_plan_file as create_plan_file,  # type: ignore[private-usage]
)
from cortex.tools.plan_crud import (
    _extract_first_heading as extract_first_heading,  # type: ignore[private-usage]
)
from cortex.tools.plan_crud import (
    _extract_status_line as extract_status_line,  # type: ignore[private-usage]
)
from cortex.tools.plan_crud import (
    _get_plan_impl as get_plan_impl,  # type: ignore[private-usage]
)
from cortex.tools.plan_crud import (
    _get_plan_path as get_plan_path,  # type: ignore[private-usage]
)
from cortex.tools.plan_crud import (
    _list_plan_files as list_plan_files,  # type: ignore[private-usage]
)
from cortex.tools.plan_crud import (
    _list_plans_impl as list_plans_impl,  # type: ignore[private-usage]
)
from cortex.tools.plan_crud import (
    _sanitize_plan_slug as sanitize_plan_slug,  # type: ignore[private-usage]
)
from cortex.tools.plan_operations import (
    CreatePlanResult,
    GetPlanResult,
    ListPlansResult,
    RegisterPlanResult,
    get_plan,
    list_plans,
    register_plan_in_roadmap,
)
from cortex.tools.plan_roadmap import (
    _find_insertion_line_for_section as find_insertion_line,  # type: ignore[private-usage]
)
from cortex.tools.plan_roadmap import (
    _is_completed_status as is_completed_status,  # type: ignore[private-usage]
)
from cortex.tools.plan_roadmap import (
    _parse_roadmap_sections as parse_roadmap_sections,  # type: ignore[private-usage]
)
from cortex.tools.plan_roadmap import (
    _register_plan_entry as register_plan_entry,  # type: ignore[private-usage]
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
            "cortex.tools.plan_roadmap.resolve_project_root_async",
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
        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True)
        roadmap = memory_bank_dir / "roadmap.md"
        _ = roadmap.write_text(
            "# Roadmap\n\n## Blockers (ASAP Priority)\nNone\n\n"
            + "## Active Work (in progress)\n\n## Future Enhancements\n\n"
            + "## Pending plans (from .cortex/plans)\n- **Other** - PENDING\n"
        )
        with patch(
            "cortex.tools.plan_roadmap.resolve_project_root_async",
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

    def test_register_duplicate_plan_path_is_noop(self) -> None:
        """Test that registering plan with same plan path is a no-op."""
        content = """# Roadmap

## Blockers (ASAP Priority)

- **Investigate Tool** - PENDING - Plan: .cortex/plans/phase-investigate-tool-failure-20260217-123456.md.

## Other Section
"""
        # Try to register plan with same plan path
        updated, line_inserted = register_plan_entry(
            content,
            plan_title="Investigate Tool Again",
            description="Plan: .cortex/plans/phase-investigate-tool-failure-20260217-123456.md.",
            status="PENDING",
            section_id="blockers",
        )

        # Should return unchanged content (no-op)
        assert updated == content
        assert line_inserted is None

    def test_register_exact_duplicate_line_is_noop(self) -> None:
        """Test that registering exact duplicate entry is a no-op."""
        content = """# Roadmap

## Pending plans (from .cortex/plans)

- **Plan A** - PENDING - Plan: .cortex/plans/plan-a.md.

## Other Section
"""
        # Try to register exact same plan
        updated, line_inserted = register_plan_entry(
            content,
            plan_title="Plan A",
            description="Plan: .cortex/plans/plan-a.md.",
            status="PENDING",
            section_id="pending",
        )

        # Should return unchanged content (no-op)
        assert updated == content
        assert line_inserted is None

    def test_register_different_plan_path_succeeds(self) -> None:
        """Test that registering plan with different plan path succeeds."""
        content = """# Roadmap

## Blockers (ASAP Priority)

- **Investigate Tool A** - PENDING - Plan: .cortex/plans/phase-investigate-tool-a-failure-20260217-123456.md.

## Other Section
"""
        # Register plan with different plan path
        updated, line_inserted = register_plan_entry(
            content,
            plan_title="Investigate Tool B",
            description="Plan: .cortex/plans/phase-investigate-tool-b-failure-20260217-123456.md.",
            status="PENDING",
            section_id="blockers",
        )

        # Should succeed (different plan path)
        assert updated != content
        assert line_inserted is not None
        assert "phase-investigate-tool-b-failure" in updated


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
            plans_dir = get_cortex_path(root, CortexResourceType.PLANS)
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


class TestExtractFirstHeading:
    """Test _extract_first_heading helper."""

    def test_extracts_first_heading(self) -> None:
        """First # line is returned without # prefix."""
        content = "# My Plan Title\n\n**Status**: Pending\n"
        assert extract_first_heading(content) == "My Plan Title"

    def test_extracts_second_level_heading(self) -> None:
        """## heading is accepted."""
        content = "## Goal\n\nSome text\n"
        assert extract_first_heading(content) == "Goal"

    def test_returns_none_when_no_heading(self) -> None:
        """No # line returns None."""
        content = "Plain text only\n"
        assert extract_first_heading(content) is None

    def test_empty_content_returns_none(self) -> None:
        """Empty string returns None."""
        assert extract_first_heading("") is None


class TestExtractStatusLine:
    """Test _extract_status_line helper."""

    def test_extracts_status_value(self) -> None:
        """**Status**: Pending is extracted."""
        content = "**Status**: Pending\n"
        assert extract_status_line(content) == "Pending"

    def test_returns_none_when_no_status(self) -> None:
        """No Status line returns None."""
        content = "# Title\n\nNo status here.\n"
        assert extract_status_line(content) is None

    def test_case_insensitive_status_key(self) -> None:
        """**status** (lowercase) is matched."""
        content = "**status**: In Progress\n"
        assert extract_status_line(content) == "In Progress"


class TestListPlanFiles:
    """Test _list_plan_files helper."""

    def test_lists_root_plans_only_when_exclude_archive(self) -> None:
        """With include_archive=False, only non-archive plans are listed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            plans_dir = get_cortex_path(root, CortexResourceType.PLANS)
            plans_dir.mkdir(parents=True)
            _ = (plans_dir / "a.md").write_text("# A")
            _ = (plans_dir / "b.md").write_text("# B")
            archive = plans_dir / "archive"
            archive.mkdir()
            _ = (archive / "old.md").write_text("# Old")
            pairs, err = list_plan_files(root, include_archive=False)
        assert err is None
        slugs = [p[0] for p in pairs]
        assert "a" in slugs
        assert "b" in slugs
        assert "old" not in slugs

    def test_includes_archive_when_requested(self) -> None:
        """With include_archive=True, archive plans are included."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            plans_dir = get_cortex_path(root, CortexResourceType.PLANS)
            plans_dir.mkdir(parents=True)
            _ = (plans_dir / "x.md").write_text("# X")
            (plans_dir / "archive").mkdir()
            _ = (plans_dir / "archive" / "y.md").write_text("# Y")
            pairs, err = list_plan_files(root, include_archive=True)
        assert err is None
        slugs = [p[0] for p in pairs]
        assert "x" in slugs
        assert "y" in slugs

    def test_returns_empty_when_plans_dir_missing(self) -> None:
        """When plans dir does not exist, returns empty list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pairs, err = list_plan_files(root, include_archive=False)
        assert err is None
        assert pairs == []


class TestGetPlanPath:
    """Test _get_plan_path helper."""

    def test_resolves_root_plan(self) -> None:
        """Finds plan at plans root."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            plans_dir = get_cortex_path(root, CortexResourceType.PLANS)
            plans_dir.mkdir(parents=True)
            _ = (plans_dir / "my-plan.md").write_text("# My Plan")
            path = get_plan_path(root, "my-plan")
        assert path is not None
        assert path.name == "my-plan.md"

    def test_returns_none_when_not_found(self) -> None:
        """Returns None when slug has no matching file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            plans_dir = get_cortex_path(root, CortexResourceType.PLANS)
            plans_dir.mkdir(parents=True)
            path = get_plan_path(root, "nonexistent")
        assert path is None


class TestListPlansImpl:
    """Test _list_plans_impl."""

    def test_returns_entries_with_titles(self) -> None:
        """List entries include slug and title from first heading."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            plans_dir = get_cortex_path(root, CortexResourceType.PLANS)
            plans_dir.mkdir(parents=True)
            _ = (plans_dir / "phase-1.md").write_text(
                "# Phase 1: Foundation\n\nContent"
            )
            result = list_plans_impl(root, include_archive=False)
        assert result.status == "success"
        assert len(result.plans) == 1
        assert result.plans[0].slug == "phase-1"
        assert result.plans[0].title == "Phase 1: Foundation"


class TestGetPlanImpl:
    """Test _get_plan_impl."""

    def test_content_format_returns_full_content(self) -> None:
        """response_format=content returns full markdown."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            plans_dir = get_cortex_path(root, CortexResourceType.PLANS)
            plans_dir.mkdir(parents=True)
            _ = (plans_dir / "test.md").write_text(
                "# Test\n\n**Status**: Pending\n\nBody"
            )
            result = get_plan_impl(root, "test", "content")
        assert result.status == "success"
        assert result.content == "# Test\n\n**Status**: Pending\n\nBody"
        assert result.slug == "test"

    def test_metadata_format_returns_title_and_status(self) -> None:
        """response_format=metadata returns title and plan_status."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            plans_dir = get_cortex_path(root, CortexResourceType.PLANS)
            plans_dir.mkdir(parents=True)
            _ = (plans_dir / "test.md").write_text("# My Plan\n\n**Status**: Pending\n")
            result = get_plan_impl(root, "test", "metadata")
        assert result.status == "success"
        assert result.title == "My Plan"
        assert result.plan_status == "Pending"
        assert result.content is None

    def test_not_found_returns_error(self) -> None:
        """Unknown slug returns error result."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            get_cortex_path(root, CortexResourceType.PLANS).mkdir(parents=True)
            result = get_plan_impl(root, "missing", "content")
        assert result.status == "error"
        assert "not found" in result.message.lower()


class TestListPlansTool:
    """Test list_plans MCP tool."""

    @pytest.mark.asyncio
    async def test_list_plans_returns_json(self, tmp_path: Path) -> None:
        """list_plans returns valid ListPlansResult JSON."""
        plans_dir = get_cortex_path(tmp_path, CortexResourceType.PLANS)
        plans_dir.mkdir(parents=True)
        _ = (plans_dir / "one.md").write_text("# One")
        with patch(
            "cortex.tools.plan_crud.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=tmp_path,
        ):
            result_str = await list_plans(include_archive=False, ctx=None)
        result = ListPlansResult.model_validate_json(result_str)
        assert result.status == "success"
        assert len(result.plans) >= 1
        assert any(p.slug == "one" for p in result.plans)


class TestGetPlanTool:
    """Test get_plan MCP tool."""

    @pytest.mark.asyncio
    async def test_get_plan_content_returns_full_text(self, tmp_path: Path) -> None:
        """get_plan with response_format=content returns plan content."""
        plans_dir = get_cortex_path(tmp_path, CortexResourceType.PLANS)
        plans_dir.mkdir(parents=True)
        _ = (plans_dir / "my-plan.md").write_text("# My Plan\n\nBody text")
        with patch(
            "cortex.tools.plan_crud.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=tmp_path,
        ):
            result_str = await get_plan(
                slug="my-plan", response_format="content", ctx=None
            )
        result = GetPlanResult.model_validate_json(result_str)
        assert result.status == "success"
        assert result.content == "# My Plan\n\nBody text"
        assert result.slug == "my-plan"

    @pytest.mark.asyncio
    async def test_get_plan_not_found_returns_error(self, tmp_path: Path) -> None:
        """get_plan with unknown slug returns error."""
        get_cortex_path(tmp_path, CortexResourceType.PLANS).mkdir(parents=True)
        with patch(
            "cortex.tools.plan_crud.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=tmp_path,
        ):
            result_str = await get_plan(slug="nonexistent", ctx=None)
        result = GetPlanResult.model_validate_json(result_str)
        assert result.status == "error"
        assert "not found" in result.message.lower()
