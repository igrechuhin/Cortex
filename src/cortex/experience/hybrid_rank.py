"""Hybrid vector + BM25 ranking over the same task-spec corpus.

Vector similarity seeds the candidate set (per the Experience Graphs paper's
vector-seeded retrieval); BM25 re-scores that candidate pool using the same
task-spec text so keyword-exact matches are not lost to embedding noise.
"""

from __future__ import annotations

from cortex.experience.models import ExperienceTask
from cortex.retrieval.bm25 import bm25_scores

# AI: weight favors vector similarity (semantic match) over BM25 (keyword
# match) since this module exists specifically to find tasks a keyword
# search would miss; BM25 still breaks ties and rewards exact-term hits.
DEFAULT_VECTOR_WEIGHT = 0.6


def hybrid_scores(
    goal: str,
    tasks: list[ExperienceTask],
    vector_similarities: dict[str, float],
    vector_weight: float = DEFAULT_VECTOR_WEIGHT,
) -> dict[str, float]:
    """Combine per-task vector similarity with BM25 score over ``tasks``.

    BM25 scores are min-max normalized against the candidate pool (not the
    whole corpus) so they compose with the [0, 1]-ish vector similarity
    range. Returns a ``task_id -> combined_score`` mapping.
    """
    if not tasks:
        return {}
    corpus = [task.spec for task in tasks]
    raw_bm25 = bm25_scores(goal, corpus)
    max_bm25 = max(raw_bm25, default=0.0)
    combined: dict[str, float] = {}
    for task, score in zip(tasks, raw_bm25, strict=True):
        normalized_bm25 = (score / max_bm25) if max_bm25 > 0.0 else 0.0
        vector_score = vector_similarities.get(task.id, 0.0)
        combined[task.id] = (
            vector_weight * vector_score + (1.0 - vector_weight) * normalized_bm25
        )
    return combined
