"""Vector-seeded prior-experience recall merged into the session brief.

Best-effort: any failure (missing store, embedding error, bad config) leaves
``brief`` unchanged so a broken recall path never breaks ``session()``. When
``experience_recall_enabled`` is False (the default-safe path is True but
callers may disable it) the merge is a no-op and ``SessionBrief`` stays
byte-identical to the pre-recall behavior (the field defaults to None and is
excluded from JSON via ``exclude_none=True``).
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from cortex.core.project_session_config import load_project_session_config
from cortex.experience.embedding_index_core import EmbeddingIndexCore
from cortex.experience.encoder import HashingEncoder
from cortex.experience.recall import recall_similar_tasks
from cortex.experience.recall_render import render_recall_summary
from cortex.experience.recorder import experience_db_path
from cortex.experience.store_core import ExperienceStoreCore
from cortex.tools.session.models import SessionBrief

logger = logging.getLogger(__name__)

_default_encoder = HashingEncoder()


def _effective_goal(brief: SessionBrief) -> str | None:
    for candidate in (brief.primary_session_goal, brief.current_focus):
        if candidate and candidate.strip():
            return candidate.strip()
    return None


def _compute_recall_summary_sync(
    project_root: Path, goal: str, k: int, threshold: float, budget_chars: int
) -> str | None:
    db_path = experience_db_path(project_root)
    if not db_path.exists():
        return None
    core = ExperienceStoreCore(db_path)
    index = EmbeddingIndexCore(db_path)
    result = recall_similar_tasks(core, index, _default_encoder, goal, k, threshold)
    return render_recall_summary(result, budget_chars)


async def load_experience_recall_summary_safe(
    project_root: Path, goal: str
) -> str | None:
    """Compute the recall block text, or None on any failure/disabled config."""
    config = load_project_session_config(project_root)
    if not config.experience_recall_enabled:
        return None
    try:
        return await asyncio.to_thread(
            _compute_recall_summary_sync,
            project_root,
            goal,
            config.experience_recall_k,
            config.experience_recall_similarity_threshold,
            config.experience_recall_budget_chars,
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("experience recall failed (best-effort): %s", exc)
        return None


async def merge_experience_recall_into_brief(
    brief: SessionBrief, project_root: Path
) -> SessionBrief:
    """Attach ``experience_recall_summary`` to ``brief`` when available."""
    goal = _effective_goal(brief)
    if goal is None:
        return brief
    summary = await load_experience_recall_summary_safe(project_root, goal)
    if summary is None:
        return brief
    return brief.model_copy(update={"experience_recall_summary": summary})
