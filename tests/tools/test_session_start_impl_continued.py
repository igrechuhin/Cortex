"""Tests for session_start_impl handoffs, gate feedback, lifecycle, and errors."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cortex.core.file_system import FileSystemManager
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.memory.compaction_operations import write_handoff
from cortex.tools.models import (
    SessionHandoff,
    SessionStartErrorResult,
    SessionStartResult,
)
from cortex.tools.session.start_tools import session_start_impl
from tests.helpers.managers import make_test_managers
from tests.helpers.path_helpers import ensure_test_cortex_structure
from tests.tools.session_start_fixtures import (
    ROADMAP_PHASE54_PENDING,
    build_minimal_session_managers,
    managers_after_compact_lifecycle,
    managers_phase54_variant,
    minimal_session_managers_custom_roadmap,
    run_session_start_patched_mcp_healthy,
)


class TestSessionStartImplContinued:
    """Additional session_start_impl scenarios split for file size limits."""

    @pytest.mark.asyncio
    async def test_session_start_impl_includes_handoff(self, tmp_path: Path) -> None:
        """Test that session_start includes handoff when it exists."""
        active_context_content = """# Active Context

## Current Focus

Working on Phase 54.

## Completed Work

- ✅ Phase 50 - COMPLETE
"""
        _memory_bank_dir, managers = await managers_phase54_variant(
            tmp_path,
            active_context=active_context_content,
            roadmap=ROADMAP_PHASE54_PENDING,
        )
        handoff = SessionHandoff(
            session_id="2026-02-20T17-00",
            completed_tasks=["Phase 50 Step 1", "Phase 50 Step 2"],
            in_progress=None,
            decisions_made=["Use Pydantic v2"],
            blockers=[],
            next_actions=["Complete Phase 54"],
        )
        await write_handoff(tmp_path, handoff, managers.fs)
        result = await run_session_start_patched_mcp_healthy(tmp_path, managers)
        assert isinstance(result, SessionStartResult)
        assert result.status == "success"
        assert result.brief is not None
        assert result.brief.last_handoff is not None
        assert result.brief.last_handoff.session_id == "2026-02-20T17-00"
        assert len(result.brief.last_handoff.completed_tasks) == 2
        assert "Phase 50 Step 1" in result.brief.last_handoff.completed_tasks
        assert "Phase 50 Step 2" in result.brief.last_handoff.completed_tasks
        assert result.brief.last_handoff.next_actions == ["Complete Phase 54"]

    @pytest.mark.asyncio
    async def test_session_start_impl_handoff_none_when_missing(
        self, tmp_path: Path
    ) -> None:
        """Test that session_start returns None handoff when file doesn't exist."""
        active_context_content = """# Active Context

## Current Focus

Working on Phase 54.
"""
        _memory_bank_dir, managers = await managers_phase54_variant(
            tmp_path,
            active_context=active_context_content,
            roadmap=ROADMAP_PHASE54_PENDING,
        )
        result = await run_session_start_patched_mcp_healthy(tmp_path, managers)
        assert isinstance(result, SessionStartResult)
        assert result.status == "success"
        assert result.brief is not None
        assert result.brief.last_handoff is None

    @pytest.mark.asyncio
    async def test_session_start_impl_includes_gate_feedback_summary(
        self, tmp_path: Path
    ) -> None:
        """session_start surfaces active gate_feedback summary from handoff state."""
        managers = await build_minimal_session_managers(tmp_path)

        with (
            patch(
                "cortex.tools.session.health.get_mcp_health_status",
                new_callable=AsyncMock,
                return_value=(True, None),
            ),
            patch(
                "cortex.tools.session.pipeline_handoff.pipeline_handoff",
                new_callable=AsyncMock,
                return_value=json.dumps(
                    {
                        "summary": "Quality gate failed with 2 issue group(s).",
                        "top_files": ["src/a.py", "tests/b.py"],
                    }
                ),
            ),
        ):
            result = await session_start_impl(None, tmp_path, managers)  # type: ignore[arg-type]

        assert isinstance(result, SessionStartResult)
        assert result.status == "success"
        assert result.brief.gate_feedback_summary is not None
        assert (
            "Quality gate failed with 2 issue group(s)."
            in result.brief.gate_feedback_summary
        )
        assert "Top files: src/a.py, tests/b.py" in result.brief.gate_feedback_summary

    @pytest.mark.asyncio
    async def test_session_start_impl_includes_clarification_summary(
        self, tmp_path: Path
    ) -> None:
        """session_start surfaces unresolved clarification counts from active plans."""
        managers = await build_minimal_session_managers(tmp_path)
        plans_dir = get_cortex_path(tmp_path, CortexResourceType.PLANS)
        plans_dir.mkdir(parents=True, exist_ok=True)
        _ = (plans_dir / "clarify.md").write_text(
            "status: IN_PROGRESS\n\n"
            + "[NEEDS CLARIFICATION: api shape]\n"
            + "[NEEDS CLARIFICATION(blocking): auth mode]\n",
            encoding="utf-8",
        )
        with patch(
            "cortex.tools.session.health.get_mcp_health_status",
            new_callable=AsyncMock,
            return_value=(True, None),
        ):
            result = await session_start_impl(None, tmp_path, managers)  # type: ignore[arg-type]
        assert isinstance(result, SessionStartResult)
        assert result.status == "success"
        assert result.brief.clarification_summary is not None
        assert "1 plans have unresolved clarifications (1 blocking)." in (
            result.brief.clarification_summary
        )

    @pytest.mark.asyncio
    async def test_session_lifecycle_compact_then_session_start_sees_handoff(
        self, tmp_path: Path
    ) -> None:
        """Integration: compact_session then session_start returns handoff in brief."""
        managers = await managers_after_compact_lifecycle(tmp_path)
        with patch(
            "cortex.tools.session.health.get_mcp_health_status",
            new_callable=AsyncMock,
            return_value=(True, None),
        ):
            result = await session_start_impl(
                None,
                tmp_path,
                managers,  # type: ignore[arg-type]
            )
        assert isinstance(result, SessionStartResult)
        assert result.status == "success"
        assert result.brief is not None
        assert result.brief.last_handoff is not None
        assert "Lifecycle integration test" in result.brief.last_handoff.next_actions

    @pytest.mark.asyncio
    async def test_session_start_impl_mcp_unhealthy(self, tmp_path: Path) -> None:
        """Test session start when MCP health check returns unhealthy."""
        managers = await minimal_session_managers_custom_roadmap(
            tmp_path,
            roadmap="# Roadmap\n\n## Pending\n\n- **Task** - PENDING\n",
        )
        with patch(
            "cortex.tools.session.health.get_mcp_health_status",
            new_callable=AsyncMock,
            return_value=(False, "MCP connection unhealthy"),
        ):
            result = await session_start_impl(None, tmp_path, managers)  # type: ignore[arg-type]
        assert isinstance(result, SessionStartResult)
        assert result.brief.mcp_healthy is False
        assert result.brief.mcp_health_message == "MCP connection unhealthy"
        assert any(
            "do not proceed without mcp" in s.lower()
            for s in result.brief.session_suggestions
        )

    @pytest.mark.asyncio
    async def test_session_start_impl_missing_active_context(
        self, tmp_path: Path
    ) -> None:
        """Test session start when activeContext.md is missing."""
        memory_bank_dir = ensure_test_cortex_structure(tmp_path)
        _ = (memory_bank_dir / "roadmap.md").write_text("# Roadmap")

        fs_manager = FileSystemManager(tmp_path)
        managers = make_test_managers(fs=fs_manager)

        with patch(
            "cortex.tools.session.health.get_mcp_health_status",
            new_callable=AsyncMock,
            return_value=(True, None),
        ):
            result = await session_start_impl(None, tmp_path, managers)  # type: ignore[arg-type]

        assert isinstance(result, SessionStartErrorResult)
        assert result.status == "error"
        assert "activeContext.md" in result.error

    @pytest.mark.asyncio
    async def test_session_start_impl_missing_roadmap(self, tmp_path: Path) -> None:
        """Test session start when roadmap.md is missing."""
        memory_bank_dir = ensure_test_cortex_structure(tmp_path)
        _ = (memory_bank_dir / "activeContext.md").write_text("# Active Context")

        fs_manager = FileSystemManager(tmp_path)
        managers = make_test_managers(fs=fs_manager)

        with patch(
            "cortex.tools.session.health.get_mcp_health_status",
            new_callable=AsyncMock,
            return_value=(True, None),
        ):
            result = await session_start_impl(None, tmp_path, managers)  # type: ignore[arg-type]

        assert isinstance(result, SessionStartErrorResult)
        assert result.status == "error"
        assert "roadmap.md" in result.error

    @pytest.mark.asyncio
    async def test_session_start_impl_exception_handling(self, tmp_path: Path) -> None:
        """Test session start handles exceptions gracefully."""
        memory_bank_dir = ensure_test_cortex_structure(tmp_path)
        _ = (memory_bank_dir / "activeContext.md").write_text("# Active Context")
        _ = (memory_bank_dir / "roadmap.md").write_text("# Roadmap")

        # Create a mock fs_manager that raises an exception
        fs_manager = MagicMock(spec=FileSystemManager)
        fs_manager.memory_bank_dir = memory_bank_dir
        fs_manager.read_file = AsyncMock(side_effect=Exception("Test error"))

        managers = make_test_managers(fs=fs_manager)

        with patch(
            "cortex.tools.session.health.get_mcp_health_status",
            new_callable=AsyncMock,
            return_value=(True, None),
        ):
            result = await session_start_impl(None, tmp_path, managers)  # type: ignore[arg-type]

        assert isinstance(result, SessionStartErrorResult)
        assert result.status == "error"
        assert "Failed to generate session brief" in result.error
