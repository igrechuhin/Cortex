"""Content- and section-level similarity (token, text, cosine, Jaccard)."""

import difflib
import math
import re

from cortex.core.token_counter import TokenCounter


class SimilarityCore:
    """Core similarity: token/text/cosine/Jaccard and section weighting."""

    def __init__(
        self,
        token_counter: TokenCounter | None = None,
        min_content_length: int = 100,
        heading_weight: float = 1.5,
        code_weight: float = 1.2,
        text_weight: float = 1.0,
    ):
        self.token_counter = token_counter or TokenCounter()
        self.min_content_length = min_content_length
        self.heading_weight = heading_weight
        self.code_weight = code_weight
        self.text_weight = text_weight

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

        if not self._meets_min_length(content1, content2):
            return 0.0

        token_sim = self._token_similarity(content1, content2)
        text_sim = self._text_similarity(content1, content2)
        jaccard_sim = self._jaccard_similarity(content1, content2)
        cosine_sim = self._cosine_similarity(content1, content2)

        return (
            (token_sim * 0.35)
            + (cosine_sim * 0.35)
            + (text_sim * 0.20)
            + (jaccard_sim * 0.10)
        )

    def _token_similarity(self, content1: str, content2: str) -> float:
        """Calculate token-based similarity."""
        encoding = self.token_counter.encoding
        if encoding is None:
            return self._jaccard_similarity(content1, content2)

        try:
            tokens1 = set(encoding.encode(content1))
            tokens2 = set(encoding.encode(content2))
        except Exception:
            return self._jaccard_similarity(content1, content2)

        if not tokens1 and not tokens2:
            return 1.0
        if not tokens1 or not tokens2:
            return 0.0

        intersection = len(tokens1 & tokens2)
        union = len(tokens1 | tokens2)

        return intersection / union if union > 0 else 0.0

    def _text_similarity(self, content1: str, content2: str) -> float:
        """Calculate text similarity using SequenceMatcher."""
        return difflib.SequenceMatcher(None, content1, content2).ratio()

    def _jaccard_similarity(self, content1: str, content2: str) -> float:
        """Calculate Jaccard similarity on word sets."""
        words1 = set(content1.lower().split())
        words2 = set(content2.lower().split())

        if not words1 and not words2:
            return 1.0
        if not words1 or not words2:
            return 0.0

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0

    def _cosine_similarity(self, content1: str, content2: str) -> float:
        """Calculate cosine similarity for vectorized content."""
        vec1 = self._vectorize_content(content1)
        vec2 = self._vectorize_content(content2)

        if not vec1 or not vec2:
            return 0.0

        dot_product = sum(vec1.get(word, 0) * vec2.get(word, 0) for word in vec1)
        magnitude1 = math.sqrt(sum(v * v for v in vec1.values()))
        magnitude2 = math.sqrt(sum(v * v for v in vec2.values()))

        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        return dot_product / (magnitude1 * magnitude2)

    def _vectorize_content(self, content: str) -> dict[str, float]:
        """Vectorize content using word frequency."""
        words = re.findall(r"\b[a-z0-9][-a-z0-9]*\b", content.lower())
        word_counts: dict[str, float] = {}
        for word in words:
            if len(word) > 2:
                word_counts[word] = word_counts.get(word, 0) + 1.0
        return word_counts

    def _meets_min_length(self, content1: str, content2: str) -> bool:
        """Check if content meets minimum length requirement."""
        try:
            count1 = self.token_counter.count_tokens(content1)
            count2 = self.token_counter.count_tokens(content2)
            return (
                count1 >= self.min_content_length and count2 >= self.min_content_length
            )
        except Exception:
            return (
                len(content1) >= self.min_content_length
                and len(content2) >= self.min_content_length
            )

    def _get_section_weight(self, section: str) -> float:
        """Get weight for section based on type."""
        if section.strip().startswith("#"):
            return self.heading_weight
        if "```" in section or section.strip().startswith("    "):
            return self.code_weight
        return self.text_weight

    def calculate_section_similarity(
        self, sections1: list[str], sections2: list[str]
    ) -> float:
        """Calculate similarity between file sections with importance weighting."""
        if not sections1 or not sections2:
            return 0.0

        weighted_similarities: list[float] = []
        for sec1 in sections1:
            weight = self._get_section_weight(sec1)
            best_match = 0.0
            for sec2 in sections2:
                sim = self.calculate_content_similarity(sec1, sec2)
                best_match = max(best_match, sim)
            weighted_similarities.append(best_match * weight)

        total_weight = sum(self._get_section_weight(sec) for sec in sections1)
        if total_weight == 0:
            return 0.0

        return sum(weighted_similarities) / total_weight
