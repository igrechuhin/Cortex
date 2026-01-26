"""Similarity detection algorithms for health-check analysis."""

import difflib
import math
import re

from cortex.core.token_counter import TokenCounter


class SimilarityEngine:
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
            min_content_length: Minimum content length in tokens for analysis (default: 100)
            heading_weight: Weight for heading sections (default: 1.5)
            code_weight: Weight for code sections (default: 1.2)
            text_weight: Weight for text sections (default: 1.0)
        """
        self.token_counter = token_counter or TokenCounter()
        self.high_threshold = high_threshold
        self.medium_threshold = medium_threshold
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

        # Check minimum content length
        if not self._meets_min_length(content1, content2):
            return 0.0

        # Use multiple algorithms and average
        token_sim = self._token_similarity(content1, content2)
        text_sim = self._text_similarity(content1, content2)
        jaccard_sim = self._jaccard_similarity(content1, content2)
        cosine_sim = self._cosine_similarity(content1, content2)

        # Weighted average (token and cosine similarity most important)
        return (
            (token_sim * 0.35)
            + (cosine_sim * 0.35)
            + (text_sim * 0.20)
            + (jaccard_sim * 0.10)
        )

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

    def _cosine_similarity(self, content1: str, content2: str) -> float:
        """Calculate cosine similarity for vectorized content.

        Args:
            content1: First content
            content2: Second content

        Returns:
            Cosine similarity score between 0.0 and 1.0
        """
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
        """Vectorize content using word frequency.

        Args:
            content: Content to vectorize

        Returns:
            Dict mapping words to their frequencies
        """
        words = re.findall(r"\b[a-z0-9][-a-z0-9]*\b", content.lower())
        word_counts: dict[str, float] = {}
        for word in words:
            if len(word) > 2:
                word_counts[word] = word_counts.get(word, 0) + 1.0
        return word_counts

    def _meets_min_length(self, content1: str, content2: str) -> bool:
        """Check if content meets minimum length requirement.

        Args:
            content1: First content
            content2: Second content

        Returns:
            True if both contents meet minimum length
        """
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
        """Get weight for section based on type.

        Args:
            section: Section content

        Returns:
            Weight for the section
        """
        if section.strip().startswith("#"):
            return self.heading_weight
        if "```" in section or section.strip().startswith("    "):
            return self.code_weight
        return self.text_weight

    def _keyword_similarity(self, content1: str, content2: str) -> float:
        """Calculate keyword-based similarity.

        Args:
            content1: First content
            content2: Second content

        Returns:
            Keyword similarity score between 0.0 and 1.0
        """
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
        """Extract keywords from content.

        Args:
            content: Content to extract keywords from

        Returns:
            List of keywords
        """
        words = re.findall(r"\b[a-z0-9][-a-z0-9]*\b", content.lower())
        stop_words = _get_stop_words()
        return [w for w in words if w not in stop_words and len(w) > 2]

    def _topic_similarity(self, content1: str, content2: str) -> float:
        """Calculate topic similarity using word frequency.

        Args:
            content1: First content
            content2: Second content

        Returns:
            Topic similarity score between 0.0 and 1.0
        """
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
        """Calculate intent similarity using pattern matching.

        Args:
            content1: First content
            content2: Second content

        Returns:
            Intent similarity score between 0.0 and 1.0
        """
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
        """Extract intent patterns from content.

        Args:
            content: Content to extract intents from

        Returns:
            List of intent patterns
        """
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
        """Calculate parameter overlap similarity.

        Args:
            params1: Parameters from first function
            params2: Parameters from second function

        Returns:
            Parameter similarity score or None if not applicable
        """
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
        """Calculate return type similarity.

        Args:
            return_type1: Return type from first function
            return_type2: Return type from second function

        Returns:
            Return type similarity score or None if not applicable
        """
        if return_type1 is None or return_type2 is None:
            return None

        if return_type1.lower() == return_type2.lower():
            return 1.0

        # Check for compatible types
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
        """Calculate usage pattern similarity.

        Args:
            pattern1: Usage pattern from first function
            pattern2: Usage pattern from second function

        Returns:
            Usage pattern similarity score or None if not applicable
        """
        if pattern1 is None or pattern2 is None:
            return None

        if not pattern1 and not pattern2:
            return 1.0
        if not pattern1 or not pattern2:
            return 0.0

        return self._jaccard_similarity(pattern1, pattern2)

    def calculate_section_similarity(
        self, sections1: list[str], sections2: list[str]
    ) -> float:
        """Calculate similarity between file sections with importance weighting.

        Args:
            sections1: Sections from first file
            sections2: Sections from second file

        Returns:
            Weighted average similarity score between 0.0 and 1.0
        """
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


def _get_stop_words() -> set[str]:
    """Get set of common stop words.

    Returns:
        Set of stop words
    """
    return _STOP_WORDS


# Private constants (file level, at bottom of file)
_STOP_WORDS: set[str] = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "but",
    "in",
    "on",
    "at",
    "to",
    "for",
    "of",
    "with",
    "by",
    "from",
    "as",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "have",
    "has",
    "had",
    "do",
    "does",
    "did",
    "will",
    "would",
    "should",
    "could",
    "may",
    "might",
    "must",
    "can",
    "this",
    "that",
    "these",
    "those",
    "it",
    "its",
    "they",
    "them",
    "their",
    "there",
    "then",
    "than",
}
