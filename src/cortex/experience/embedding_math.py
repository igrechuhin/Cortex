"""Pure vector math helpers for embedding storage and cosine similarity.

Stateless functions only; no I/O. Shared by :mod:`cortex.experience.encoder`
(vector construction) and :mod:`cortex.experience.embedding_index_core`
(similarity scoring).
"""

from __future__ import annotations

import math


def l2_normalize(vector: list[float]) -> list[float]:
    """Return ``vector`` scaled to unit L2 norm; zero vector passes through."""
    norm = math.sqrt(sum(component * component for component in vector))
    if norm == 0.0:
        return list(vector)
    return [component / norm for component in vector]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity of two equal-length vectors; 0.0 for empty/zero input.

    Assumes callers pass vectors of the same dimensionality (both produced
    by the same encoder version); mismatched lengths raise ``ValueError``.
    """
    if len(a) != len(b):
        raise ValueError(f"vector length mismatch: {len(a)} != {len(b)}")
    if not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def pack_vector(vector: list[float]) -> bytes:
    """Serialize a float vector to a compact BLOB (little-endian float32)."""
    import array

    return array.array("f", vector).tobytes()


def unpack_vector(blob: bytes) -> list[float]:
    """Deserialize a BLOB produced by :func:`pack_vector` back to floats."""
    import array

    values = array.array("f")
    values.frombytes(blob)
    return list(values)
