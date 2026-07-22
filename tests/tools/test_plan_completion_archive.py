"""
Tests for plan_completion archive/integration behavior (split from
test_plan_completion.py to satisfy file size limits).

Covers: dependency resync after complete, archive routing, end-to-end
integration, the plan() MCP tool wrapper, progress-entry parenthesis
validation, and error propagation from apply_progress_and_archive.
"""

import json
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, patch

import pytest

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.plans.completion import complete_plan
from cortex.tools.plans.plan import plan as plan_tool
from cortex.tools.plans.register_artifact_graph import (
    sync_plan_dependency_statuses_after_completion,
)


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


def _write_plan_frontmatter(
    path: Path, *, title: str, status: str, depends_on: list[str]
) -> None:
    deps = ", ".join(f'"{d}"' for d in depends_on)
    body = (
        "---\n"
        + f"title: {title}\n"
        + f"status: {status}\n"
        + f"depends_on: [{deps}]\n"
        + "---\n\n"
    )
    _ = path.write_text(body, encoding="utf-8")


def _seed_sweep_roadmap_and_blocked_follower(tmp_path: Path) -> Path:
    """Memory bank + plans: DONE foundation, BLOCKED follow, roadmap **Sweep**."""
    mem = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
    mem.mkdir(parents=True)
    plans = get_cortex_path(tmp_path, CortexResourceType.PLANS)
    plans.mkdir(parents=True)
    _write_plan_frontmatter(
        plans / "foundation.md",
        title="foundation",
        status="DONE",
        depends_on=[],
    )
    _write_plan_frontmatter(
        plans / "follow.md",
        title="follow",
        status="BLOCKED",
        depends_on=["foundation"],
    )
    _ = (mem / "roadmap.md").write_text(
        "# Roadmap\n\n## Pending\n\n- **Sweep** - PENDING\n",
        encoding="utf-8",
    )
    _ = (mem / "activeContext.md").write_text(
        "# Active\n\n## Completed Work (2026-04-11)\n\n", encoding="utf-8"
    )
    return plans


class TestCompletePlanDependencyResync:
    """Post-complete artifact graph resync (Step 5)."""

    @pytest.mark.asyncio
    async def test_sync_unblocks_when_dependency_done_in_archive(
        self, tmp_path: Path
    ) -> None:
        plans = get_cortex_path(tmp_path, CortexResourceType.PLANS)
        arch = plans / "archive" / "Other"
        arch.mkdir(parents=True)
        _write_plan_frontmatter(
            arch / "base.md", title="base", status="DONE", depends_on=[]
        )
        _write_plan_frontmatter(
            plans / "leaf.md", title="leaf", status="BLOCKED", depends_on=["base"]
        )

        n = await sync_plan_dependency_statuses_after_completion(tmp_path, None)
        assert n == 1
        assert "status: READY" in (plans / "leaf.md").read_text(encoding="utf-8")

    @pytest.mark.asyncio
    async def test_complete_plan_reports_plans_unblocked(self, tmp_path: Path) -> None:
        plans = _seed_sweep_roadmap_and_blocked_follower(tmp_path)
        with _patch_root(tmp_path):
            result_str = await complete_plan(
                plan_title="Sweep",
                summary="Done.",
                completion_date="2026-04-11",
                plan_file_name=None,
            )
        result = json.loads(result_str)
        assert result["status"] == "success"
        assert result.get("plans_unblocked") == 1
        assert "Unblocked 1 dependent" in (result.get("message") or "")
        assert "status: READY" in (plans / "follow.md").read_text(encoding="utf-8")


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

    def test_balanced_parens_mid_title_are_valid(self) -> None:
        """Balanced parens used as ordinary title text (not a '(date)' suffix)
        must not false-positive, even when not immediately closed by '**'."""
        from cortex.tools.plans.completion_validation import (
            validate_progress_entry_text,
        )

        entry = (
            "**Fix plan(graph) archive blindness** - COMPLETE. Masking satisfied deps."
        )
        assert validate_progress_entry_text(entry) is None


class TestApplyProgressAndArchivePropagatesFailure:
    """apply_progress_and_archive surfaces a failed progress append (not silent)."""

    @pytest.mark.asyncio
    async def test_complete_plan_reports_error_when_progress_entry_invalid(
        self, tmp_path: Path
    ) -> None:
        mem = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        mem.mkdir(parents=True)
        roadmap = mem / "roadmap.md"
        _ = roadmap.write_text(
            "# Roadmap\n\n## Pending\n\n- **Progress fail case** - PENDING\n"
        )
        active = mem / "activeContext.md"
        _ = active.write_text("# Active\n\n## Completed Work (2026-02-09)\n\n")
        _ = (mem / "progress.md").write_text("# Progress\n\n## 2026-02-09\n\n")
        with _patch_root(tmp_path):
            result_str = await complete_plan(
                plan_title="Progress fail case",
                summary="Done.",
                completion_date="2026-02-09",
                progress_entry="20260209COMPLETE",
            )
        result = json.loads(result_str)
        assert result["status"] == "error"
        assert result.get("error")
        assert " - COMPLETE" in (result.get("error") or "")
        assert result.get("progress_line_inserted") is None
        # Roadmap/activeContext steps already completed before the failing
        # progress step are not rolled back.
        assert result["roadmap_line_removed"] is not None
        assert result["active_context_line_inserted"] is not None
        assert "Progress fail case" not in roadmap.read_text()
