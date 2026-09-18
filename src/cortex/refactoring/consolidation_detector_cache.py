"""
Memoized hashing and similarity helpers for consolidation detection.

Extracted from consolidation_detector.py for file size compliance.

Cached at module scope, not as ConsolidationDetector methods: decorating an
instance method with functools.cache would pin every detector instance ever
constructed in the cache for the life of the process.
"""

from functools import cache

from cortex.refactoring.consolidation_detector_similarity import (
    calculate_similarity,
    compute_content_hash,
)


@cache
def cached_content_hash(content: str) -> str:
    """Compute (and memoize) the content hash used for duplicate detection."""
    return compute_content_hash(content)


@cache
def cached_similarity(content1: str, content2: str, hash1: str, hash2: str) -> float:
    """Compute (and memoize) similarity, short-circuiting on identical hashes."""
    if hash1 == hash2:
        return 1.0
    return calculate_similarity(content1, content2)
