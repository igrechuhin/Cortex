"""Embedding-based relevance ranking for context-layer budget truncation.

Reuses the same primitives that back the experience store's task-embedding
index (:mod:`cortex.experience.encoder` for vectorization,
:mod:`cortex.experience.embedding_math` for cosine similarity,
:mod:`cortex.retrieval.bm25` for the keyword signal) and mirrors the
vector/BM25 blend formula in :mod:`cortex.experience.hybrid_rank`.

# AI: does NOT round-trip through ``EmbeddingIndexCore``'s SQLite-backed
# top-k index. That index persists embeddings keyed by a stable ``task_id``
# for reuse across calls; the candidates ranked here are ephemeral
# paragraphs/lines recomputed on every context-load call, so persisting them
# would write throwaway rows on a hot path for no lookup benefit (see the
# plan's "coupling to experience-store internals" risk). Cosine similarity
# is computed directly in-memory instead.
"""

from __future__ import annotations

import logging
import os

from pydantic import BaseModel, Field

from cortex.experience.embedding_math import cosine_similarity
from cortex.experience.encoder import (
    DEFAULT_EMBEDDING_DIM,
    EncoderProtocol,
    HashingEncoder,
)
from cortex.experience.hybrid_rank import DEFAULT_VECTOR_WEIGHT
from cortex.retrieval.bm25 import bm25_scores

logger = logging.getLogger(__name__)

RELEVANCE_RANKING_ENV_FLAG = "CORTEX_RELEVANCE_RANKING_ENABLED"

# AI: opt-in, defaults to disabled per the plan's rollback-safety risk
# mitigation ("config flag defaults to disabled until validated").
_ENABLED_VALUES = frozenset({"1", "true", "on", "yes"})

_shared_encoder: EncoderProtocol = HashingEncoder(dim=DEFAULT_EMBEDDING_DIM)


class RankedCandidate(BaseModel):
    """One ranked candidate: its original position, text, and blended score."""

    index: int = Field(
        ge=0, description="Position of this candidate in the input list."
    )
    text: str
    score: float


def relevance_ranking_enabled(override: bool | None = None) -> bool:
    """Return True when relevance-ranked truncation is enabled (default off)."""
    if override is not None:
        return override
    raw = os.environ.get(RELEVANCE_RANKING_ENV_FLAG, "0")
    return raw.strip().lower() in _ENABLED_VALUES


def _vector_scores(
    encoder: EncoderProtocol, query_vector: list[float], candidates: list[str]
) -> list[float]:
    return [
        cosine_similarity(query_vector, encoder.encode(candidate))
        for candidate in candidates
    ]


def _blend(
    query: str,
    candidates: list[str],
    vector_scores: list[float],
    vector_weight: float,
) -> list[RankedCandidate]:
    """Blend vector similarity with pool-normalized BM25 (mirrors hybrid_rank)."""
    bm25_raw = bm25_scores(query, candidates)
    max_bm25 = max(bm25_raw, default=0.0)
    ranked: list[RankedCandidate] = []
    for idx, (text, vscore, bscore) in enumerate(
        zip(candidates, vector_scores, bm25_raw, strict=True)
    ):
        normalized_bm25 = (bscore / max_bm25) if max_bm25 > 0.0 else 0.0
        combined = vector_weight * vscore + (1.0 - vector_weight) * normalized_bm25
        ranked.append(RankedCandidate(index=idx, text=text, score=combined))
    return ranked


def rank_candidates_by_relevance(
    query: str,
    candidates: list[str],
    encoder: EncoderProtocol | None = None,
    vector_weight: float = DEFAULT_VECTOR_WEIGHT,
) -> list[RankedCandidate]:
    """Rank ``candidates`` by relevance to ``query``, most relevant first.

    Blends cosine similarity of encoded text against the query with a
    BM25 keyword score over the candidate pool, same weighting formula as
    :func:`cortex.experience.hybrid_rank.hybrid_scores`. Returns ``[]`` for
    an empty candidate list; raises nothing candidates-side (encoder errors
    propagate to the caller, which is expected to fail open — see
    :func:`reorder_by_relevance`).
    """
    if not candidates:
        return []
    active_encoder = encoder or _shared_encoder
    query_vector = active_encoder.encode(query)
    vector_scores = _vector_scores(active_encoder, query_vector, candidates)
    ranked = _blend(query, candidates, vector_scores, vector_weight)
    ranked.sort(key=lambda candidate: candidate.score, reverse=True)
    return ranked


def reorder_by_relevance(
    query: str | None,
    segments: list[str],
    encoder: EncoderProtocol | None = None,
) -> list[str]:
    """Return ``segments`` reordered by relevance to ``query``, best first.

    Fails open to the original (positional) order — unchanged — when
    ranking is disabled, ``query`` is missing/blank, there are fewer than
    two segments, or ranking raises for any reason (embedding encoder
    error, etc.). This is a hot path (called on every context-load budget
    cut) and must never block or slow context loading on a ranking failure.
    """
    if len(segments) < 2 or not query or not query.strip():
        return list(segments)
    if not relevance_ranking_enabled():
        return list(segments)
    try:
        ranked = rank_candidates_by_relevance(query, segments, encoder=encoder)
    except Exception as exc:  # noqa: BLE001 - fail open, never block context loading
        logger.warning("relevance ranking failed, using positional order: %s", exc)
        return list(segments)
    return [candidate.text for candidate in ranked]
