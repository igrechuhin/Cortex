"""
Tests for plan_completion module.

Tests public API: complete_plan, update_memory_bank (consolidates
roadmap and append_entry operations).
"""

import json
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, patch

import pytest

from cortex.core.models import OperationStatus
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.plans.completion import CompletePlanResult, complete_plan
from cortex.tools.plans.plan import plan as plan_tool
from cortex.tools.plans.update_memory_bank import update_memory_bank


@contextmanager
def _patch_root(tmp_path: Path):
    """Patch all project-root resolvers used by plan/complete/log hooks."""
    with ExitStack() as stack:
        _ = stack.enter_context(
            patch(
                "cortex.tools.plans.completion.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=tmp_path,
            )
        )
        _ = stack.enter_context(
            patch(
                "cortex.tools.plans.operations_log_hooks.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=tmp_path,
            )
        )
        _ = stack.enter_context(
            patch(
                "cortex.tools.plans.crud.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=tmp_path,
            )
        )
        yield


def _append_progress(date_str: str, entry_text: str):
    """Call update_memory_bank(operation=progress_append)."""
    return update_memory_bank(
        operation="progress_append", date_str=date_str, entry_text=entry_text
    )


def _append_active_context(date_str: str, title: str, summary: str):
    """Call update_memory_bank(operation=active_context_append)."""
    return update_memory_bank(
        operation="active_context_append",
        date_str=date_str,
        title=title,
        summary=summary,
    )


def _parse_wrapper_result(result_str: str) -> dict[str, object]:
    outer = json.loads(result_str)
    inner_raw = outer.get("result", outer)
    return json.loads(inner_raw) if isinstance(inner_raw, str) else inner_raw


def _setup_complete_smoke_files(tmp_path: Path) -> tuple[Path, Path]:
    mem = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
    mem.mkdir(parents=True)
    roadmap = mem / "roadmap.md"
    _ = roadmap.write_text(
        "# Roadmap\n\n## Pending\n\n- **Wire optimization** - PENDING - Connect config.\n"
    )
    active = mem / "activeContext.md"
    _ = active.write_text("# Active Context\n\n## Completed Work (2026-02-05)\n\n")
    return roadmap, active


class TestCompletePlanFindRoadmapBullet:
    """complete_plan finds and removes the matching roadmap bullet (public API)."""

    @pytest.mark.asyncio
    async def test_finds_bullet_containing_title(self, tmp_path: Path) -> None:
        mem = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        mem.mkdir(parents=True)
        roadmap = mem / "roadmap.md"
        _ = roadmap.write_text(
            "# Roadmap\n\n## Pending\n\n"
            + "- **Wire optimization** - PENDING - Connect config.\n"
        )
        _ = (mem / "activeContext.md").write_text(
            "# Active\n\n## Completed Work (2026-02-05)\n\n"
        )
        with _patch_root(tmp_path):
            result_str = await complete_plan(
                plan_title="Wire optimization",
                summary="Done.",
                completion_date="2026-02-05",
            )
        result = json.loads(result_str)
        assert result["status"] == "success"
        assert result["roadmap_line_removed"] is not None
        assert "Wire optimization" not in roadmap.read_text()

    @pytest.mark.asyncio
    async def test_returns_error_when_plan_not_found(self, tmp_path: Path) -> None:
        mem = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        mem.mkdir(parents=True)
        _ = (mem / "roadmap.md").write_text(
            "# Roadmap\n\n## Pending\n\n- **Other** - PENDING\n"
        )
        _ = (mem / "activeContext.md").write_text(
            "# Active\n\n## Completed Work (2026-02-05)\n\n"
        )
        with _patch_root(tmp_path):
            result_str = await complete_plan(
                plan_title="Wire optimization",
                summary="Done.",
                completion_date="2026-02-05",
            )
        result = json.loads(result_str)
        assert result["status"] == "error"
        assert (
            "not found" in result.get("message", "").lower()
            or "bullet" in (result.get("error") or "").lower()
        )

    @pytest.mark.asyncio
    async def test_first_match_wins(self, tmp_path: Path) -> None:
        mem = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        mem.mkdir(parents=True)
        roadmap = mem / "roadmap.md"
        _ = roadmap.write_text(
            "# Roadmap\n\n## Pending\n\n"
            + "- **Phase A** - PENDING\n"
            + "- **Phase B** - PENDING\n"
        )
        _ = (mem / "activeContext.md").write_text(
            "# Active\n\n## Completed Work (2026-02-05)\n\n"
        )
        with _patch_root(tmp_path):
            result_str = await complete_plan(
                plan_title="Phase",
                summary="Done.",
                completion_date="2026-02-05",
            )
        result = json.loads(result_str)
        assert result["status"] == "success"
        text = roadmap.read_text()
        assert "Phase A" not in text
        assert "Phase B" in text


