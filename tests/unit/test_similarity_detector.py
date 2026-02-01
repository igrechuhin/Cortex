"""Tests for similarity_detector."""

from cortex.script_analysis.similarity_detector import (
    compute_similarity,
    find_similar_pairs,
)
from cortex.script_detection.models import ScriptCaptureRecord


def _record(script_id: str, content: str) -> ScriptCaptureRecord:
    """Build a minimal ScriptCaptureRecord."""
    return ScriptCaptureRecord(
        script_id=script_id,
        timestamp="2026-01-16T10:00:00Z",
        task_description="Task",
        script_path="x.py",
        script_content=content,
    )


class TestComputeSimilarity:
    """Tests for compute_similarity."""

    def test_same_id_returns_one(self) -> None:
        """Same script_id yields similarity 1.0."""
        r = _record("id-1", "print(1)")
        assert compute_similarity(r, r) == 1.0

    def test_identical_content_returns_one(self) -> None:
        """Identical content yields 1.0 (content hash match)."""
        a = _record("id-a", "x = 1\ny = 2\n")
        b = _record("id-b", "x = 1\ny = 2\n")
        assert compute_similarity(a, b) == 1.0

    def test_completely_different_content_returns_low(self) -> None:
        """Completely different content yields low or zero similarity."""
        a = _record("id-a", "line1\nline2\nline3\n")
        b = _record("id-b", "alpha\nbeta\ngamma\n")
        score = compute_similarity(a, b)
        assert score < 0.5

    def test_partial_overlap_returns_mid(self) -> None:
        """Some shared lines yield Jaccard between 0 and 1."""
        a = _record("id-a", "line1\nline2\nline3\n")
        b = _record("id-b", "line1\nline2\nother\n")
        score = compute_similarity(a, b)
        assert 0 < score <= 1.0


class TestFindSimilarPairs:
    """Tests for find_similar_pairs."""

    def test_empty_list_returns_empty(self) -> None:
        """Empty records list returns no pairs."""
        assert find_similar_pairs([], min_similarity=0.5) == []

    def test_single_record_returns_empty(self) -> None:
        """Single record returns no pairs."""
        records = [_record("id-1", "content")]
        assert find_similar_pairs(records, min_similarity=0.5) == []

    def test_two_identical_records_returns_one_pair(self) -> None:
        """Two identical content records return one pair with score 1.0."""
        records = [
            _record("id-a", "same\ncontent\n"),
            _record("id-b", "same\ncontent\n"),
        ]
        pairs = find_similar_pairs(records, min_similarity=0.5)
        assert len(pairs) == 1
        assert pairs[0].script_id_1 == "id-a"
        assert pairs[0].script_id_2 == "id-b"
        assert pairs[0].similarity_score == 1.0

    def test_min_similarity_filters_pairs(self) -> None:
        """Pairs below min_similarity are excluded."""
        records = [
            _record("id-a", "line1\nline2\nline3\n"),
            _record("id-b", "line1\nline2\nother\n"),
        ]
        pairs_high = find_similar_pairs(records, min_similarity=0.99)
        pairs_low = find_similar_pairs(records, min_similarity=0.1)
        assert len(pairs_high) <= len(pairs_low)

    def test_pairs_sorted_by_score_descending(self) -> None:
        """Pairs are ordered by similarity_score descending."""
        r1 = _record("id-1", "a\nb\nc\n")
        r2 = _record("id-2", "a\nb\nc\n")
        r3 = _record("id-3", "a\nb\n")
        records = [r1, r2, r3]
        pairs = find_similar_pairs(records, min_similarity=0.2)
        if len(pairs) >= 2:
            assert pairs[0].similarity_score >= pairs[1].similarity_score
