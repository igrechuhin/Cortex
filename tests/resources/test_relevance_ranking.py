"""Unit tests for embedding-based relevance ranking (AAA pattern)."""

from __future__ import annotations

import pytest

from cortex.tools.context.relevance_ranking import (
    RELEVANCE_RANKING_ENV_FLAG,
    RankedCandidate,
    rank_candidates_by_relevance,
    relevance_ranking_enabled,
    reorder_by_relevance,
)
from tests.experience.embedding_fixtures import FakeEncoder


class _RaisingEncoder:
    """Test double that always raises, simulating an unavailable embedder."""

    dim = 8
    version = "raising-v1"

    def encode(self, text: str) -> list[float]:
        raise RuntimeError("embedding backend unavailable")


def test_relevance_ranking_enabled_defaults_to_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    monkeypatch.delenv(RELEVANCE_RANKING_ENV_FLAG, raising=False)

    # Act
    result = relevance_ranking_enabled()

    # Assert
    assert result is False


@pytest.mark.parametrize("raw_value", ["1", "true", "TRUE", "on", "yes"])
def test_relevance_ranking_enabled_true_for_accepted_values(
    monkeypatch: pytest.MonkeyPatch, raw_value: str
) -> None:
    # Arrange
    monkeypatch.setenv(RELEVANCE_RANKING_ENV_FLAG, raw_value)

    # Act
    result = relevance_ranking_enabled()

    # Assert
    assert result is True


def test_relevance_ranking_enabled_override_wins_over_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    monkeypatch.setenv(RELEVANCE_RANKING_ENV_FLAG, "1")

    # Act
    result = relevance_ranking_enabled(override=False)

    # Assert
    assert result is False


def test_rank_candidates_by_relevance_empty_candidates_returns_empty_list() -> None:
    # Arrange
    encoder = FakeEncoder(keyword_dims={"auth": 0}, dim=4)

    # Act
    ranked = rank_candidates_by_relevance("auth bug", [], encoder=encoder)

    # Assert
    assert ranked == []


def test_rank_candidates_by_relevance_single_candidate_returned_unchanged() -> None:
    # Arrange
    encoder = FakeEncoder(keyword_dims={"auth": 0}, dim=4)
    candidates = ["a paragraph about the auth token bug"]

    # Act
    ranked = rank_candidates_by_relevance("auth bug", candidates, encoder=encoder)

    # Assert
    assert len(ranked) == 1
    assert ranked[0].text == candidates[0]
    assert ranked[0].index == 0


def test_rank_candidates_by_relevance_orders_semantically_relevant_first() -> None:
    # Arrange
    encoder = FakeEncoder(keyword_dims={"auth": 0, "billing": 1}, dim=4)
    candidates = [
        "The billing invoice reconciliation job runs nightly.",
        "The auth token refresh flow was recently rewritten.",
        "Unrelated release-notes boilerplate paragraph.",
    ]

    # Act
    ranked = rank_candidates_by_relevance(
        "fix the auth token bug", candidates, encoder=encoder
    )

    # Assert
    assert ranked[0].text == candidates[1]
    assert ranked[0].score > ranked[-1].score


def test_rank_candidates_by_relevance_returns_ranked_candidate_models() -> None:
    # Arrange
    encoder = FakeEncoder(keyword_dims={"auth": 0}, dim=4)

    # Act
    ranked = rank_candidates_by_relevance(
        "auth bug", ["auth paragraph", "other paragraph"], encoder=encoder
    )

    # Assert
    assert all(isinstance(item, RankedCandidate) for item in ranked)


def test_reorder_by_relevance_returns_positional_order_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    monkeypatch.delenv(RELEVANCE_RANKING_ENV_FLAG, raising=False)
    segments = ["first paragraph", "second paragraph"]

    # Act
    ordered = reorder_by_relevance("some query", segments)

    # Assert
    assert ordered == segments


def test_reorder_by_relevance_returns_positional_order_when_query_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    monkeypatch.setenv(RELEVANCE_RANKING_ENV_FLAG, "1")
    segments = ["first paragraph", "second paragraph"]

    # Act
    ordered = reorder_by_relevance(None, segments)

    # Assert
    assert ordered == segments


def test_reorder_by_relevance_returns_positional_order_for_blank_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    monkeypatch.setenv(RELEVANCE_RANKING_ENV_FLAG, "1")
    segments = ["first paragraph", "second paragraph"]

    # Act
    ordered = reorder_by_relevance("   ", segments)

    # Assert
    assert ordered == segments


def test_reorder_by_relevance_returns_input_unchanged_for_single_segment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    monkeypatch.setenv(RELEVANCE_RANKING_ENV_FLAG, "1")
    segments = ["only paragraph"]

    # Act
    ordered = reorder_by_relevance("auth bug", segments)

    # Assert
    assert ordered == segments


def test_reorder_by_relevance_reorders_when_enabled_and_query_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    monkeypatch.setenv(RELEVANCE_RANKING_ENV_FLAG, "1")
    encoder = FakeEncoder(keyword_dims={"auth": 0, "billing": 1}, dim=4)
    segments = [
        "Unrelated release-notes boilerplate paragraph.",
        "The auth token refresh flow was recently rewritten.",
    ]

    # Act
    ordered = reorder_by_relevance("auth token bug", segments, encoder=encoder)

    # Assert
    assert ordered[0] == segments[1]


def test_reorder_by_relevance_fails_open_when_encoder_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    monkeypatch.setenv(RELEVANCE_RANKING_ENV_FLAG, "1")
    segments = ["first paragraph", "second paragraph"]

    # Act
    ordered = reorder_by_relevance("auth bug", segments, encoder=_RaisingEncoder())

    # Assert
    assert ordered == segments