class TestCompletePlanCompletedWorkSection:
    """complete_plan appends to or creates Completed Work section (public API)."""

    @pytest.mark.asyncio
    async def test_appends_to_existing_section(self, tmp_path: Path) -> None:
        mem = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        mem.mkdir(parents=True)
        _ = (mem / "roadmap.md").write_text(
            "# Roadmap\n\n## Pending\n\n- **New plan** - PENDING\n"
        )
        active = mem / "activeContext.md"
        _ = active.write_text(
            "# Active\n\n## Completed Work (2026-02-05)\n\n"
            + "- ✅ **Old** - COMPLETE (2026-02-05) - x\n"
        )
        with _patch_root(tmp_path):
            result_str = await complete_plan(
                plan_title="New plan",
                summary="Summary",
                completion_date="2026-02-05",
            )
        result = json.loads(result_str)
        assert result["status"] == "success"
        assert "**New plan**" in active.read_text()
        assert "Summary" in active.read_text()

    @pytest.mark.asyncio
    async def test_creates_section_when_missing(self, tmp_path: Path) -> None:
        mem = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        mem.mkdir(parents=True)
        _ = (mem / "roadmap.md").write_text(
            "# Roadmap\n\n## Pending\n\n- **New plan** - PENDING\n"
        )
        active = mem / "activeContext.md"
        _ = active.write_text("# Active\n\n## Completed Work (2026-02-04)\n\n")
        with _patch_root(tmp_path):
            result_str = await complete_plan(
                plan_title="New plan",
                summary="Summary",
                completion_date="2026-02-05",
            )
        result = json.loads(result_str)
        assert result["status"] == "success"
        text = active.read_text()
        assert "## Completed Work (2026-02-05)" in text
        assert "**New plan**" in text


class TestAppendProgressEntry:
    """update_memory_bank(operation=progress_append) public API."""

    @pytest.mark.asyncio
    async def test_appends_to_existing_date_section(self, tmp_path: Path) -> None:
        mem = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        mem.mkdir(parents=True)
        progress = mem / "progress.md"
        _ = progress.write_text(
            "# Progress Log\n\n## 2026-02-09\n\n- **Old** - COMPLETE.\n"
        )
        with _patch_root(tmp_path):
            result_str = await _append_progress(
                "2026-02-09", "**New step** - COMPLETE. Done."
            )
        result = json.loads(result_str)
        assert result["status"] == "success"
        assert result.get("line_inserted") is not None
        assert "**New step**" in progress.read_text()

    @pytest.mark.asyncio
    async def test_creates_date_section_when_missing(self, tmp_path: Path) -> None:
        mem = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        mem.mkdir(parents=True)
        progress = mem / "progress.md"
        _ = progress.write_text("# Progress\n\n## 2026-02-08\n\n")
        with _patch_root(tmp_path):
            result_str = await _append_progress(
                "2026-02-09", "**New** - COMPLETE. Summary."
            )
        result = json.loads(result_str)
        assert result["status"] == "success"
        text = progress.read_text()
        assert "## 2026-02-09" in text
        assert "**New**" in text

    @pytest.mark.asyncio
    async def test_returns_error_when_file_missing(self, tmp_path: Path) -> None:
        get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK).mkdir(parents=True)
        with _patch_root(tmp_path):
            result_str = await _append_progress("2026-02-09", "**New** - COMPLETE.")
        result = json.loads(result_str)
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_rejects_malformed_progress_entry(self, tmp_path: Path) -> None:
        mem = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        mem.mkdir(parents=True)
        _ = (mem / "progress.md").write_text(
            "# Progress\n\n## 2026-02-09\n\n- **Old** - COMPLETE.\n"
        )
        with _patch_root(tmp_path):
            result_str = await _append_progress("2026-02-09", "20260209COMPLETE")
        result = json.loads(result_str)
        assert result["status"] == "error"
        assert result.get("error")
        assert " - COMPLETE" in (result.get("error") or "")

    @pytest.mark.asyncio
    async def test_rejects_invalid_date(self, tmp_path: Path) -> None:
        mem = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        mem.mkdir(parents=True)
        _ = (mem / "progress.md").write_text(
            "# Progress\n\n## 2026-02-09\n\n- **Old** - COMPLETE.\n"
        )
        with _patch_root(tmp_path):
            result_str = await _append_progress(
                "2026/02/09", "**New** - COMPLETE. Done."
            )
        result = json.loads(result_str)
        assert result["status"] == "error"
        assert "date" in (result.get("error") or "").lower()


