"""Surface open claims and recent misses in the session brief.

Best-effort: any failure leaves the brief unchanged, so a broken prediction
store never breaks ``session()``. The rendered line is capped by
``brief_cap`` so accumulating verdicts cannot blow the token budget.
"""

from __future__ import annotations

import logging
from pathlib import Path

from cortex.experience.claims import ClaimVerdict, Verdict, is_free_text
from cortex.experience.predictions import open_predictions, recent_verdicts
from cortex.tools.session.models import SessionBrief

logger = logging.getLogger(__name__)

_MAX_SURFACED_MISSES = 3


def _render(open_count: int, free_text: int, misses: list[ClaimVerdict]) -> str | None:
    if not open_count and not misses:
        return None
    parts = [f"{open_count} open claim(s) awaiting the next run_quality_gate()"]
    # AI: measures the vocabulary gap rather than assuming it — a high
    # free-text share means the seven forms cannot express real intent.
    if free_text:
        parts.append(f"{free_text} free-text (graded only as 'change')")
    if misses:
        listed = "; ".join(f"{m.claim.raw} ({m.evidence})" for m in misses)
        parts.append(f"recent misses: {listed}")
    return " | ".join(parts)


def merge_predictions_into_brief(
    brief: SessionBrief, project_root: Path
) -> SessionBrief:
    """Attach the ``predictions`` line to ``brief`` when there is one."""
    try:
        from cortex.tools.session.pipeline_handoff_io import get_session_id

        session_id = get_session_id(project_root)
        misses = [
            verdict
            for verdict in recent_verdicts(project_root, session_id, limit=20)
            if verdict.verdict is Verdict.MISS
        ][:_MAX_SURFACED_MISSES]
        claims = open_predictions(project_root, session_id)
        free_text = sum(1 for claim in claims if is_free_text(claim))
        line = _render(len(claims), free_text, misses)
    except Exception as exc:  # noqa: BLE001
        logger.debug("prediction brief failed (best-effort): %s", exc)
        return brief
    if line is None:
        return brief
    return brief.model_copy(update={"predictions": line})
