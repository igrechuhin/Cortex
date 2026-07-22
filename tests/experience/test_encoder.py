"""Unit tests for the Encoder protocol and default HashingEncoder (AAA)."""

from __future__ import annotations

from cortex.experience.embedding_math import cosine_similarity
from cortex.experience.encoder import DEFAULT_EMBEDDING_DIM, HashingEncoder
from tests.experience.embedding_fixtures import FakeEncoder


def test_hashing_encoder_returns_unit_length_vector_of_configured_dim() -> None:
    # Arrange
    encoder = HashingEncoder(dim=32)

    # Act
    vector = encoder.encode("fix the pyright type error in the retrieval module")

    # Assert
    assert len(vector) == 32
    norm = sum(component * component for component in vector) ** 0.5
    assert norm == 1.0 or norm == 0.0


def test_hashing_encoder_is_deterministic_across_calls() -> None:
    # Arrange
    encoder = HashingEncoder(dim=DEFAULT_EMBEDDING_DIM)
    text = "quality gate failed on markdown lint"

    # Act
    first = encoder.encode(text)
    second = encoder.encode(text)

    # Assert
    assert first == second


def test_hashing_encoder_similar_text_scores_higher_than_unrelated_text() -> None:
    # Arrange
    encoder = HashingEncoder(dim=DEFAULT_EMBEDDING_DIM)
    goal = "fix pyright type error in retrieval module"
    similar = "resolve pyright type error inside retrieval code"
    unrelated = "bake a chocolate cake for the weekend party"

    # Act
    goal_vec = encoder.encode(goal)
    similar_vec = encoder.encode(similar)
    unrelated_vec = encoder.encode(unrelated)

    # Assert
    assert cosine_similarity(goal_vec, similar_vec) > cosine_similarity(
        goal_vec, unrelated_vec
    )


def test_hashing_encoder_empty_text_returns_zero_vector() -> None:
    # Arrange
    encoder = HashingEncoder(dim=16)

    # Act
    vector = encoder.encode("")

    # Assert
    assert vector == [0.0] * 16


def test_hashing_encoder_default_dim_and_version() -> None:
    # Arrange / Act
    encoder = HashingEncoder()

    # Assert
    assert encoder.dim == DEFAULT_EMBEDDING_DIM
    assert encoder.version == "hashing-v1"


def test_fake_encoder_satisfies_encoder_protocol_shape() -> None:
    # Arrange
    encoder = FakeEncoder(keyword_dims={"auth": 0, "billing": 1}, dim=4)

    # Act
    auth_vector = encoder.encode("Fix the AUTH token bug")
    billing_vector = encoder.encode("billing invoice mismatch")
    unmatched_vector = encoder.encode("something else entirely")

    # Assert
    assert auth_vector == [1.0, 0.0, 0.0, 0.0]
    assert billing_vector == [0.0, 1.0, 0.0, 0.0]
    assert unmatched_vector == [0.0, 0.0, 0.0, 0.01]