class TestAppendProgressEntryValidation:
    """Progress entry format validation via update_memory_bank(operation=progress_append)."""

    @pytest.mark.asyncio
    async def test_valid_formats_accepted(self, tmp_path: Path) -> None:
        mem = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        mem.mkdir(parents=True)
        _ = (mem / "progress.md").write_text("# Progress\n\n## 2026-02-09\n\n")
        with _patch_root(tmp_path):
            for entry in (
                "**Title** - COMPLETE. Summary.",
                ")** - COMPLETE. Done.",
                "**Phase 54 (2026-02-20)** - COMPLETE. Implemented.",
                "**Ongoing** - In progress.",
            ):
                result_str = await _append_progress("2026-02-09", entry)
                result = json.loads(result_str)
                assert result["status"] == "success", f"Rejected valid: {entry!r}"

    @pytest.mark.asyncio
    async def test_invalid_formats_rejected(self, tmp_path: Path) -> None:
        mem = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        mem.mkdir(parents=True)
        _ = (mem / "progress.md").write_text("# Progress\n\n## 2026-02-09\n\n")
        with _patch_root(tmp_path):
            for entry, fragment in (
                ("**Title (2026-02-20** - COMPLETE. Done.", ")** - COMPLETE"),
                ("20260209COMPLETE", " - COMPLETE"),
                ("COMPLETE", None),
            ):
                result_str = await _append_progress("2026-02-09", entry)
                result = json.loads(result_str)
                assert result["status"] == "error", f"Accepted invalid: {entry!r}"
                if fragment:
                    assert fragment in (result.get("error") or "")


class TestCompletePlanDateValidation:
    """Date validation (YYYY-MM-DD) via complete_plan and update_memory_bank."""

    @pytest.mark.asyncio
    async def test_complete_plan_rejects_invalid_date(self) -> None:
        result_str = await complete_plan(
            plan_title="Any plan",
            summary="Summary",
            completion_date="2026/02/05",
        )
        result = json.loads(result_str)
        assert result["status"] == "error"
        assert "date" in (result.get("error") or "").lower() or "YYYY-MM-DD" in (
            result.get("error") or ""
        )

    @pytest.mark.asyncio
    async def test_append_progress_rejects_invalid_dates(self, tmp_path: Path) -> None:
        mem = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        mem.mkdir(parents=True)
        _ = (mem / "progress.md").write_text("# Progress\n\n## 2026-02-09\n\n")
        valid_entry = "**X** - COMPLETE. Done."
        with _patch_root(tmp_path):
            for bad_date in ("", "2026-2-20", "20260220", "2026/02/20", "2026-02-30"):
                result_str = await _append_progress(bad_date, valid_entry)
                result = json.loads(result_str)
                assert result["status"] == "error", f"Accepted date: {bad_date!r}"


class TestAppendActiveContextEntry:
    """update_memory_bank(operation=active_context_append) public API."""

    @pytest.mark.asyncio
    async def test_appends_to_existing_section(self, tmp_path: Path) -> None:
        mem = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        mem.mkdir(parents=True)
        active = mem / "activeContext.md"
        _ = active.write_text("# Active\n\n## Completed Work (2026-02-09)\n\n")
        with _patch_root(tmp_path):
            result_str = await _append_active_context(
                "2026-02-09", "New step", "Summary of work."
            )
        result = json.loads(result_str)
        assert result["status"] == "success"
        assert result.get("line_inserted") is not None
        text = active.read_text()
        assert "New step" in text
        assert "Summary of work" in text

    @pytest.mark.asyncio
    async def test_returns_error_when_file_missing(self, tmp_path: Path) -> None:
        get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK).mkdir(parents=True)
        with _patch_root(tmp_path):
            result_str = await _append_active_context("2026-02-09", "Title", "Summary")
        result = json.loads(result_str)
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_skips_duplicate_same_date_and_title(self, tmp_path: Path) -> None:
        """When same date and title already exist, append is skipped (no duplicate bullet)."""
        mem = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        mem.mkdir(parents=True)
        active = mem / "activeContext.md"
        existing = (
            "# Active\n\n## Completed Work (2026-02-09)\n\n"
            "- ✅ **E2E Plan Test** - COMPLETE (2026-02-09) - Done.\n"
        )
        _ = active.write_text(existing)
        with _patch_root(tmp_path):
            result_str = await _append_active_context(
                "2026-02-09", "E2E Plan Test", "Another summary."
            )
        result = json.loads(result_str)
        assert result["status"] == "success"
        assert result.get("line_inserted") is None
        assert "Skipped duplicate" in (result.get("message") or "")
        assert active.read_text() == existing


