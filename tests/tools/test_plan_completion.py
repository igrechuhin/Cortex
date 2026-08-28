"""
Tests for plan_completion module.

Tests public API: complete_plan, update_memory_bank (consolidates
roadmap and append_entry operations).

Archive/dependency-resync/integration coverage lives in
test_plan_completion_archive.py (split to satisfy file size limits).
"""

import json
from contextlib import ExitStack, contextmanager
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from cortex.core.models import OperationStatus
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.plans.completion import CompletePlanResult, complete_plan
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
            plans_unblocked=None,
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
            plans_unblocked=None,
        )
        data = json.loads(result.model_dump_json())
        assert data["status"] == "error"
        assert "No bullet" in data.get("error", "")


class TestCompletePlanRejectsMalformedProgressEntryBeforeWriting:
    """A malformed progress_entry must abort before roadmap/activeContext are touched.

    Regression: the format guard used to live inside the progress append, which runs
    *after* the roadmap bullet is removed and the activeContext entry inserted (and after
    the plan file is archived). A rejected entry therefore left a partially completed
    plan the caller had to repair by hand.
    """

    @staticmethod
    def _seed(tmp_path: Path) -> tuple[Path, Path, Path]:
        mem = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        mem.mkdir(parents=True)
        roadmap = mem / "roadmap.md"
        _ = roadmap.write_text(
            "# Roadmap\n\n## Pending\n\n- **Wire optimization** - PENDING - Connect config.\n"
        )
        active = mem / "activeContext.md"
        _ = active.write_text("# Active\n\n## Completed Work (2026-02-05)\n\n")
        progress = mem / "progress.md"
        _ = progress.write_text("# Progress\n\n")
        return roadmap, active, progress

    @pytest.mark.asyncio
    async def test_malformed_entry_leaves_every_file_untouched(
        self, tmp_path: Path
    ) -> None:
        roadmap, active, progress = self._seed(tmp_path)
        before = (roadmap.read_text(), active.read_text(), progress.read_text())

        with _patch_root(tmp_path):
            result_str = await complete_plan(
                plan_title="Wire optimization",
                summary="Done.",
                completion_date="2026-02-05",
                # AI: 'COMPLETE' without the ' - COMPLETE' delimiter is exactly the shape
                # validate_progress_entry_text rejects.
                progress_entry="**Wire optimization** COMPLETE. Connected config.",
            )

        result = json.loads(result_str)
        assert result["status"] == OperationStatus.ERROR
        assert "progress_entry" in result["message"].lower()
        assert " - COMPLETE" in (result["error"] or "")
        # The point of the regression: nothing was written.
        assert result["roadmap_line_removed"] is None
        assert result["active_context_line_inserted"] is None
        assert result["progress_line_inserted"] is None
        assert (roadmap.read_text(), active.read_text(), progress.read_text()) == before
        assert "Wire optimization" in roadmap.read_text()

    @pytest.mark.asyncio
    async def test_well_formed_entry_still_completes(self, tmp_path: Path) -> None:
        roadmap, _active, progress = self._seed(tmp_path)

        with _patch_root(tmp_path):
            result_str = await complete_plan(
                plan_title="Wire optimization",
                summary="Done.",
                completion_date="2026-02-05",
                progress_entry="**Wire optimization** - COMPLETE. Connected config.",
            )

        result = json.loads(result_str)
        assert result["status"] == OperationStatus.SUCCESS
        assert result["roadmap_line_removed"] is not None
        assert result["progress_line_inserted"] is not None
        assert "Wire optimization" not in roadmap.read_text()
        assert "Connected config." in progress.read_text()
