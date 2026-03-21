"""Similarity detection algorithms for health-check analysis."""

import re

from cortex.core.token_counter import TokenCounter
from cortex.health_check.similarity_core import SimilarityCore
from cortex.health_check.similarity_stop_words import get_stop_words


class SimilarityEngine(SimilarityCore):
    """Engine for calculating similarity between files."""

    def __init__(
        self,
        token_counter: TokenCounter | None = None,
        high_threshold: float = 0.75,
        medium_threshold: float = 0.60,
        min_content_length: int = 100,
        heading_weight: float = 1.5,
        code_weight: float = 1.2,
        text_weight: float = 1.0,
    ):
        """Initialize similarity engine.

        Args:
            token_counter: Token counter instance. If None, creates new one.
            high_threshold: High confidence similarity threshold (default: 0.75)
            medium_threshold: Medium confidence similarity threshold (default: 0.60)
            min_content_length: Minimum content length in tokens for
            analysis (default: 100)
            heading_weight: Weight for heading sections (default: 1.5)
            code_weight: Weight for code sections (default: 1.2)
            text_weight: Weight for text sections (default: 1.0)
        """
        super().__init__(
            token_counter=token_counter,
            min_content_length=min_content_length,
            heading_weight=heading_weight,
            code_weight=code_weight,
            text_weight=text_weight,
        )
        self.high_threshold = high_threshold
        self.medium_threshold = medium_threshold

    def _keyword_similarity(self, content1: str, content2: str) -> float:
        """Calculate keyword-based similarity."""
        keywords1 = self._extract_keywords(content1)
        keywords2 = self._extract_keywords(content2)

        if not keywords1 and not keywords2:
            return 1.0
        if not keywords1 or not keywords2:
            return 0.0

        intersection = len(set(keywords1) & set(keywords2))
        union = len(set(keywords1) | set(keywords2))

        return intersection / union if union > 0 else 0.0

    def _extract_keywords(self, content: str) -> list[str]:
        """Extract keywords from content."""
        words = re.findall(r"\b[a-z0-9][-a-z0-9]*\b", content.lower())
        stop_words = get_stop_words()
        return [w for w in words if w not in stop_words and len(w) > 2]

    def _topic_similarity(self, content1: str, content2: str) -> float:
        """Calculate topic similarity using word frequency."""
        vec1 = self._vectorize_content(content1)
        vec2 = self._vectorize_content(content2)

        if not vec1 or not vec2:
            return 0.0

        all_words = set(vec1.keys()) | set(vec2.keys())
        if not all_words:
            return 1.0

        similarities: list[float] = []
        for word in all_words:
            freq1 = vec1.get(word, 0)
            freq2 = vec2.get(word, 0)
            max_freq = max(freq1, freq2)
            if max_freq > 0:
                similarities.append(min(freq1, freq2) / max_freq)

        return sum(similarities) / len(similarities) if similarities else 0.0

    def _intent_similarity(self, content1: str, content2: str) -> float:
        """Calculate intent similarity using pattern matching."""
        intents1 = self._extract_intents(content1)
        intents2 = self._extract_intents(content2)

        if not intents1 and not intents2:
            return 1.0
        if not intents1 or not intents2:
            return 0.0

        intersection = len(set(intents1) & set(intents2))
        union = len(set(intents1) | set(intents2))

        return intersection / union if union > 0 else 0.0

    def _extract_intents(self, content: str) -> list[str]:
        """Extract intent patterns from content."""
        intents: list[str] = []
        content_lower = content.lower()

        intent_patterns = [
            ("analyze", "analysis"),
            ("validate", "validation"),
            ("check", "checking"),
            ("create", "creation"),
            ("update", "updating"),
            ("delete", "deletion"),
            ("read", "reading"),
            ("write", "writing"),
            ("execute", "execution"),
            ("process", "processing"),
        ]

        for pattern, _ in intent_patterns:
            if pattern in content_lower:
                intents.append(pattern)

        return intents

    def _parameter_overlap(
        self, params1: list[str] | None, params2: list[str] | None
    ) -> float | None:
        """Calculate parameter overlap similarity."""
        if params1 is None or params2 is None:
            return None

        if not params1 and not params2:
            return 1.0
        if not params1 or not params2:
            return 0.0

        set1 = {p.lower().strip() for p in params1}
        set2 = {p.lower().strip() for p in params2}

        intersection = len(set1 & set2)
        union = len(set1 | set2)

        return intersection / union if union > 0 else 0.0

    def _return_type_similarity(
        self, return_type1: str | None, return_type2: str | None
    ) -> float | None:
        """Calculate return type similarity."""
        if return_type1 is None or return_type2 is None:
            return None

        if return_type1.lower() == return_type2.lower():
            return 1.0

        type_mappings = {
            "str": "string",
            "int": "integer",
            "float": "number",
            "bool": "boolean",
            "list": "array",
            "dict": "object",
        }

        norm1 = type_mappings.get(return_type1.lower(), return_type1.lower())
        norm2 = type_mappings.get(return_type2.lower(), return_type2.lower())

        return 1.0 if norm1 == norm2 else 0.0

    def _usage_pattern_similarity(
        self, pattern1: str | None, pattern2: str | None
    ) -> float | None:
        """Calculate usage pattern similarity."""
        if pattern1 is None or pattern2 is None:
            return None

        if not pattern1 and not pattern2:
            return 1.0
        if not pattern1 or not pattern2:
            return 0.0

        return self._jaccard_similarity(pattern1, pattern2)

    def calculate_semantic_similarity(self, content1: str, content2: str) -> float:
        """Calculate semantic similarity using keyword and topic analysis.

        Args:
            content1: First content to compare
            content2: Second content to compare

        Returns:
            Semantic similarity score between 0.0 and 1.0
        """
        if not content1 or not content2:
            return 0.0

        keyword_sim = self._keyword_similarity(content1, content2)
        topic_sim = self._topic_similarity(content1, content2)
        intent_sim = self._intent_similarity(content1, content2)

        return (keyword_sim * 0.5) + (topic_sim * 0.3) + (intent_sim * 0.2)

    def calculate_functional_similarity(
        self,
        params1: list[str] | None = None,
        params2: list[str] | None = None,
        return_type1: str | None = None,
        return_type2: str | None = None,
        usage_pattern1: str | None = None,
        usage_pattern2: str | None = None,
    ) -> float:
        """Calculate functional similarity between functions/tools.

        Args:
            params1: Parameters from first function
            params2: Parameters from second function
            return_type1: Return type from first function
            return_type2: Return type from second function
            usage_pattern1: Usage pattern from first function
            usage_pattern2: Usage pattern from second function

        Returns:
            Functional similarity score between 0.0 and 1.0
        """
        param_sim = self._parameter_overlap(params1, params2)
        return_sim = self._return_type_similarity(return_type1, return_type2)
        usage_sim = self._usage_pattern_similarity(usage_pattern1, usage_pattern2)

        weights = [0.4, 0.3, 0.3]
        scores = [param_sim, return_sim, usage_sim]
        valid_scores = [s for s in scores if s is not None]
        valid_weights = [
            w for w, s in zip(weights, scores, strict=False) if s is not None
        ]

        if not valid_scores:
            return 0.0

        total_weight = sum(valid_weights)
        if total_weight == 0:
            return 0.0

        weighted_sum = sum(
            s * w for s, w in zip(valid_scores, valid_weights, strict=False)
        )
        return weighted_sum / total_weight