class TestCompletePlanResult:
    """CompletePlanResult model."""

    def test_success_serialization(self) -> None:
        result = CompletePlanResult(
            status=OperationStatus.SUCCESS,
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
            status=OperationStatus.ERROR,
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


class TestCompletePlanArchive:
    """complete_plan with plan_file_name: archive behavior (public API)."""

    @pytest.mark.asyncio
    async def test_rejects_path_traversal_in_plan_file_name(
        self, tmp_path: Path
    ) -> None:
        mem = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        mem.mkdir(parents=True)
        _ = (mem / "roadmap.md").write_text(
            "# Roadmap\n\n## Pending\n\n- **Some plan** - PENDING\n"
        )
        _ = (mem / "activeContext.md").write_text(
            "# Active\n\n## Completed Work (2026-02-09)\n\n"
        )
        with _patch_root(tmp_path):
            result_str = await complete_plan(
                plan_title="Some plan",
                summary="Done.",
                completion_date="2026-02-09",
                plan_file_name="session-optimization/../evil.md",
            )
        result = json.loads(result_str)
        assert result["status"] == "error"
        assert "single filename" in (result.get("error") or "").lower()

    @pytest.mark.asyncio
    async def test_returns_error_when_plan_file_not_found(self, tmp_path: Path) -> None:
        mem = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        mem.mkdir(parents=True)
        _ = (mem / "roadmap.md").write_text(
            "# Roadmap\n\n## Pending\n\n- **Some plan** - PENDING\n"
        )
        _ = (mem / "activeContext.md").write_text(
            "# Active\n\n## Completed Work (2026-02-09)\n\n"
        )
        get_cortex_path(tmp_path, CortexResourceType.PLANS).mkdir(parents=True)
        with _patch_root(tmp_path):
            result_str = await complete_plan(
                plan_title="Some plan",
                summary="Done.",
                completion_date="2026-02-09",
                plan_file_name="session-optimization-missing.md",
            )
        result = json.loads(result_str)
        assert result["status"] == "error"
        assert "not found" in (result.get("error") or "").lower()

    @pytest.mark.asyncio
    async def test_moves_session_optimization_to_archive(self, tmp_path: Path) -> None:
        plans = get_cortex_path(tmp_path, CortexResourceType.PLANS)
        plans.mkdir(parents=True)
        plan_name = "session-optimization-foo.md"
        _ = (plans / plan_name).write_text("# Plan\n")
        mem = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        mem.mkdir(parents=True)
        _ = (mem / "roadmap.md").write_text(
            "# Roadmap\n\n## Pending\n\n- **Foo** - PENDING\n"
        )
        _ = (mem / "activeContext.md").write_text(
            "# Active\n\n## Completed Work (2026-02-09)\n\n"
        )
        with _patch_root(tmp_path):
            result_str = await complete_plan(
                plan_title="Foo",
                summary="Done.",
                completion_date="2026-02-09",
                plan_file_name=plan_name,
            )
        result = json.loads(result_str)
        assert result["status"] == "success"
        assert result.get("archive_path")
        assert "SessionOptimization" in (result.get("archive_path") or "")
        assert not (plans / plan_name).exists()
        archive = get_cortex_path(tmp_path, CortexResourceType.PLANS_ARCHIVE)
        assert (archive / "SessionOptimization" / plan_name).exists()

    @pytest.mark.asyncio
    async def test_moves_phase_plan_to_phase_n_subdir(self, tmp_path: Path) -> None:
        plans = get_cortex_path(tmp_path, CortexResourceType.PLANS)
        plans.mkdir(parents=True)
        plan_name = "phase-9-excellence-98.md"
        _ = (plans / plan_name).write_text("# Plan\n")
        mem = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        mem.mkdir(parents=True)
        _ = (mem / "roadmap.md").write_text(
            "# Roadmap\n\n## Pending\n\n- **Phase 9** - PENDING\n"
        )
        _ = (mem / "activeContext.md").write_text(
            "# Active\n\n## Completed Work (2026-02-09)\n\n"
        )
        with _patch_root(tmp_path):
            result_str = await complete_plan(
                plan_title="Phase 9",
                summary="Done.",
                completion_date="2026-02-09",
                plan_file_name=plan_name,
            )
        result = json.loads(result_str)
        assert result["status"] == "success"
        assert "Phase9" in (result.get("archive_path") or "")
        archive = get_cortex_path(tmp_path, CortexResourceType.PLANS_ARCHIVE)
        assert (archive / "Phase9" / plan_name).exists()

    @pytest.mark.asyncio
    async def test_moves_investigate_plan_to_investigations_date(
        self, tmp_path: Path
    ) -> None:
        plans = get_cortex_path(tmp_path, CortexResourceType.PLANS)
        plans.mkdir(parents=True)
        plan_name = "phase-investigate-foo-20260204-123456.md"
        _ = (plans / plan_name).write_text("# Plan\n")
        mem = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        mem.mkdir(parents=True)
        _ = (mem / "roadmap.md").write_text(
            "# Roadmap\n\n## Pending\n\n- **Investigate foo** - PENDING\n"
        )
        _ = (mem / "activeContext.md").write_text(
            "# Active\n\n## Completed Work (2026-02-09)\n\n"
        )
        with _patch_root(tmp_path):
            result_str = await complete_plan(
                plan_title="Investigate foo",
                summary="Done.",
                completion_date="2026-02-09",
                plan_file_name=plan_name,
            )
        result = json.loads(result_str)
        assert result["status"] == "success"
        assert "Investigations" in (result.get("archive_path") or "")
        assert "2026-02-04" in (result.get("archive_path") or "")
        archive = get_cortex_path(tmp_path, CortexResourceType.PLANS_ARCHIVE)
        assert (archive / "Investigations" / "2026-02-04" / plan_name).exists()


class TestCompletePlanIntegration:
    """Integration tests for complete_plan."""

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
        with _patch_root(tmp_path):
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
        with _patch_root(tmp_path):
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
    async def test_complete_plan_rejects_invalid_completion_date(self) -> None:
        result_str = await complete_plan(
            plan_title="Any plan",
            summary="Summary",
            completion_date="2026/02/05",
        )
        result = json.loads(result_str)
        assert result["status"] == "error"
        assert "date" in (result.get("error") or "").lower() or "YYYY-MM-DD" in (
            result.get("error") or ""
        )

    @pytest.mark.asyncio
    async def test_complete_plan_with_plan_file_name_archives_file(
        self, tmp_path: Path
    ) -> None:
        plan_basename = "session-optimization-roadmap-full-content-enforcement.md"
        plan_in_root = self._seed_archive_candidate(tmp_path, plan_basename)
        with _patch_root(tmp_path):
            result_str = await complete_plan(
                plan_title="Roadmap full-content enforcement",
                summary="Strengthened plan workflow and memory-bank-updater.",
                completion_date="2026-02-09",
                progress_entry="**Roadmap full-content enforcement** - COMPLETE. Summary.",
                plan_file_name=plan_basename,
            )
        result = json.loads(result_str)
        self._assert_archive_result(tmp_path, plan_basename, plan_in_root, result)

    @staticmethod
    def _seed_archive_candidate(tmp_path: Path, plan_basename: str) -> Path:
        mem = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        mem.mkdir(parents=True)
        plans_dir = get_cortex_path(tmp_path, CortexResourceType.PLANS)
        plans_dir.mkdir(parents=True)
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
        return plan_in_root

    @staticmethod
    def _assert_archive_result(
        tmp_path: Path,
        plan_basename: str,
        plan_in_root: Path,
        result: dict[str, object],
    ) -> None:
        archive_path_str = cast(str, result["archive_path"])
        assert result["status"] == "success"
        assert archive_path_str
        assert "SessionOptimization" in archive_path_str
        assert archive_path_str.endswith(plan_basename)
        assert not plan_in_root.exists()
        archive_path = (
            get_cortex_path(tmp_path, CortexResourceType.PLANS_ARCHIVE)
            / "SessionOptimization"
            / plan_basename
        )
        assert archive_path.exists()
        assert "COMPLETE" in archive_path.read_text()
        assert result.get("progress_line_inserted") is not None


class TestPlanToolCompleteSmoke:
    """Smoke tests for plan(operation='complete') MCP tool wrapper."""

    @pytest.mark.asyncio
    async def test_plan_tool_complete_delegates_to_complete_plan(
        self, tmp_path: Path
    ) -> None:
        """plan(operation='complete', ...) updates roadmap and activeContext like complete_plan."""
        roadmap, active = _setup_complete_smoke_files(tmp_path)

        with _patch_root(tmp_path):
            result_str = await plan_tool(
                operation="complete",
                plan_title="Wire optimization",
                summary="Connected config to runtime.",
                completion_date="2026-02-05",
                progress_entry=None,
                plan_file_name=None,
            )
        wrapper_result = _parse_wrapper_result(result_str)
        assert wrapper_result["status"] == "success"
        assert wrapper_result["roadmap_line_removed"] is not None
        assert wrapper_result["active_context_line_inserted"] is not None
        assert "Wire optimization" not in roadmap.read_text()
        active_text = active.read_text()
        assert "Wire optimization" in active_text
        assert "Connected config to runtime." in active_text

    @pytest.mark.asyncio
    async def test_plan_tool_create_appends_operations_log_entry(
        self, tmp_path: Path
    ) -> None:
        """plan(operation='create') appends a parseable operations-log entry."""
        with _patch_root(tmp_path):
            result_str = await plan_tool(
                operation="create",
                title="Operations log hook test",
                content="# Test plan\n\nBody.",
                slug="operations-log-hook-test",
            )
        result = json.loads(result_str)
        assert result["status"] == "success"
        log_path = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK) / "log.md"
        log_text = log_path.read_text(encoding="utf-8")
        assert "plan | Created plan: Operations log hook test" in log_text

    @pytest.mark.asyncio
    async def test_plan_tool_complete_appends_operations_log_entry(
        self, tmp_path: Path
    ) -> None:
        """plan(operation='complete') appends a parseable operations-log entry."""
        mem = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        mem.mkdir(parents=True)
        _ = (mem / "roadmap.md").write_text(
            "# Roadmap\n\n## Pending\n\n- **Hook target** - PENDING\n"
        )
        _ = (mem / "activeContext.md").write_text(
            "# Active Context\n\n## Completed Work (2026-02-05)\n\n"
        )

        with _patch_root(tmp_path):
            result_str = await plan_tool(
                operation="complete",
                plan_title="Hook target",
                summary="Marked complete via wrapper.",
                completion_date="2026-02-05",
            )
        outer = json.loads(result_str)
        inner_raw = outer.get("result", outer)
        wrapper_result = (
            json.loads(inner_raw) if isinstance(inner_raw, str) else inner_raw
        )
        assert wrapper_result["status"] == "success"
        log_path = mem / "log.md"
        log_text = log_path.read_text(encoding="utf-8")
        assert "plan | Completed plan: Hook target" in log_text


