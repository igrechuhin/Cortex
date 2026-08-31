"""Quality-gate result -> experience-store fitness attachment (best-effort).

Also the single choke point where open predictions are graded: every quality
gate is the "next frame" a recorded claim can be contradicted by, so grading
happens here rather than at a new call site.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from cortex.core.models import ModelDict
from cortex.experience.claim_grading import (
    frame_from_gate_result,
    grade_claims,
    verdict_counts,
)
from cortex.experience.predictions import (
    open_predictions,
    record_verdicts,
)
from cortex.experience.recorder import record_gate_fitness

logger = logging.getLogger(__name__)

_SUMMARY_KEYS: tuple[str, ...] = (
    "preflight_passed",
    "summary",
    "total_errors",
    "total_warnings",
)

NO_PREDICTIONS_NOTICE = (
    "No open predictions — this gate graded nothing. "
    'Record one first: session(operation="predict", '
    'prediction="gate clean; touches <path>", task_description="<why>").'
)


def gate_summary(result: ModelDict) -> str:
    """Compact JSON score summary (pass/fail + error counts) for the artifact."""
    return json.dumps({key: result.get(key) for key in _SUMMARY_KEYS if key in result})


def _changed_files(root: Path) -> frozenset[str] | None:
    """Working-tree + staged + untracked paths, project-relative; None if git fails."""
    from cortex.tools.execution.pre_commit_pipeline_quality import (
        collect_git_delta_files,
    )

    paths = collect_git_delta_files(root)
    if paths is None:
        return None
    relative: set[str] = set()
    for path in paths:
        try:
            relative.add(path.relative_to(root.resolve()).as_posix())
        except ValueError:
            relative.add(path.as_posix())
    return frozenset(relative)


def _grade_open_predictions(root: Path, session_id: str, result: ModelDict) -> str:
    """Grade and record open claims; return the notice for the gate response."""
    claims = open_predictions(root, session_id)
    if not claims:
        return NO_PREDICTIONS_NOTICE
    frame = frame_from_gate_result(result, _changed_files(root))
    verdicts = grade_claims(claims, frame)
    _ = record_verdicts(root, session_id, verdicts)
    counts = verdict_counts(verdicts)
    misses = [v.claim.raw for v in verdicts if v.verdict.value == "MISS"]
    notice = (
        f"Graded {len(verdicts)} claim(s): {counts['HIT']} HIT, "
        f"{counts['MISS']} MISS, {counts['UNGRADED']} UNGRADED."
    )
    return f"{notice} Missed: {'; '.join(misses)}" if misses else notice


def _grade_predictions_safe(root: Path, session_id: str, result: ModelDict) -> None:
    """Never let grading disturb the gate result."""
    try:
        result["predictions"] = _grade_open_predictions(root, session_id, result)
    except Exception as exc:  # noqa: BLE001
        logger.warning("prediction grading failed (best-effort): %s", exc)


async def record_gate_result(
    root: Path, result: ModelDict, pipeline: str = "commit"
) -> str | None:
    """Attach the gate outcome as node fitness. Never raises past the recorder."""
    # AI: imported lazily to keep experience/ free of session-tool import cycles.
    from cortex.tools.session.pipeline_handoff_io import get_session_id

    session_id = get_session_id(root)
    passed = result.get("preflight_passed") is True
    node_id = await asyncio.to_thread(
        record_gate_fitness,
        root,
        session_id,
        pipeline,
        passed,
        gate_summary(result),
    )
    await asyncio.to_thread(_grade_predictions_safe, root, session_id, result)
    return node_id
