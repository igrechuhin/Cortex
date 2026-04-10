"""Tests for session goal models, drift detection, and plan path extraction."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cortex.core.drift_detector import check_drift
from cortex.core.plan_path_extract import extract_file_patterns_from_plan
from cortex.core.session_goal_builder import build_session_goal, resolve_plan_file
from cortex.core.session_goal_models import SessionGoal
from cortex.core.session_goal_store import (
    delete_session_goal,
    read_session_goal,
    session_goal_path,
    write_session_goal,
)


def test_session_goal_roundtrip(tmp_path: Path) -> None:
    sg = SessionGoal(
        goal="Implement feature X", plan_slug="p.md", allowed_files=["src/**"]
    )
    write_session_goal(tmp_path, sg)
    path = session_goal_path(tmp_path)
    assert path.is_file()
    loaded = read_session_goal(tmp_path)
    assert loaded is not None
    assert loaded.goal == "Implement feature X"
    assert loaded.allowed_files == ["src/**"]


def test_check_drift_allowed_pattern() -> None:
    g = SessionGoal(
        goal="work on cortex",
        plan_slug=None,
        allowed_files=["src/cortex/core/*.py"],
        blocked_files=[],
    )
    r = check_drift("src/cortex/core/foo.py", g)
    assert r.drifted is False
    assert r.allowed is True


def test_check_drift_blocked() -> None:
    g = SessionGoal(
        goal="work",
        plan_slug=None,
        allowed_files=["src/safe/**"],
        blocked_files=["**/secrets/**"],
    )
    r = check_drift("src/secrets/key.pem", g)
    assert r.drifted is True
    assert "blocked" in r.reason.lower()


def test_extract_file_patterns_from_plan() -> None:
    text = "See `src/cortex/tools/session.py` and tests/test_x.py."
    got = extract_file_patterns_from_plan(text)
    assert "src/cortex/tools/session.py" in got


def test_resolve_plan_file(tmp_path: Path) -> None:
    plans = tmp_path / ".cortex" / "plans"
    plans.mkdir(parents=True)
    p = plans / "my-plan.md"
    _ = p.write_text("hello", encoding="utf-8")
    assert resolve_plan_file(tmp_path, "my-plan.md") == p
    assert resolve_plan_file(tmp_path, "my-plan") == p


def test_build_session_goal_populates_allowed(tmp_path: Path) -> None:
    plans = tmp_path / ".cortex" / "plans"
    plans.mkdir(parents=True)
    plan = plans / "t.md"
    _ = plan.write_text("Edit `src/foo.py` for logic.\n", encoding="utf-8")
    sg = build_session_goal("Do the thing", "t.md", tmp_path)
    assert "src/foo.py" in sg.allowed_files


def test_session_goal_json_serializable() -> None:
    sg = SessionGoal(goal="g", plan_slug=None)
    raw = sg.model_dump_json()
    data = json.loads(raw)
    assert data["goal"] == "g"


# ---------------------------------------------------------------------------
# check_drift — additional branches
# ---------------------------------------------------------------------------


def test_check_drift_similarity_unrelated() -> None:
    """Path with no relation to goal and non-empty allowed_files → drifted via similarity."""
    g = SessionGoal(
        goal="implement session goal anchoring",
        plan_slug="session-goal-anchoring",
        allowed_files=["src/cortex/core/session_goal*.py"],
    )
    result = check_drift("docs/unrelated_readme.md", g)
    assert result.drifted is True
    assert result.allowed is False


def test_check_drift_empty_allowed_files_flags_all() -> None:
    """Empty allowed_files means every path is potential drift (plan spec)."""
    g = SessionGoal(
        goal="fix the auth bug",
        plan_slug=None,
        allowed_files=[],
        blocked_files=[],
    )
    result = check_drift("src/cortex/core/foo.py", g)
    assert result.drifted is True
    assert "no allowed_files" in result.reason


def test_check_drift_blocked_overrides_allowed() -> None:
    """blocked_files wins even when path would match allowed_files first (no-match case)."""
    g = SessionGoal(
        goal="work on cortex",
        plan_slug=None,
        allowed_files=["src/cortex/**"],
        blocked_files=["src/cortex/secrets/**"],
    )
    # This path doesn't match allowed_files (pattern is src/cortex/**
    # but PurePosixPath.match checks suffix), so blocked check fires.
    result = check_drift("src/cortex/secrets/key.pem", g)
    assert result.drifted is True
    assert "blocked" in result.reason


# ---------------------------------------------------------------------------
# delete_session_goal
# ---------------------------------------------------------------------------


def test_delete_session_goal_returns_true_when_file_exists(tmp_path: Path) -> None:
    sg = SessionGoal(goal="delete me", plan_slug=None)
    write_session_goal(tmp_path, sg)
    assert session_goal_path(tmp_path).is_file()
    removed = delete_session_goal(tmp_path)
    assert removed is True
    assert not session_goal_path(tmp_path).exists()


def test_delete_session_goal_returns_false_when_absent(tmp_path: Path) -> None:
    removed = delete_session_goal(tmp_path)
    assert removed is False


# ---------------------------------------------------------------------------
# merge_session_goal_into_brief
# ---------------------------------------------------------------------------


def _make_minimal_brief() -> object:
    """Return a minimal SessionBrief-like object for merge tests."""
    from cortex.tools.session.models import (
        SessionBrief,
        SessionHealthSummary,
        TokenBudgetStatus,
    )

    health = SessionHealthSummary(
        file_count=0,
        total_tokens=0,
        token_budget_status=TokenBudgetStatus.HEALTHY,
    )
    return SessionBrief(
        project_name="test",
        health=health,
        next_work_item=None,
        next_work_plan_path=None,
        git_status=None,
        last_handoff=None,
    )


def test_merge_session_goal_into_brief_write_branch(tmp_path: Path) -> None:
    from cortex.tools.session.session_goal_brief import merge_session_goal_into_brief

    brief = _make_minimal_brief()
    with patch("cortex.tools.session.session_goal_brief._invalidate_context_cache"):
        updated = merge_session_goal_into_brief(
            brief,  # type: ignore[arg-type]
            tmp_path,
            goal="Fix the login bug",
            plan_slug=None,
            blocked_files=None,
        )
    assert updated.primary_session_goal == "Fix the login bug"
    assert updated.session_goal_drift_hint is not None
    assert "Drift detection active" in updated.session_goal_drift_hint
    assert session_goal_path(tmp_path).is_file()


def test_merge_session_goal_into_brief_resume_branch(tmp_path: Path) -> None:
    from cortex.tools.session.session_goal_brief import merge_session_goal_into_brief

    sg = SessionGoal(goal="Resumed goal", plan_slug=None)
    write_session_goal(tmp_path, sg)

    brief = _make_minimal_brief()
    with patch("cortex.tools.session.session_goal_brief._invalidate_context_cache"):
        updated = merge_session_goal_into_brief(
            brief,  # type: ignore[arg-type]
            tmp_path,
            goal=None,
            plan_slug=None,
            blocked_files=None,
        )
    assert updated.primary_session_goal == "Resumed goal"
    assert updated.session_goal_drift_hint is not None
    assert "resumed" in updated.session_goal_drift_hint.lower()


def test_merge_session_goal_into_brief_no_goal_branch(tmp_path: Path) -> None:
    from cortex.tools.session.session_goal_brief import merge_session_goal_into_brief

    brief = _make_minimal_brief()
    updated = merge_session_goal_into_brief(
        brief,  # type: ignore[arg-type]
        tmp_path,
        goal=None,
        plan_slug=None,
        blocked_files=None,
    )
    assert updated.primary_session_goal is None
    assert updated.session_goal_drift_hint is not None
    assert "No session goal set" in updated.session_goal_drift_hint


# ---------------------------------------------------------------------------
# execute_session_goal_operation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_set_goal(tmp_path: Path) -> None:
    from cortex.tools.files.operation_helpers import FileOperation
    from cortex.tools.files.session_goal_file_ops import execute_session_goal_operation

    managers: MagicMock = MagicMock()
    content = json.dumps({"goal": "Implement feature Y", "plan_slug": None})
    with patch("cortex.tools.files.session_goal_file_ops._invalidate_context_cache"):
        result = await execute_session_goal_operation(
            tmp_path, FileOperation.SET_GOAL, content, managers
        )
    data = json.loads(result)
    assert data["status"] == "success"
    assert data["operation"] == "set_goal"
    assert data["session_goal"]["goal"] == "Implement feature Y"
    assert session_goal_path(tmp_path).is_file()


@pytest.mark.asyncio
async def test_execute_get_goal_present(tmp_path: Path) -> None:
    from cortex.tools.files.operation_helpers import FileOperation
    from cortex.tools.files.session_goal_file_ops import execute_session_goal_operation

    sg = SessionGoal(goal="Get me", plan_slug=None)
    write_session_goal(tmp_path, sg)
    managers: MagicMock = MagicMock()
    result = await execute_session_goal_operation(
        tmp_path, FileOperation.GET_GOAL, None, managers
    )
    data = json.loads(result)
    assert data["status"] == "success"
    assert data["session_goal"]["goal"] == "Get me"


@pytest.mark.asyncio
async def test_execute_get_goal_absent(tmp_path: Path) -> None:
    from cortex.tools.files.operation_helpers import FileOperation
    from cortex.tools.files.session_goal_file_ops import execute_session_goal_operation

    managers: MagicMock = MagicMock()
    result = await execute_session_goal_operation(
        tmp_path, FileOperation.GET_GOAL, None, managers
    )
    data = json.loads(result)
    assert data["status"] == "success"
    assert data["session_goal"] is None


@pytest.mark.asyncio
async def test_execute_clear_goal(tmp_path: Path) -> None:
    from cortex.tools.files.operation_helpers import FileOperation
    from cortex.tools.files.session_goal_file_ops import execute_session_goal_operation

    sg = SessionGoal(goal="Clear me", plan_slug=None)
    write_session_goal(tmp_path, sg)
    managers: MagicMock = MagicMock()
    with patch("cortex.tools.files.session_goal_file_ops._invalidate_context_cache"):
        result = await execute_session_goal_operation(
            tmp_path, FileOperation.CLEAR_GOAL, None, managers
        )
    data = json.loads(result)
    assert data["status"] == "success"
    assert data["removed"] is True
    assert not session_goal_path(tmp_path).exists()


@pytest.mark.asyncio
async def test_execute_set_goal_missing_content(tmp_path: Path) -> None:
    from cortex.tools.files.operation_helpers import FileOperation
    from cortex.tools.files.session_goal_file_ops import execute_session_goal_operation

    managers: MagicMock = MagicMock()
    result = await execute_session_goal_operation(
        tmp_path, FileOperation.SET_GOAL, None, managers
    )
    data = json.loads(result)
    assert data["status"] == "error"


# ---------------------------------------------------------------------------
# append_session_goal_to_context_payload
# ---------------------------------------------------------------------------


def test_append_session_goal_to_context_injects_goal(tmp_path: Path) -> None:
    from cortex.tools.optimization.handlers import (
        append_session_goal_to_context_payload,
    )

    sg = SessionGoal(goal="Context goal", plan_slug=None)
    write_session_goal(tmp_path, sg)

    payload = json.dumps({"status": "success", "data": "some context"})
    result = append_session_goal_to_context_payload(payload, tmp_path)
    data = json.loads(result)
    assert "session_goal" in data
    assert data["session_goal"]["goal"] == "Context goal"


def test_append_session_goal_to_context_absent(tmp_path: Path) -> None:
    from cortex.tools.optimization.handlers import (
        append_session_goal_to_context_payload,
    )

    payload = json.dumps({"status": "success", "data": "no goal"})
    result = append_session_goal_to_context_payload(payload, tmp_path)
    data = json.loads(result)
    assert "session_goal" not in data


def test_append_session_goal_to_context_non_success_passthrough(
    tmp_path: Path,
) -> None:
    from cortex.tools.optimization.handlers import (
        append_session_goal_to_context_payload,
    )

    sg = SessionGoal(goal="Should not appear", plan_slug=None)
    write_session_goal(tmp_path, sg)

    payload = json.dumps({"status": "error", "error": "something failed"})
    result = append_session_goal_to_context_payload(payload, tmp_path)
    data = json.loads(result)
    assert "session_goal" not in data


# ---------------------------------------------------------------------------
# build_session_drift_summary
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_session_drift_summary_no_goal(tmp_path: Path) -> None:
    from cortex.tools.session.session_drift_report import build_session_drift_summary

    result = await build_session_drift_summary(tmp_path)
    assert result is None


@pytest.mark.asyncio
async def test_build_session_drift_summary_no_changed_files(tmp_path: Path) -> None:
    from cortex.tools.session.session_drift_report import build_session_drift_summary

    sg = SessionGoal(
        goal="test", plan_slug=None, allowed_files=["src/**"], blocked_files=[]
    )
    write_session_goal(tmp_path, sg)

    mock_result = MagicMock()
    mock_result.success = True
    mock_result.stdout = ""

    with (
        patch(
            "cortex.tools.session.session_drift_report.run_git_command",
            new=AsyncMock(return_value=mock_result),
        ),
        patch(
            "cortex.tools.session.session_drift_report.acquire_git_operation_slot",
            new=AsyncMock(),
        ),
    ):
        result = await build_session_drift_summary(tmp_path)

    assert result is not None
    assert result["files_touched"] == 0
    assert result["high_drift_warning"] is False


@pytest.mark.asyncio
async def test_build_session_drift_summary_with_in_scope_files(
    tmp_path: Path,
) -> None:
    from cortex.tools.session.session_drift_report import build_session_drift_summary

    sg = SessionGoal(
        goal="test", plan_slug=None, allowed_files=["src/cortex/core/*.py"]
    )
    write_session_goal(tmp_path, sg)

    tracked = MagicMock()
    tracked.success = True
    tracked.stdout = "src/cortex/core/foo.py\n"
    untracked = MagicMock()
    untracked.success = True
    untracked.stdout = ""

    with (
        patch(
            "cortex.tools.session.session_drift_report.run_git_command",
            new=AsyncMock(side_effect=[tracked, untracked]),
        ),
        patch(
            "cortex.tools.session.session_drift_report.acquire_git_operation_slot",
            new=AsyncMock(),
        ),
    ):
        result = await build_session_drift_summary(tmp_path)

    assert result is not None
    assert result["files_touched"] == 1
    assert result["in_scope"] == 1
    assert result["out_of_scope"] == 0
    assert result["high_drift_warning"] is False


def _high_drift_git_results() -> tuple[MagicMock, MagicMock]:
    tracked = MagicMock()
    tracked.success = True
    tracked.stdout = (
        "src/cortex/core/one_file.py\n"
        "docs/unrelated1.md\n"
        "docs/unrelated2.md\n"
        "tests/unrelated3.py\n"
        "README.md\n"
    )
    untracked = MagicMock()
    untracked.success = True
    untracked.stdout = ""
    return tracked, untracked


@pytest.mark.asyncio
async def test_build_session_drift_summary_high_drift(tmp_path: Path) -> None:
    from cortex.tools.session.session_drift_report import build_session_drift_summary

    sg = SessionGoal(
        goal="tiny scoped task",
        plan_slug=None,
        allowed_files=["src/cortex/core/one_file.py"],
    )
    write_session_goal(tmp_path, sg)

    tracked, untracked = _high_drift_git_results()

    with (
        patch(
            "cortex.tools.session.session_drift_report.run_git_command",
            new=AsyncMock(side_effect=[tracked, untracked]),
        ),
        patch(
            "cortex.tools.session.session_drift_report.acquire_git_operation_slot",
            new=AsyncMock(),
        ),
    ):
        result = await build_session_drift_summary(tmp_path)

    assert result is not None
    assert result["high_drift_warning"] is True
    assert "high_drift_message" in result


@pytest.mark.asyncio
async def test_build_session_drift_summary_git_failure(tmp_path: Path) -> None:
    from cortex.tools.session.session_drift_report import build_session_drift_summary

    sg = SessionGoal(goal="test", plan_slug=None, allowed_files=["src/**"])
    write_session_goal(tmp_path, sg)

    with patch(
        "cortex.tools.session.session_drift_report.acquire_git_operation_slot",
        new=AsyncMock(side_effect=RuntimeError("git unavailable")),
    ):
        result = await build_session_drift_summary(tmp_path)

    assert result is not None
    assert result["files_touched"] == 0
    assert "note" in result


# ---------------------------------------------------------------------------
# compact_attach_session_drift_json — drift_summary surface
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compact_attach_drift_summary_key(tmp_path: Path) -> None:
    from cortex.tools.memory.compaction_write_helpers import (
        compact_attach_session_drift_json,
    )

    sg = SessionGoal(goal="ship it", plan_slug=None, allowed_files=["src/**"])
    write_session_goal(tmp_path, sg)

    success_json = json.dumps({"status": "success", "message": "compacted"})

    mock_drift: dict[str, object] = {
        "files_touched": 3,
        "in_scope": 2,
        "out_of_scope": 1,
        "drift_rate": 0.33,
        "high_drift_warning": False,
        "summary_line": "Session touched 3 files: 2 in scope, 1 out of scope (drift).",
        "goal_session_id": sg.session_id,
    }

    with patch(
        "cortex.tools.session.session_drift_report.build_session_drift_summary_safe",
        new=AsyncMock(return_value=mock_drift),
    ):
        result = await compact_attach_session_drift_json(success_json, tmp_path)

    data = json.loads(result)
    assert "session_drift" in data
    assert "drift_summary" in data
    assert "3 files" in data["drift_summary"]


@pytest.mark.asyncio
async def test_compact_attach_drift_summary_high_drift_message(
    tmp_path: Path,
) -> None:
    from cortex.tools.memory.compaction_write_helpers import (
        compact_attach_session_drift_json,
    )

    sg = SessionGoal(goal="x", plan_slug=None, allowed_files=["src/**"])
    write_session_goal(tmp_path, sg)

    success_json = json.dumps({"status": "success"})
    mock_drift: dict[str, object] = {
        "files_touched": 5,
        "in_scope": 1,
        "out_of_scope": 4,
        "drift_rate": 0.8,
        "high_drift_warning": True,
        "summary_line": "Session touched 5 files: 1 in scope, 4 out of scope (drift).",
        "high_drift_message": "High drift detected. Consider splitting into focused sessions.",
        "goal_session_id": sg.session_id,
    }

    with patch(
        "cortex.tools.session.session_drift_report.build_session_drift_summary_safe",
        new=AsyncMock(return_value=mock_drift),
    ):
        result = await compact_attach_session_drift_json(success_json, tmp_path)

    data = json.loads(result)
    assert "High drift detected" in data["drift_summary"]


@pytest.mark.asyncio
async def test_compact_attach_no_drift_when_no_goal(tmp_path: Path) -> None:
    from cortex.tools.memory.compaction_write_helpers import (
        compact_attach_session_drift_json,
    )

    success_json = json.dumps({"status": "success"})

    with patch(
        "cortex.tools.session.session_drift_report.build_session_drift_summary_safe",
        new=AsyncMock(return_value=None),
    ):
        result = await compact_attach_session_drift_json(success_json, tmp_path)

    data = json.loads(result)
    assert "session_drift" not in data
    assert "drift_summary" not in data
