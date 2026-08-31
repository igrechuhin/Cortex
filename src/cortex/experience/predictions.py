"""Persist predictions and their verdicts as ordinary experience nodes.

Every function here follows the ``record_gate_fitness`` contract: best-effort,
never raises past the caller, logs at WARNING with the session id as trace id,
and counts the failure. Recording a prediction must never break a quality gate.

Claims live in their own ``prediction`` pipeline lineage so grading never
perturbs the commit pipeline's node chain. Open claims are the prediction nodes
appended since the last ``predictions-graded`` marker.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from cortex.experience.artifacts import load_artifact, store_artifact
from cortex.experience.claims import Claim, ClaimVerdict, Verdict
from cortex.experience.models import ExperienceNodeStatus
from cortex.experience.recorder import (
    append_child_node,
    ensure_lineage,
    experience_db_path,
    recording_enabled,
    warn_recording_failure,
)
from cortex.experience.store_core import ExperienceStoreCore

__all__ = [
    "GRADED_MARKER_LABEL",
    "PREDICTION_PIPELINE",
    "open_predictions",
    "recent_verdicts",
    "record_prediction",
    "record_verdicts",
]

PREDICTION_PIPELINE = "prediction"
PREDICTION_LABEL_PREFIX = "prediction:"
GRADED_MARKER_LABEL = "predictions-graded"


def _core(project_root: Path) -> ExperienceStoreCore:
    return ExperienceStoreCore(experience_db_path(project_root))


def record_prediction(
    project_root: Path,
    session_id: str,
    claims: list[Claim],
    because: str | None = None,
    enabled: bool | None = None,
) -> str | None:
    """Record open claims for the session. Best-effort; returns the node id."""
    if not recording_enabled(enabled) or not claims:
        return None
    try:
        core = _core(project_root)
        session = ensure_lineage(core, session_id, PREDICTION_PIPELINE)
        payload = json.dumps(
            {
                "because": because,
                "claims": [claim.model_dump(mode="json") for claim in claims],
            }
        )
        node = append_child_node(
            core,
            experience_session_id=session.id,
            status=ExperienceNodeStatus.PENDING,
            label=f"{PREDICTION_LABEL_PREFIX}{len(claims)}",
            artifact_ref=store_artifact(project_root, "prediction", payload),
        )
        return node.id
    except Exception as exc:  # noqa: BLE001
        warn_recording_failure(session_id, "record_prediction", exc)
        return None


def _claims_from_artifact(project_root: Path, artifact_ref: str) -> list[Claim]:
    raw = cast(dict[str, object], json.loads(load_artifact(project_root, artifact_ref)))
    items = raw.get("claims")
    if not isinstance(items, list):
        return []
    return [
        Claim.model_validate(item)
        for item in cast(list[object], items)
        if isinstance(item, dict)
    ]


def open_predictions(
    project_root: Path, session_id: str, enabled: bool | None = None
) -> list[Claim]:
    """Claims recorded since the last grading run. Best-effort; [] on failure."""
    if not recording_enabled(enabled) or not experience_db_path(project_root).exists():
        return []
    try:
        core = _core(project_root)
        session = ensure_lineage(core, session_id, PREDICTION_PIPELINE)
        claims: list[Claim] = []
        for node in core.list_nodes(session.id):
            label = node.label or ""
            if label == GRADED_MARKER_LABEL:
                claims = []
            elif label.startswith(PREDICTION_LABEL_PREFIX) and node.artifact_ref:
                claims.extend(_claims_from_artifact(project_root, node.artifact_ref))
        return claims
    except Exception as exc:  # noqa: BLE001
        warn_recording_failure(session_id, "open_predictions", exc)
        return []


def _fitness(verdicts: list[ClaimVerdict]) -> float | None:
    graded = [v for v in verdicts if v.verdict is not Verdict.UNGRADED]
    if not graded:
        return None
    hits = sum(1 for v in graded if v.verdict is Verdict.HIT)
    return hits / len(graded)


def record_verdicts(
    project_root: Path,
    session_id: str,
    verdicts: list[ClaimVerdict],
    enabled: bool | None = None,
) -> str | None:
    """Record graded verdicts and close the open-prediction window."""
    if not recording_enabled(enabled) or not verdicts:
        return None
    try:
        core = _core(project_root)
        session = ensure_lineage(core, session_id, PREDICTION_PIPELINE)
        payload = json.dumps([v.model_dump(mode="json") for v in verdicts])
        missed = any(v.verdict is Verdict.MISS for v in verdicts)
        node = append_child_node(
            core,
            experience_session_id=session.id,
            status=(
                ExperienceNodeStatus.FAILED
                if missed
                else ExperienceNodeStatus.COMPLETED
            ),
            label=GRADED_MARKER_LABEL,
            fitness=_fitness(verdicts),
            artifact_ref=store_artifact(project_root, "prediction-verdicts", payload),
        )
        return node.id
    except Exception as exc:  # noqa: BLE001
        warn_recording_failure(session_id, "record_verdicts", exc)
        return None


def _verdicts_from_artifact(
    project_root: Path, artifact_ref: str
) -> list[ClaimVerdict]:
    raw = json.loads(load_artifact(project_root, artifact_ref))
    if not isinstance(raw, list):
        return []
    return [
        ClaimVerdict.model_validate(item)
        for item in cast(list[object], raw)
        if isinstance(item, dict)
    ]


def recent_verdicts(
    project_root: Path,
    session_id: str,
    limit: int = 3,
    enabled: bool | None = None,
) -> list[ClaimVerdict]:
    """Most recent graded verdicts, newest marker first. Best-effort."""
    if not recording_enabled(enabled) or not experience_db_path(project_root).exists():
        return []
    try:
        core = _core(project_root)
        session = ensure_lineage(core, session_id, PREDICTION_PIPELINE)
        collected: list[ClaimVerdict] = []
        for node in reversed(core.list_nodes(session.id)):
            if node.label != GRADED_MARKER_LABEL or not node.artifact_ref:
                continue
            collected.extend(_verdicts_from_artifact(project_root, node.artifact_ref))
            if len(collected) >= limit:
                break
        return collected[:limit]
    except Exception as exc:  # noqa: BLE001
        warn_recording_failure(session_id, "recent_verdicts", exc)
        return []
