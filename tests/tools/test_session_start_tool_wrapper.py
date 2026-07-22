"""Tests for session_start tool wrapper and brief payload capping."""

import json
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, patch

import pytest

from cortex.tools.models import SessionHealthSummary
from cortex.tools.session.brief import cap_session_brief_payload
from cortex.tools.session.models import (
    ConcurrentSession,
    SessionBrief,
    TokenBudgetStatus,
)
from cortex.tools.session.start_tools import session_start
from tests.helpers.tool_call_helpers import get_tool_fn
from tests.tools.session_start_fixtures import (
    ROADMAP_PHASE54_TOOL,
    managers_phase54_variant,
)


class TestSessionStartTool:
    """Tests for session_start tool wrapper."""

    @pytest.mark.asyncio
    async def test_session_start_success(self, tmp_path: Path) -> None:
        """Test successful session_start tool call."""
        _mb, managers = await managers_phase54_variant(
            tmp_path,
            active_context="# Active Context\n\n## Current Focus\n\nWorking on Phase 54.\n",
            roadmap=ROADMAP_PHASE54_TOOL,
            extra_content="",
        )

        with (
            patch(
                "cortex.tools.session.start_tools.get_or_resolve_project_root"
            ) as mock_root,
            patch(
                "cortex.tools.session.start_tools.get_current_managers"
            ) as mock_managers,
            patch(
                "cortex.tools.session.health.get_mcp_health_status",
                new_callable=AsyncMock,
                return_value=(True, None),
            ),
        ):
            mock_root.return_value = tmp_path
            mock_managers.return_value = managers

            tool_fn = get_tool_fn(session_start)
            result_json = await tool_fn(task_description=None, ctx=None)
            assert isinstance(result_json, str)
            result = json.loads(result_json)

            assert result["status"] == "success"
            assert "brief" in result
            assert result["token_count"] > 0

    @pytest.mark.asyncio
    async def test_session_start_no_managers(self) -> None:
        """Test session_start when managers are not initialized."""
        with (
            patch(
                "cortex.tools.session.start_tools.get_or_resolve_project_root"
            ) as mock_root,
            patch(
                "cortex.tools.session.start_tools.get_current_managers"
            ) as mock_managers,
        ):
            mock_root.return_value = Path("/tmp/test")
            mock_managers.return_value = None

            tool_fn = get_tool_fn(session_start)
            result_json = await tool_fn(task_description=None, ctx=None)
            assert isinstance(result_json, str)
            result = json.loads(result_json)

            assert result["status"] == "error"
            assert "Managers not initialized" in result["error"]


async def _run_session_start_json(
    tmp_path: Path, managers: object
) -> dict[str, object]:
    with (
        patch(
            "cortex.tools.session.start_tools.get_or_resolve_project_root"
        ) as mock_root,
        patch("cortex.tools.session.start_tools.get_current_managers") as mock_managers,
        patch(
            "cortex.tools.session.health.get_mcp_health_status",
            new_callable=AsyncMock,
            return_value=(True, None),
        ),
    ):
        mock_root.return_value = tmp_path
        mock_managers.return_value = managers
        tool_fn = get_tool_fn(session_start)
        result_json = await tool_fn(task_description=None, ctx=None)
        assert isinstance(result_json, str)
        parsed: dict[str, object] = json.loads(result_json)
        return parsed


@pytest.mark.asyncio
async def test_session_start_recall_disabled_omits_summary_key(tmp_path: Path) -> None:
    """No experience store and recall disabled: brief has no recall key at all."""
    from cortex.core.path_resolver import CortexResourceType, get_cortex_path
    from cortex.core.project_session_config import project_session_config_path

    _mb, managers = await managers_phase54_variant(
        tmp_path,
        active_context="# Active Context\n\n## Current Focus\n\nWorking on Phase 54.\n",
        roadmap=ROADMAP_PHASE54_TOOL,
        extra_content="",
    )
    cortex_dir = get_cortex_path(tmp_path, CortexResourceType.CORTEX_DIR)
    cortex_dir.mkdir(parents=True, exist_ok=True)
    _ = project_session_config_path(tmp_path).write_text(
        "experience_recall_enabled: false\n", encoding="utf-8"
    )

    result = await _run_session_start_json(tmp_path, managers)

    assert result["status"] == "success"
    brief = cast(dict[str, object], result["brief"])
    assert "experience_recall_summary" not in brief


def test_cap_session_brief_payload_truncates_long_concurrent_task() -> None:
    """Long concurrent session task strings are capped for stable MCP JSON."""
    long_task = "x" * 3000
    brief = SessionBrief(
        project_name="Proj",
        current_focus="",
        recent_completed=[],
        next_work_item=None,
        next_work_plan_path=None,
        health=SessionHealthSummary(
            file_count=1,
            total_tokens=1,
            token_budget_status=TokenBudgetStatus.HEALTHY,
        ),
        git_status=None,
        session_suggestions=[],
        last_handoff=None,
        concurrent_sessions=[
            ConcurrentSession(
                agent_role=None,
                task=long_task,
                started="2020-01-01T00:00:00+00:00",
                session_id="sid",
            )
        ],
        locked_tasks=[],
        mcp_healthy=True,
        mcp_health_message=None,
    )
    capped = cap_session_brief_payload(brief)
    assert len(capped.concurrent_sessions[0].task) < len(long_task)
    assert capped.concurrent_sessions[0].task.endswith("…")