# ---------------------------------------------------------------------------
# validate_progress_entry_text parenthesis fix (Fix 3)
# ---------------------------------------------------------------------------


class TestValidateProgressEntryTextParentheses:
    def test_parens_in_summary_body_are_valid(self) -> None:
        """Parentheses in the summary body (after ' - COMPLETE') must not be rejected."""
        from cortex.tools.plans.completion_validation import (
            validate_progress_entry_text,
        )

        entry = "**Fix quality gate** - COMPLETE. Resolved using autofix() helper."
        assert validate_progress_entry_text(entry) is None

    def test_properly_closed_parens_in_title_are_valid(self) -> None:
        """Title with properly closed '(date)**' is valid."""
        from cortex.tools.plans.completion_validation import (
            validate_progress_entry_text,
        )

        entry = "**Fix quality gate (2026-03-23)** - COMPLETE. Summary."
        assert validate_progress_entry_text(entry) is None

    def test_unclosed_parens_in_title_are_invalid(self) -> None:
        """Unclosed '(' before ' - COMPLETE' with no ')** ' is rejected."""
        from cortex.tools.plans.completion_validation import (
            validate_progress_entry_text,
        )

        entry = "**Fix quality gate (2026-03-23 - COMPLETE. Missing closing."
        assert validate_progress_entry_text(entry) is not None

    def test_no_complete_marker_is_valid(self) -> None:
        """Entry without COMPLETE is always valid (not a completion entry)."""
        from cortex.tools.plans.completion_validation import (
            validate_progress_entry_text,
        )

        entry = "Some note with (parentheses) here."
        assert validate_progress_entry_text(entry) is None
