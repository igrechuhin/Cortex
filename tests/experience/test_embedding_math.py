"""Unit tests for embedding vector math (AAA pattern)."""

from __future__ import annotations

import pytest

from cortex.experience.embedding_math import (
    cosine_similarity,
    l2_normalize,
    pack_vector,
    unpack_vector,
)


def test_l2_normalize_scales_to_unit_norm() -> None:
    # Arrange
    vector = [3.0, 4.0]

    # Act
    normalized = l2_normalize(vector)

    # Assert
    assert normalized == pytest.approx([0.6, 0.8])  # type: ignore[arg-type]


def test_l2_normalize_zero_vector_passes_through() -> None:
    # Arrange
    vector = [0.0, 0.0, 0.0]

    # Act
    normalized = l2_normalize(vector)

    # Assert
    assert normalized == [0.0, 0.0, 0.0]


def test_cosine_similarity_identical_vectors_is_one() -> None:
    # Arrange
    a = [1.0, 2.0, 3.0]

    # Act
    similarity = cosine_similarity(a, list(a))

    # Assert
    assert similarity == pytest.approx(1.0)  # type: ignore[arg-type]


def test_cosine_similarity_orthogonal_vectors_is_zero() -> None:
    # Arrange
    a = [1.0, 0.0]
    b = [0.0, 1.0]

    # Act
    similarity = cosine_similarity(a, b)

    # Assert
    assert similarity == pytest.approx(0.0)  # type: ignore[arg-type]


def test_cosine_similarity_opposite_vectors_is_negative_one() -> None:
    # Arrange
    a = [1.0, 0.0]
    b = [-1.0, 0.0]

    # Act
    similarity = cosine_similarity(a, b)

    # Assert
    assert similarity == pytest.approx(-1.0)  # type: ignore[arg-type]


def test_cosine_similarity_zero_vector_is_zero() -> None:
    # Arrange
    a = [0.0, 0.0]
    b = [1.0, 1.0]

    # Act
    similarity = cosine_similarity(a, b)

    # Assert
    assert similarity == 0.0


def test_cosine_similarity_empty_vectors_is_zero() -> None:
    # Act
    similarity = cosine_similarity([], [])

    # Assert
    assert similarity == 0.0


def test_cosine_similarity_length_mismatch_raises() -> None:
    # Arrange / Act / Assert
    with pytest.raises(ValueError, match="length mismatch"):
        _ = cosine_similarity([1.0], [1.0, 2.0])


def test_pack_unpack_vector_round_trips() -> None:
    # Arrange
    vector = [0.1, -0.2, 0.3, 0.0]

    # Act
    restored = unpack_vector(pack_vector(vector))

    # Assert
    assert restored == pytest.approx(vector, abs=1e-6)  # type: ignore[arg-type]
