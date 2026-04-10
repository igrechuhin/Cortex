"""Non-blocking drift detection: compare edited paths to session goal patterns."""

from __future__ import annotations

from difflib import SequenceMatcher
from pathlib import PurePosixPath

from cortex.core.session_goal_models import DriftResult, SessionGoal


def _path_matches_any(path_norm: str, patterns: list[str]) -> bool:
    for pat in patterns:
        if not pat.strip():
            continue
        p = pat.replace("\\", "/").strip()
        try:
            if PurePosixPath(path_norm).match(p):
                return True
        except ValueError:
            continue
    return False


def _similarity_score(path_norm: str, goal: SessionGoal) -> float:
    """Heuristic 0..1 similarity between path and goal metadata."""
    pn = path_norm.lower()
    best = 0.0
    anchors: list[str] = [goal.goal.lower()]
    if goal.plan_slug:
        anchors.append(goal.plan_slug.lower())
    for a in goal.allowed_files:
        anchors.append(a.lower())
    for anchor in anchors:
        if not anchor:
            continue
        best = max(best, SequenceMatcher(None, pn, anchor).ratio())
    for segment in pn.split("/"):
        if len(segment) < 2:
            continue
        for anchor in anchors:
            if anchor:
                best = max(best, SequenceMatcher(None, segment, anchor).ratio())
    return best


def _empty_path_result() -> DriftResult:
    return DriftResult(
        drifted=True,
        reason="empty path",
        allowed=False,
    )


def _blocked_or_missing_scope_result(
    path_norm: str, goal: SessionGoal
) -> DriftResult | None:
    if _path_matches_any(path_norm, goal.blocked_files):
        return DriftResult(
            drifted=True,
            reason="explicitly blocked",
            allowed=False,
        )
    if not goal.allowed_files:
        return DriftResult(
            drifted=True,
            reason="no allowed_files defined — all paths are potential drift",
            allowed=False,
        )
    return None


def _result_from_similarity(path_norm: str, goal: SessionGoal) -> DriftResult:
    sim = _similarity_score(path_norm, goal)
    if sim < 0.5:
        return DriftResult(
            drifted=True,
            reason="unrelated to goal",
            allowed=False,
        )
    return DriftResult(
        drifted=False,
        reason="weak association (similarity above threshold)",
        allowed=False,
    )


def check_drift(file_path: str, goal: SessionGoal) -> DriftResult:
    """Classify whether file_path is in scope for the given goal (warning-only)."""
    path_norm = file_path.replace("\\", "/").strip()
    if not path_norm:
        return _empty_path_result()

    if _path_matches_any(path_norm, goal.allowed_files):
        return DriftResult(drifted=False, reason="matches allowed_files", allowed=True)

    blocked_or_missing = _blocked_or_missing_scope_result(path_norm, goal)
    if blocked_or_missing is not None:
        return blocked_or_missing
    return _result_from_similarity(path_norm, goal)
