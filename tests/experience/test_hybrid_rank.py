"""Unit tests for hybrid vector+BM25 scoring (AAA pattern)."""

from __future__ import annotations

from cortex.experience.hybrid_rank import hybrid_scores
from cortex.experience.models import ExperienceTask


def test_hybrid_scores_combines_vector_and_bm25() -> None:
    # Arrange
    tasks = [
        ExperienceTask(id="t1", spec="fix pyright type errors in retrieval module"),
        ExperienceTask(id="t2", spec="bake a chocolate cake recipe"),
    ]
    vector_similarities = {"t1": 0.9, "t2": 0.1}

    # Act
    scores = hybrid_scores("pyright type errors", tasks, vector_similarities)

    # Assert
    assert scores["t1"] > scores["t2"]


def test_hybrid_scores_empty_tasks_returns_empty_dict() -> None:
    # Act
    scores = hybrid_scores("goal", [], {})

    # Assert
    assert scores == {}


def test_hybrid_scores_zero_bm25_falls_back_to_vector_only() -> None:
    # Arrange: query shares no tokens with either spec (BM25 all-zero).
    tasks = [ExperienceTask(id="t1", spec="alpha beta gamma")]
    vector_similarities = {"t1": 0.5}

    # Act
    scores = hybrid_scores("zzz unrelated query", tasks, vector_similarities)

    # Assert
    assert scores["t1"] == 0.6 * 0.5


def test_hybrid_scores_missing_vector_similarity_defaults_to_zero() -> None:
    # Arrange
    tasks = [ExperienceTask(id="t1", spec="fix bug")]

    # Act
    scores = hybrid_scores("fix bug", tasks, {})

    # Assert: only the BM25 component contributes.
    assert scores["t1"] > 0.0
    assert scores["t1"] <= (1.0 - 0.6)


def test_hybrid_scores_vector_weight_is_configurable() -> None:
    # Arrange
    tasks = [ExperienceTask(id="t1", spec="alpha beta gamma")]
    vector_similarities = {"t1": 1.0}

    # Act
    scores = hybrid_scores(
        "zzz unrelated", tasks, vector_similarities, vector_weight=1.0
    )

    # Assert
    assert scores["t1"] == 1.0
