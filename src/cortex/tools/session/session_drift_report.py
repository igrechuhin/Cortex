"""End-of-session drift summary vs .cortex/.session/session-goal.md."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from cortex.core.drift_detector import check_drift
from cortex.core.security import acquire_git_operation_slot
from cortex.core.session_goal_models import SessionGoal
from cortex.core.session_goal_store import read_session_goal
from cortex.tools.session.start_tools import run_git_command

logger = logging.getLogger(__name__)


async def _git_changed_paths(project_root: Path) -> list[str]:
    """List paths differing from HEAD (tracked + untracked under repo)."""
    await acquire_git_operation_slot()
    tracked = await run_git_command(
        ["git", "diff", "--name-only", "HEAD"],
        cwd=project_root,
        timeout=30.0,
    )
    untracked = await run_git_command(
        ["git", "ls-files", "-o", "--exclude-standard"],
        cwd=project_root,
        timeout=30.0,
    )
    paths: list[str] = []
    if tracked.success and tracked.stdout.strip():
        paths.extend(
            line.strip() for line in tracked.stdout.splitlines() if line.strip()
        )
    if untracked.success and untracked.stdout.strip():
        paths.extend(
            line.strip() for line in untracked.stdout.splitlines() if line.strip()
        )
    seen: set[str] = set()
    out: list[str] = []
    for p in paths:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def _count_drift(paths: list[str], goal: SessionGoal) -> tuple[int, int]:
    in_scope = 0
    out_scope = 0
    for rel in paths:
        res = check_drift(rel, goal)
        if res.drifted:
            out_scope += 1
        else:
            in_scope += 1
    return in_scope, out_scope


def _drift_dict_nonpositive(
    goal: SessionGoal, note: str | None = None
) -> dict[str, object]:
    base: dict[str, object] = {
        "goal_session_id": goal.session_id,
        "files_touched": 0,
        "in_scope": 0,
        "out_of_scope": 0,
        "drift_rate": 0.0,
        "high_drift_warning": False,
    }
    if note:
        base["note"] = note
    else:
        base["summary_line"] = (
            "Session touched 0 files: 0 in scope, 0 out of scope (drift)."
        )
    return base


def _drift_dict_from_counts(
    goal: SessionGoal, paths: list[str], in_scope: int, out_scope: int
) -> dict[str, object]:
    n = len(paths)
    drift_rate = out_scope / n if n else 0.0
    high = drift_rate > 0.30
    summary_line = (
        f"Session touched {n} files: {in_scope} in scope, "
        f"{out_scope} out of scope (drift)."
    )
    out: dict[str, object] = {
        "goal_session_id": goal.session_id,
        "files_touched": n,
        "in_scope": in_scope,
        "out_of_scope": out_scope,
        "drift_rate": round(drift_rate, 4),
        "high_drift_warning": high,
        "summary_line": summary_line,
    }
    if high:
        out["high_drift_message"] = (
            "High drift detected. Consider splitting into focused sessions."
        )
    return out


async def build_session_drift_summary(project_root: Path) -> dict[str, object] | None:
    """Return drift stats for compact JSON, or None if no session goal."""
    goal = read_session_goal(project_root)
    if goal is None:
        return None
    try:
        paths = await _git_changed_paths(project_root)
    except Exception as e:
        logger.debug("Drift summary git listing failed: %s", e)
        return _drift_dict_nonpositive(goal, "Could not list git changes.")
    if not paths:
        return _drift_dict_nonpositive(goal)
    in_s, out_s = _count_drift(paths, goal)
    return _drift_dict_from_counts(goal, paths, in_s, out_s)


async def build_session_drift_summary_safe(
    project_root: Path,
) -> dict[str, object] | None:
    """Wrapper with overall timeout so compact never hangs."""
    try:
        async with asyncio.timeout(45.0):
            return await build_session_drift_summary(project_root)
    except TimeoutError:
        logger.warning("Session drift summary timed out")
        return None
    except Exception as e:
        logger.debug("Session drift summary failed: %s", e)
        return None
