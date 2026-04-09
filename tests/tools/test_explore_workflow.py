"""Tests for /cortex/explore workflow wiring."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, patch

import pytest

from cortex.core.models import (
    ExploreComplexity,
    ExploreOption,
    ExploreSession,
    RiskLevel,
)
from cortex.tools.files.operations import manage_file
from cortex.tools.optimization.handlers import load_context
from cortex.tools.plans.crud import create_plan
from cortex.tools.session.brief_extraction_helpers import generate_session_suggestions
from cortex.tools.session.models import SessionHealthSummary, TokenBudgetStatus
from tests.helpers.path_helpers import ensure_test_cortex_structure
from tests.helpers.tool_call_helpers import get_tool_fn


def _seed_explore_logs(tmp_path: Path) -> None:
    explore_dir = tmp_path / ".cortex" / "plans" / "explore"
    explore_dir.mkdir(parents=True, exist_ok=True)
    old_log = explore_dir / "decision-log-old.md"
    fresh_log = explore_dir / "decision-log-fresh.md"
    _ = old_log.write_text("# old\n", encoding="utf-8")
    _ = fresh_log.write_text("# fresh\n", encoding="utf-8")
    old_time = time.time() - (9 * 24 * 60 * 60)
    os.utime(old_log, (old_time, old_time))


async def _call_manage_file_json(operation: str) -> dict[str, object]:
    return json.loads(
        await manage_file(file_name="activeContext.md", operation=operation)
    )


def test_explore_models_validation_round_trip() -> None:
    """Explore models validate and keep enum values."""
    option = ExploreOption(
        title="Keep current architecture",
        description="Smallest migration risk",
        pros=["Low disruption"],
        cons=["Limited improvement"],
        complexity=ExploreComplexity.LOW,
        risk=RiskLevel.LOW,
    )
    session = ExploreSession(
        topic="Exploration topic",
        options=[option],
        recommendation="Choose low-risk path",
        created=datetime.now(),
        decision=None,
    )
    assert session.options[0].complexity == ExploreComplexity.LOW
    assert session.options[0].risk == RiskLevel.LOW


@pytest.mark.asyncio
async def test_manage_file_lists_and_clears_explore_logs(tmp_path: Path) -> None:
    """manage_file exposes list_explore_logs and clear_explore_logs."""
    _ = ensure_test_cortex_structure(tmp_path)
    _seed_explore_logs(tmp_path)

    with patch(
        "cortex.tools.files.manage_file_helpers.get_or_resolve_project_root",
        new_callable=AsyncMock,
        return_value=tmp_path,
    ):
        listed = await _call_manage_file_json("list_explore_logs")
        assert listed["status"] == "success"
        assert listed["count"] == 2

        cleared = await _call_manage_file_json("clear_explore_logs")
        assert cleared["status"] == "success"
        assert cleared["count"] == 1
        deleted = cleared.get("deleted")
        assert isinstance(deleted, list) and deleted
        first_deleted = cast(str, deleted[0])
        assert "decision-log-old.md" in first_deleted

        listed_after = await _call_manage_file_json("list_explore_logs")
        assert listed_after["count"] == 1
        logs = listed_after.get("logs")
        assert isinstance(logs, list) and logs
        first_log = cast(str, logs[0])
        assert "decision-log-fresh.md" in first_log


@pytest.mark.asyncio
async def test_create_plan_with_explore_log_adds_decision_basis(tmp_path: Path) -> None:
    """create_plan prepends Decision Basis when explore_log_path is provided."""
    _ = ensure_test_cortex_structure(tmp_path)
    explore_dir = tmp_path / ".cortex" / "plans" / "explore"
    explore_dir.mkdir(parents=True, exist_ok=True)
    explore_log = explore_dir / "decision-log-abc.md"
    _ = explore_log.write_text(
        "# Explore\n\n## Recommendation\nUse Option B\n\n## Selected Option\nOption B\n",
        encoding="utf-8",
    )

    create_fn = get_tool_fn(create_plan)
    with patch(
        "cortex.tools.plans.crud.resolve_project_root_async",
        new_callable=AsyncMock,
        return_value=tmp_path,
    ):
        raw = await create_fn(
            operation="create",
            title="Plan with lineage",
            content="# Plan\n\ncontent",
            slug="plan-with-lineage",
            explore_log_path=".cortex/plans/explore/decision-log-abc.md",
            ctx=None,
        )
        result = json.loads(str(raw))
    assert result["status"] == "success"
    created = (tmp_path / ".cortex" / "plans" / "plan-with-lineage.md").read_text(
        encoding="utf-8"
    )
    assert "## Decision Basis" in created
    assert "Selected option: Option B" in created


@pytest.mark.asyncio
async def test_load_context_includes_explore_summary(tmp_path: Path) -> None:
    """Context resource includes explore summary when session config references log."""
    explore_log = tmp_path / ".cortex" / "plans" / "explore" / "decision-log-x.md"
    explore_log.parent.mkdir(parents=True, exist_ok=True)
    _ = explore_log.write_text(
        "# Explore\n\n## Recommendation\nUse C\n\n## Selected Option\nOption C\n",
        encoding="utf-8",
    )
    with (
        patch(
            "cortex.core.session_config.read_session_config",
            return_value={
                "task_description": "test",
                "token_budget": 1000,
                "explore_log_path": ".cortex/plans/explore/decision-log-x.md",
            },
        ),
        patch(
            "cortex.tools.optimization.handlers.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=tmp_path,
        ),
        patch(
            "cortex.tools.optimization.handlers.load_context_impl",
            new_callable=AsyncMock,
            return_value=json.dumps({"status": "success"}),
        ),
    ):
        payload = json.loads(await load_context())
    assert "explore_summary" in payload
    assert "Option C" in str(payload["explore_summary"])


def test_generate_session_suggestions_adds_explore_tip_without_next_work() -> None:
    """Session brief suggests /cortex/explore only when no active next item exists."""
    health = SessionHealthSummary(
        file_count=7,
        total_tokens=1000,
        token_budget_status=TokenBudgetStatus.HEALTHY,
        missing_files=[],
        has_errors=False,
    )
    suggestions = generate_session_suggestions(
        health, git_status=None, next_work_item=None
    )
    assert any("/cortex/explore" in item for item in suggestions)
