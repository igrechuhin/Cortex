"""
Tests for plan_completion module.

Tests complete_plan: move a plan from roadmap to activeContext.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from cortex.tools.plan_completion import (
    CompletePlanResult,
    _append_completed_entry,  # type: ignore[private-usage]
    _create_section_and_append,  # type: ignore[private-usage]
    _find_completed_work_section,  # type: ignore[private-usage]
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


class TestCompletePlanResult:
    """Test CompletePlanResult model."""

    def test_success_serialization(self) -> None:
        result = CompletePlanResult(
            status="success",
            message="Moved",
            roadmap_line_removed=5,
            active_context_line_inserted=10,
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
            error="No bullet",
        )
        data = json.loads(result.model_dump_json())
        assert data["status"] == "error"
        assert "No bullet" in data.get("error", "")


class TestCompletePlanIntegration:
    """Integration tests for complete_plan tool."""

    @pytest.mark.asyncio
    async def test_complete_plan_moves_entry(self, tmp_path: Path) -> None:
        mem = tmp_path / ".cortex" / "memory-bank"
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
        mem = tmp_path / ".cortex" / "memory-bank"
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
