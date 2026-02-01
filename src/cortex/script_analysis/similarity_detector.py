"""Detect duplicate or redundant captured scripts."""

import re
from hashlib import sha256

from cortex.script_analysis.models import SimilarityPair
from cortex.script_detection.models import ScriptCaptureRecord


def _normalize_content(content: str) -> str:
    """Normalize script content for comparison (lowercase, collapse whitespace)."""
    if not content:
        return ""
    text = content.strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def _content_hash(content: str) -> str:
    """SHA256 hash of normalized content."""
    return sha256(_normalize_content(content).encode("utf-8")).hexdigest()


def _jaccard_lines(content_a: str, content_b: str) -> float:
    """Jaccard similarity of line sets (after stripping)."""
    lines_a = {ln.strip() for ln in content_a.splitlines() if ln.strip()}
    lines_b = {ln.strip() for ln in content_b.splitlines() if ln.strip()}
    if not lines_a and not lines_b:
        return 1.0
    if not lines_a or not lines_b:
        return 0.0
    inter = len(lines_a & lines_b)
    union = len(lines_a | lines_b)
    return inter / union if union else 0.0


def compute_similarity(
    record_a: ScriptCaptureRecord, record_b: ScriptCaptureRecord
) -> float:
    """Compute similarity score between two capture records (0-1).

    Uses content hash equality and Jaccard similarity of lines.
    Same content -> 1.0; no overlap -> 0.0.

    Args:
        record_a: First capture record.
        record_b: Second capture record.

    Returns:
        Similarity score between 0 and 1.
    """
    if record_a.script_id == record_b.script_id:
        return 1.0

    content_a = record_a.script_content or ""
    content_b = record_b.script_content or ""

    if _content_hash(content_a) == _content_hash(content_b):
        return 1.0

    return _jaccard_lines(content_a, content_b)


def find_similar_pairs(
    records: list[ScriptCaptureRecord],
    min_similarity: float = 0.5,
) -> list[SimilarityPair]:
    """Find pairs of records with similarity >= min_similarity.

    Args:
        records: List of capture records.
        min_similarity: Minimum score to include a pair (0-1).

    Returns:
        List of SimilarityPair, ordered by score descending.
    """
    pairs: list[SimilarityPair] = []
    n = len(records)
    for i in range(n):
        for j in range(i + 1, n):
            score = compute_similarity(records[i], records[j])
            if score >= min_similarity:
                pairs.append(
                    SimilarityPair(
                        script_id_1=records[i].script_id,
                        script_id_2=records[j].script_id,
                        similarity_score=round(score, 4),
                    )
                )
    pairs.sort(key=lambda p: p.similarity_score, reverse=True)
    return pairs
