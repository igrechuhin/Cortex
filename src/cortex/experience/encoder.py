"""Encoder protocol and default local encoder for task-description embeddings.

The default :class:`HashingEncoder` needs no external API and no heavyweight
ML dependency (sentence-transformers, torch, etc. are not in ``pyproject.toml``
and this module does not add one), matching the plan's "no mandatory
heavyweight dependency" constraint. Test doubles (deterministic fakes) live
under ``tests/experience/`` and satisfy :class:`EncoderProtocol` structurally.
"""

from __future__ import annotations

import hashlib
from typing import Protocol

from cortex.experience.embedding_math import l2_normalize
from cortex.retrieval.bm25 import tokenize

# AI: default dimensionality for the local hashing encoder. 128 balances
# collision rate against vector storage/scan cost at dev-tool scale (brute
# force top-k over a few thousand rows).
DEFAULT_EMBEDDING_DIM = 128
HASHING_ENCODER_VERSION = "hashing-v1"


class EncoderProtocol(Protocol):
    """Structural interface for task-description encoders (DI target)."""

    dim: int
    version: str

    def encode(self, text: str) -> list[float]:
        """Return a fixed-length embedding vector for ``text``."""
        ...  # pragma: no cover - structural Protocol stub, never executed


def _hash_token(token: str, dim: int) -> tuple[int, float]:
    """Map a token to (bucket index, sign) via the hashing trick.

    # AI: uses hashlib.sha256 rather than the builtin ``hash()`` because
    # Python randomizes str hashes per process (PYTHONHASHSEED) unless
    # disabled; sha256 gives a stable, cross-process-deterministic bucket
    # assignment so the same text always encodes to the same vector.
    """
    digest = hashlib.sha256(token.encode("utf-8")).digest()
    index = int.from_bytes(digest[:8], "big") % dim
    sign = 1.0 if digest[8] & 1 else -1.0
    return index, sign


class HashingEncoder:
    """Deterministic local feature-hashing encoder (Weinberger et al. 2009).

    Bag-of-words hashing trick: each token votes +1/-1 into a hashed bucket,
    the result is L2-normalized so dot product equals cosine similarity.
    No external API call, no model weights to load or ship.
    """

    def __init__(self, dim: int = DEFAULT_EMBEDDING_DIM) -> None:
        self.dim = dim
        self.version = HASHING_ENCODER_VERSION

    def encode(self, text: str) -> list[float]:
        vector = [0.0] * self.dim
        for token in tokenize(text):
            index, sign = _hash_token(token, self.dim)
            vector[index] += sign
        return l2_normalize(vector)
