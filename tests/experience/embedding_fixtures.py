"""Deterministic test-double encoder for embedding/recall tests.

Not a pytest module (no ``test_`` prefix); imported by test modules that
need full control over which task vectors are "similar" to a goal without
depending on the production hashing scheme.
"""

from __future__ import annotations


class FakeEncoder:
    """One-hot-per-keyword encoder: fully deterministic, no hashing collisions.

    Each keyword in ``keyword_dims`` sets its mapped vector index to 1.0 when
    present (case-insensitive substring match) in the encoded text. Text that
    matches no keyword gets a small signal on a dedicated fallback axis (the
    last vector index) so it stays orthogonal to every registered keyword
    axis instead of accidentally aliasing dimension 0.
    """

    def __init__(self, keyword_dims: dict[str, int], dim: int) -> None:
        self.dim = dim
        self.version = "fake-v1"
        self._keyword_dims = keyword_dims
        self._fallback_index = dim - 1

    def encode(self, text: str) -> list[float]:
        lowered = text.lower()
        vector = [0.0] * self.dim
        matched = False
        for keyword, index in self._keyword_dims.items():
            if keyword in lowered:
                vector[index] = 1.0
                matched = True
        if not matched:
            vector[self._fallback_index] = 0.01
        return vector
