"""
Tests for plan_completion module.

Tests complete_plan: move a plan from roadmap to activeContext.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.plan_completion import (
    CompletePlanResult,
    _append_completed_entry,  # type: ignore[private-usage]
    _append_progress_entry_content,  # type: ignore[private-usage]
    _archive_plan_file,  # type: ignore[private-usage]
    _archive_subdir_for_plan,  # type: ignore[private-usage]
    _create_section_and_append,  # type: ignore[private-usage]
    _execute_append_active_context,  # type: ignore[private-usage]
    _execute_append_progress,  # type: ignore[private-usage]
    _find_completed_work_section,  # type: ignore[private-usage]
    _find_progress_date_section,  # type: ignore[private-usage]
    _find_roadmap_bullet_line,  # type: ignore[private-usage]
    _last_bullet_line_in_range,  # type: ignore[private-usage]
    _remove_line_at,  # type: ignore[private-usage]
    complete_plan,
)


class TestFindRoadmapBulletLine:
    """Tests for _find_roadmap_bullet_line."""

    def test_finds_bullet_containing_title(self) -> None:
        content = "## Pending\n\n- **Wire optimization** - PENDING - Connect config.\n"
        assert _find_roadmap_bullet_line(content, "Wire optimization") == 3

    def test_returns_none_when_not_found(self) -> None:
        content = "## Pending\n\n- **Other** - PENDING\n"
        assert _find_roadmap_bullet_line(content, "Wire optimization") is None

    def test_first_match_wins(self) -> None:
        content = "- **Phase A** - PENDING\n- **Phase B** - PENDING\n"
        assert _find_roadmap_bullet_line(content, "Phase") == 1


class TestRemoveLineAt:
    """Tests for _remove_line_at."""

    def test_removes_line(self) -> None:
        content = "line1\nline2\nline3"
        out = _remove_line_at(content, 2)
        assert out == "line1\nline3"

    def test_removes_first_line(self) -> None:
        content = "a\nb\nc"
        assert _remove_line_at(content, 1) == "b\nc"


class TestFindCompletedWorkSection:
    """Tests for _find_completed_work_section."""

    def test_finds_section(self) -> None:
        content = (
            "# Active\n\n## Completed Work (2026-02-05)\n\n- ✅ **X** - COMPLETE\n"
        )
        section = _find_completed_work_section(content, "2026-02-05")
        assert section is not None
        start, end = section
        assert start == 3
        assert end >= 3

    def test_returns_none_when_date_missing(self) -> None:
        content = "## Completed Work (2026-02-04)\n\n- item\n"
        assert _find_completed_work_section(content, "2026-02-05") is None


class TestLastBulletLineInRange:
    """Tests for _last_bullet_line_in_range."""

    def test_returns_last_bullet_index(self) -> None:
        lines = ["## H", "", "- one", "- two"]
        assert _last_bullet_line_in_range(lines, 0, 4) == 3

    def test_returns_none_when_no_bullet(self) -> None:
        lines = ["## H", "", "text"]
        assert _last_bullet_line_in_range(lines, 0, 3) is None


class TestAppendCompletedEntry:
    """Tests for _append_completed_entry."""

    def test_appends_to_existing_section(self) -> None:
        content = "# Active\n\n## Completed Work (2026-02-05)\n\n- ✅ **Old** - COMPLETE (2026-02-05) - x\n"
        new_content, line = _append_completed_entry(
            content, "2026-02-05", "New plan", "Summary"
        )
        assert line is not None
        assert "**New plan**" in new_content
        assert "COMPLETE (2026-02-05)" in new_content
        assert "Summary" in new_content


class TestCreateSectionAndAppend:
    """Tests for _create_section_and_append."""

    def test_appends_when_section_exists(self) -> None:
        content = (
            "# Active\n\n## Completed Work (2026-02-05)\n\n- ✅ **A** - COMPLETE - a\n"
        )
        new_content, line = _create_section_and_append(
            content, "2026-02-05", "B", "b summary"
        )
        assert line is not None
        assert "**B**" in new_content
        assert "b summary" in new_content


class TestFindProgressDateSection:
    """Tests for _find_progress_date_section."""

    def test_finds_section(self) -> None:
        content = "# Progress Log\n\n## 2026-02-09\n\n- **X** - COMPLETE.\n"
        section = _find_progress_date_section(content, "2026-02-09")
        assert section is not None
        start, end = section
        assert start == 2
        assert end >= 2

    def test_returns_none_when_date_missing(self) -> None:
        content = "# Progress\n\n## 2026-02-08\n\n"
        assert _find_progress_date_section(content, "2026-02-09") is None


class TestAppendProgressEntryContent:
    """Tests for _append_progress_entry_content."""

    def test_appends_to_existing_date_section(self) -> None:
        content = "# Progress Log\n\n## 2026-02-09\n\n" + "- **Old** - COMPLETE.\n"
        new_content, line = _append_progress_entry_content(
            content, "2026-02-09", "**New** - COMPLETE. Summary."
        )
        assert line is not None
        assert "**New**" in new_content
        assert "Summary" in new_content


class TestExecuteAppendProgress:
    """Tests for _execute_append_progress."""

    def test_append_success(self, tmp_path: Path) -> None:
        mem = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        mem.mkdir(parents=True)
        _ = (mem / "progress.md").write_text(
            "# Progress Log\n\n## 2026-02-09\n\n- **Old** - COMPLETE.\n"
        )
        result = _execute_append_progress(
            tmp_path, "2026-02-09", "**New step** - COMPLETE. Done."
        )
        assert result.status == "success"
        assert result.line_inserted is not None
        assert "**New step**" in (mem / "progress.md").read_text()

    def test_append_when_file_missing_returns_error(self, tmp_path: Path) -> None:
        get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK).mkdir(parents=True)
        result = _execute_append_progress(tmp_path, "2026-02-09", "**New** - COMPLETE.")
        assert result.status == "error"


class TestExecuteAppendActiveContext:
    """Tests for _execute_append_active_context."""

    def test_append_success(self, tmp_path: Path) -> None:
        mem = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        mem.mkdir(parents=True)
        _ = (mem / "activeContext.md").write_text(
            "# Active\n\n## Completed Work (2026-02-09)\n\n"
        )
        result = _execute_append_active_context(
            tmp_path, "2026-02-09", "New step", "Summary of work."
        )
        assert result.status == "success"
        assert result.line_inserted is not None
        text = (mem / "activeContext.md").read_text()
        assert "New step" in text
        assert "Summary of work" in text

    def test_append_when_file_missing_returns_error(self, tmp_path: Path) -> None:
        get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK).mkdir(parents=True)
        result = _execute_append_active_context(
            tmp_path, "2026-02-09", "Title", "Summary"
        )
        assert result.status == "error"


class TestCompletePlanResult:
    """Test CompletePlanResult model."""

    def test_success_serialization(self) -> None:
        result = CompletePlanResult(
            status="success",
            message="Moved",
            roadmap_line_removed=5,
            active_context_line_inserted=10,
            progress_line_inserted=None,
            archive_path=None,
            error=None,
        )
        data = json.loads(result.model_dump_json())
        assert data["status"] == "success"
        assert data["roadmap_line_removed"] == 5
        assert data["active_context_line_inserted"] == 10

    def test_error_serialization(self) -> None:
        result = CompletePlanResult(
            status="error",
            message="Not found",
            roadmap_line_removed=None,
            active_context_line_inserted=None,
            progress_line_inserted=None,
            archive_path=None,
            error="No bullet",
        )
        data = json.loads(result.model_dump_json())
        assert data["status"] == "error"
        assert "No bullet" in data.get("error", "")


class TestArchiveSubdirForPlan:
    """Tests for _archive_subdir_for_plan."""

    def test_session_optimization_returns_session_optimization(self) -> None:
        assert (
            _archive_subdir_for_plan("session-optimization-foo.md")
            == "SessionOptimization"
        )

    def test_phase_number_returns_phase_n(self) -> None:
        assert _archive_subdir_for_plan("phase-9-excellence-98.md") == "Phase9"
        assert _archive_subdir_for_plan("phase-53-type-cleanup.md") == "Phase53"

    def test_investigate_with_date_returns_investigations_date(self) -> None:
        assert (
            _archive_subdir_for_plan("phase-investigate-foo-20260204-123456.md")
            == "Investigations/2026-02-04"
        )

    def test_path_traversal_returns_none(self) -> None:
        assert _archive_subdir_for_plan("foo/bar.md") is None
        assert _archive_subdir_for_plan("") is None


class TestArchivePlanFile:
    """Tests for _archive_plan_file."""

    def test_rejects_path_traversal(self, tmp_path: Path) -> None:
        _, err = _archive_plan_file(tmp_path, "session-optimization/../evil.md")
        assert err is not None
        assert "single filename" in (err or "").lower()

    def test_returns_error_when_file_not_found(self, tmp_path: Path) -> None:
        get_cortex_path(tmp_path, CortexResourceType.PLANS).mkdir(parents=True)
        _, err = _archive_plan_file(tmp_path, "session-optimization-missing.md")
        assert err is not None
        assert "not found" in (err or "").lower()

    def test_moves_session_optimization_to_archive_and_removes_from_root(
        self, tmp_path: Path
    ) -> None:
        plans = get_cortex_path(tmp_path, CortexResourceType.PLANS)
        plans.mkdir(parents=True)
        plan_name = "session-optimization-foo.md"
        _ = (plans / plan_name).write_text("# Plan\n")
        path, err = _archive_plan_file(tmp_path, plan_name)
        assert err is None
        assert path is not None
        assert "SessionOptimization" in path
        assert not (plans / plan_name).exists()
        plans_archive = get_cortex_path(tmp_path, CortexResourceType.PLANS_ARCHIVE)
        assert (plans_archive / "SessionOptimization" / plan_name).exists()


class TestCompletePlanIntegration:
    """Integration tests for complete_plan tool."""

    @pytest.mark.asyncio
    async def test_complete_plan_moves_entry(self, tmp_path: Path) -> None:
        mem = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        mem.mkdir(parents=True)
        roadmap = mem / "roadmap.md"
        _ = roadmap.write_text(
            "# Roadmap\n\n## Pending plans\n\n"
            + "- **Wire optimization** - PENDING - Connect config.\n"
        )
        active = mem / "activeContext.md"
        _ = active.write_text(
            "# Active Context\n\n**Completed only.**\n\n"
            + "## Completed Work (2026-02-05)\n\n"
            + "- ✅ **Phase 50** - COMPLETE (2026-02-05) - Plan tools.\n"
        )
        with patch(
            "cortex.tools.plan_completion.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=tmp_path,
        ):
            result_str = await complete_plan(
                plan_title="Wire optimization",
                summary="Connected config to runtime.",
                completion_date="2026-02-05",
            )
        result = json.loads(result_str)
        assert result["status"] == "success"
        assert result["roadmap_line_removed"] is not None
        assert result["active_context_line_inserted"] is not None
        assert "Wire optimization" not in roadmap.read_text()
        assert "Wire optimization" in active.read_text()
        assert "Connected config to runtime" in active.read_text()

    @pytest.mark.asyncio
    async def test_complete_plan_not_found_returns_error(self, tmp_path: Path) -> None:
        mem = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        mem.mkdir(parents=True)
        _ = (mem / "roadmap.md").write_text(
            "# Roadmap\n\n## Pending\n\n- **Other** - PENDING\n"
        )
        _ = (mem / "activeContext.md").write_text(
            "# Active\n\n## Completed Work (2026-02-05)\n\n"
        )
        with patch(
            "cortex.tools.plan_completion.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=tmp_path,
        ):
            result_str = await complete_plan(
                plan_title="Nonexistent plan",
                summary="Summary",
            )
        result = json.loads(result_str)
        assert result["status"] == "error"
        assert (
            "not found" in result.get("message", "").lower()
            or "No roadmap" in (result.get("error") or "")
            or "bullet" in (result.get("error") or "").lower()
        )

    @pytest.mark.asyncio
    async def test_complete_plan_with_plan_file_name_archives_file(
        self, tmp_path: Path
    ) -> None:
        """complete_plan with plan_file_name moves plan file to archive and removes from plans root."""
        mem = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        mem.mkdir(parents=True)
        plans_dir = get_cortex_path(tmp_path, CortexResourceType.PLANS)
        plans_dir.mkdir(parents=True)
        plan_basename = "session-optimization-roadmap-full-content-enforcement.md"
        plan_in_root = plans_dir / plan_basename
        _ = plan_in_root.write_text("# Plan\n\n**Status**: COMPLETE\n")
        _ = (mem / "roadmap.md").write_text(
            "# Roadmap\n\n## Pending\n\n"
            + "- **Roadmap full-content enforcement** - PENDING - Plan: .cortex/plans/"
            + plan_basename
            + "\n"
        )
        _ = (mem / "activeContext.md").write_text(
            "# Active\n\n## Completed Work (2026-02-09)\n\n"
        )
        _ = (mem / "progress.md").write_text("# Progress\n\n## 2026-02-09\n\n")
        with patch(
            "cortex.tools.plan_completion.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=tmp_path,
        ):
            result_str = await complete_plan(
                plan_title="Roadmap full-content enforcement",
                summary="Strengthened create-plan and memory-bank-updater.",
                completion_date="2026-02-09",
                progress_entry="**Roadmap full-content enforcement** - COMPLETE. Summary.",
                plan_file_name=plan_basename,
            )
        result = json.loads(result_str)
        assert result["status"] == "success"
        assert result["archive_path"]
        assert "SessionOptimization" in result["archive_path"]
        assert result["archive_path"].endswith(plan_basename)
        assert not plan_in_root.exists()
        archive_path = (
            get_cortex_path(tmp_path, CortexResourceType.PLANS_ARCHIVE)
            / "SessionOptimization"
            / plan_basename
        )
        assert archive_path.exists()
        assert "COMPLETE" in archive_path.read_text()
        assert result.get("progress_line_inserted") is not None
