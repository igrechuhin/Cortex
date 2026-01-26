"""Similarity detection algorithms for health-check analysis."""

import difflib

from cortex.core.token_counter import TokenCounter


class SimilarityEngine:
    """Engine for calculating similarity between files."""

    def __init__(self, token_counter: TokenCounter | None = None):
        """Initialize similarity engine.

        Args:
            token_counter: Token counter instance. If None, creates new one.
        """
        self.token_counter = token_counter or TokenCounter()

    def calculate_content_similarity(self, content1: str, content2: str) -> float:
        """Calculate content similarity using multiple algorithms.

        Args:
            content1: First content to compare
            content2: Second content to compare

        Returns:
            Similarity score between 0.0 and 1.0
        """
        if not content1 or not content2:
            return 0.0

        if content1 == content2:
            return 1.0

        # Use multiple algorithms and average
        token_sim = self._token_similarity(content1, content2)
        text_sim = self._text_similarity(content1, content2)
        jaccard_sim = self._jaccard_similarity(content1, content2)

        # Weighted average (token similarity most important)
        return (token_sim * 0.5) + (text_sim * 0.3) + (jaccard_sim * 0.2)

    def _token_similarity(self, content1: str, content2: str) -> float:
        """Calculate token-based similarity.

        Args:
            content1: First content
            content2: Second content

        Returns:
            Similarity score between 0.0 and 1.0
        """
        # Get encoding if available
        encoding = self.token_counter.encoding
        if encoding is None:
            # Fallback to word-based similarity if tiktoken unavailable
            return self._jaccard_similarity(content1, content2)

        try:
            tokens1 = set(encoding.encode(content1))
            tokens2 = set(encoding.encode(content2))
        except Exception:
            # Fallback to word-based similarity on error
            return self._jaccard_similarity(content1, content2)

        if not tokens1 and not tokens2:
            return 1.0
        if not tokens1 or not tokens2:
            return 0.0

        intersection = len(tokens1 & tokens2)
        union = len(tokens1 | tokens2)

        return intersection / union if union > 0 else 0.0

    def _text_similarity(self, content1: str, content2: str) -> float:
        """Calculate text similarity using SequenceMatcher.

        Args:
            content1: First content
            content2: Second content

        Returns:
            Similarity score between 0.0 and 1.0
        """
        return difflib.SequenceMatcher(None, content1, content2).ratio()

    def _jaccard_similarity(self, content1: str, content2: str) -> float:
        """Calculate Jaccard similarity on word sets.

        Args:
            content1: First content
            content2: Second content

        Returns:
            Similarity score between 0.0 and 1.0
        """
        words1 = set(content1.lower().split())
        words2 = set(content2.lower().split())

        if not words1 and not words2:
            return 1.0
        if not words1 or not words2:
            return 0.0

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0

    def calculate_section_similarity(
        self, sections1: list[str], sections2: list[str]
    ) -> float:
        """Calculate similarity between file sections.

        Args:
            sections1: Sections from first file
            sections2: Sections from second file

        Returns:
            Average similarity score between 0.0 and 1.0
        """
        if not sections1 or not sections2:
            return 0.0

        similarities: list[float] = []
        for sec1 in sections1:
            best_match = 0.0
            for sec2 in sections2:
                sim = self.calculate_content_similarity(sec1, sec2)
                best_match = max(best_match, sim)
            similarities.append(best_match)

        return sum(similarities) / len(similarities) if similarities else 0.0
