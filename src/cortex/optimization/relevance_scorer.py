"""
Relevance scoring for intelligent context selection.

This module provides functionality to score files and sections based on their
relevance to a given task description, using multiple scoring algorithms.
"""

import hashlib
import math
import re
from datetime import datetime

from cortex.core.dependency_graph import DependencyGraph
from cortex.core.metadata_index import MetadataIndex
from cortex.optimization.models import FileMetadataForScoring, SectionScoreModel


class RelevanceScorer:
    """Score content relevance for context selection."""

    def __init__(
        self,
        dependency_graph: DependencyGraph,
        metadata_index: MetadataIndex,
        keyword_weight: float = 0.4,
        dependency_weight: float = 0.3,
        recency_weight: float = 0.2,
        quality_weight: float = 0.1,
    ):
        """
        Initialize relevance scorer.

        Args:
            dependency_graph: Dependency graph for relationship analysis
            metadata_index: Metadata index for file information
            keyword_weight: Weight for keyword matching score (default: 0.4)
            dependency_weight: Weight for dependency-based score (default: 0.3)
            recency_weight: Weight for recency score (default: 0.2)
            quality_weight: Weight for quality score (default: 0.1)
        """
        self.dependency_graph: DependencyGraph = dependency_graph
        self.metadata_index: MetadataIndex = metadata_index
        self.keyword_weight: float = keyword_weight
        self.dependency_weight: float = dependency_weight
        self.recency_weight: float = recency_weight
        self.quality_weight: float = quality_weight

        # Cache for dependency score computation
        self._dependency_score_cache: dict[str, dict[str, float]] = {}

    async def score_files(
        self,
        task_description: str,
        files_content: dict[str, str],
        files_metadata: dict[str, FileMetadataForScoring],
        quality_scores: dict[str, float] | None = None,
    ) -> dict[str, dict[str, float | str]]:
        """
        Score files by relevance to task.

        Args:
            task_description: Description of the task
            files_content: Dict mapping file names to content
            files_metadata: Dict mapping file names to metadata
            quality_scores: Optional dict mapping file names to quality scores (0-1)

        Returns:
            {
                "file_name": {
                    "total_score": 0.85,
                    "keyword_score": 0.90,
                    "dependency_score": 0.75,
                    "recency_score": 0.80,
                    "quality_score": 0.95,
                    "reason": "High keyword match, recent update"
                },
                ...
            }
        """
        if not files_content:
            return {}

        task_keywords = self.extract_keywords(task_description)
        keyword_scores = self._calculate_keyword_scores_for_files(
            task_keywords, files_content
        )
        dependency_scores = self.calculate_dependency_scores(keyword_scores)
        recency_scores = self._calculate_recency_scores_for_files(files_metadata)
        normalized_quality = self._normalize_quality_scores(quality_scores)

        return self._combine_scores_into_results(
            list(files_content.keys()),
            keyword_scores,
            dependency_scores,
            recency_scores,
            normalized_quality,
        )

    async def score_sections(
        self, task_description: str, file_name: str, content: str
    ) -> list[SectionScoreModel]:
        """
        Score sections within a file.

        Args:
            task_description: Description of the task
            file_name: Name of the file
            content: File content

        Returns:
            [
                {
                    "section": "Goals",
                    "score": 0.90,
                    "reason": "Contains keywords: 'build', 'system'"
                },
                ...
            ]
        """
        # Extract keywords from task description
        task_keywords: list[str] = self.extract_keywords(task_description)

        # Parse sections
        sections: dict[str, str] = self.parse_sections(content)

        results: list[SectionScoreModel] = []
        for section_name, section_content in sections.items():
            # Calculate keyword score for section
            score = self.calculate_keyword_score(task_keywords, section_content)

            # Find matching keywords
            content_lower = section_content.lower()
            matching_keywords: list[str] = [
                kw for kw in task_keywords if kw in content_lower
            ]

            reason: str = (
                (
                    f"Contains keywords: "
                    f"{', '.join(repr(kw) for kw in matching_keywords[:3])}"
                )
                if matching_keywords
                else "No keyword matches"
            )

            results.append(
                SectionScoreModel(
                    section=section_name,
                    title=section_name,
                    score=round(score, 3),
                    reason=reason,
                )
            )

        # Sort by score descending
        results.sort(key=lambda x: x.score, reverse=True)

        return results

    def extract_keywords(self, text: str) -> list[str]:
        """
        Extract important keywords from text.

        Args:
            text: Input text

        Returns:
            List of keywords (lowercased)
        """
        text_lower = text.lower()
        words = self._extract_words_from_text(text_lower)
        keywords = self._filter_stop_words_and_short(words)
        return self._deduplicate_keywords(keywords)

    def _calculate_keyword_scores_for_files(
        self, task_keywords: list[str], files_content: dict[str, str]
    ) -> dict[str, float]:
        """Calculate keyword scores for all files.

        Args:
            task_keywords: Keywords extracted from task description
            files_content: Dict mapping file names to content

        Returns:
            Dict mapping file names to keyword scores
        """
        keyword_scores: dict[str, float] = {}
        for file_name, content in files_content.items():
            keyword_scores[file_name] = self.calculate_keyword_score(
                task_keywords, content
            )
        return keyword_scores

    def _calculate_recency_scores_for_files(
        self, files_metadata: dict[str, FileMetadataForScoring]
    ) -> dict[str, float]:
        """Calculate recency scores for all files.

        Args:
            files_metadata: Dict mapping file names to metadata

        Returns:
            Dict mapping file names to recency scores
        """
        recency_scores: dict[str, float] = {}
        for file_name, metadata in files_metadata.items():
            recency_scores[file_name] = self.calculate_recency_score(metadata)
        return recency_scores

    def _normalize_quality_scores(
        self, quality_scores: dict[str, float] | None
    ) -> dict[str, float]:
        """Normalize quality scores if provided.

        Args:
            quality_scores: Optional dict mapping file names to quality scores

        Returns:
            Normalized quality scores dict
        """
        if not quality_scores:
            return {}
        max_quality: float = (
            max(quality_scores.values()) if quality_scores.values() else 1.0
        )
        if max_quality > 1.0:
            return {k: v / max_quality for k, v in quality_scores.items()}
        return quality_scores

    def _combine_scores_into_results(
        self,
        file_names: list[str],
        keyword_scores: dict[str, float],
        dependency_scores: dict[str, float],
        recency_scores: dict[str, float],
        normalized_quality: dict[str, float],
    ) -> dict[str, dict[str, float | str]]:
        """Combine all scores into final results.

        Args:
            file_names: List of file names to score
            keyword_scores: Dict mapping file names to keyword scores
            dependency_scores: Dict mapping file names to dependency scores
            recency_scores: Dict mapping file names to recency scores
            normalized_quality: Dict mapping file names to quality scores

        Returns:
            Dict mapping file names to score results
        """
        results: dict[str, dict[str, float | str]] = {}
        for file_name in file_names:
            results[file_name] = self._calculate_file_score_result(
                file_name,
                keyword_scores,
                dependency_scores,
                recency_scores,
                normalized_quality,
            )
        return results

    def _calculate_file_score_result(
        self,
        file_name: str,
        keyword_scores: dict[str, float],
        dependency_scores: dict[str, float],
        recency_scores: dict[str, float],
        normalized_quality: dict[str, float],
    ) -> dict[str, float | str]:
        """Calculate score result for a single file."""
        keyword_score: float = keyword_scores.get(file_name, 0.0)
        dependency_score: float = dependency_scores.get(file_name, 0.0)
        recency_score: float = recency_scores.get(file_name, 0.0)
        quality_score: float = normalized_quality.get(file_name, 0.5)

        total_score: float = (
            self.keyword_weight * keyword_score
            + self.dependency_weight * dependency_score
            + self.recency_weight * recency_score
            + self.quality_weight * quality_score
        )

        reason = self._generate_score_reason(
            keyword_score, dependency_score, recency_score, quality_score
        )

        return {
            "total_score": round(total_score, 3),
            "keyword_score": round(keyword_score, 3),
            "dependency_score": round(dependency_score, 3),
            "recency_score": round(recency_score, 3),
            "quality_score": round(quality_score, 3),
            "reason": reason,
        }

    def _generate_score_reason(
        self,
        keyword_score: float,
        dependency_score: float,
        recency_score: float,
        quality_score: float,
    ) -> str:
        """Generate reason string for score.

        Args:
            keyword_score: Keyword matching score
            dependency_score: Dependency score
            recency_score: Recency score
            quality_score: Quality score

        Returns:
            Reason string describing why file scored as it did
        """
        reasons: list[str] = []
        if keyword_score > 0.7:
            reasons.append("high keyword match")
        if dependency_score > 0.7:
            reasons.append("important dependency")
        if recency_score > 0.7:
            reasons.append("recently updated")
        if quality_score > 0.8:
            reasons.append("high quality")
        return ", ".join(reasons) if reasons else "moderate relevance"

    def _extract_words_from_text(self, text_lower: str) -> list[str]:
        """Extract words from lowercase text.

        Args:
            text_lower: Lowercase text

        Returns:
            List of extracted words
        """
        return re.findall(r"\b[a-z0-9][-a-z0-9]*\b", text_lower)

    def _filter_stop_words_and_short(self, words: list[str]) -> list[str]:
        """Filter stop words and short words.

        Args:
            words: List of words

        Returns:
            Filtered keywords
        """
        stop_words = self._get_stop_words()
        return [w for w in words if w not in stop_words and len(w) > 2]

    def _get_stop_words(self) -> set[str]:
        """Get set of common stop words.

        Returns:
            Set of stop words
        """
        return _STOP_WORDS

    def _deduplicate_keywords(self, keywords: list[str]) -> list[str]:
        """Deduplicate keywords while maintaining order.

        Args:
            keywords: List of keywords

        Returns:
            Deduplicated keywords
        """
        seen: set[str] = set()
        unique_keywords: list[str] = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                unique_keywords.append(kw)
        return unique_keywords

    def calculate_keyword_score(self, task_keywords: list[str], content: str) -> float:
        """
        Calculate TF-IDF based keyword score.

        Args:
            task_keywords: Keywords from task description
            content: File or section content

        Returns:
            Score between 0.0 and 1.0
        """
        if not task_keywords or not content:
            return 0.0

        content_lower: str = content.lower()

        # Count keyword occurrences
        keyword_counts: dict[str, int] = {}
        for keyword in task_keywords:
            keyword_counts[keyword] = content_lower.count(keyword)

        # Calculate TF (term frequency)
        total_words = len(content_lower.split())
        if total_words == 0:
            return 0.0

        tf_scores: dict[str, float] = {
            kw: count / total_words for kw, count in keyword_counts.items()
        }

        # Simple IDF approximation: boost earlier keywords
        idf_scores: dict[str, float] = {}
        for i, kw in enumerate(task_keywords):
            # Earlier keywords are more important
            idf_scores[kw] = 1.0 / (1.0 + math.log(1 + i))

        # Combine TF-IDF
        tfidf_scores: dict[str, float] = {
            kw: tf_scores[kw] * idf_scores[kw] for kw in task_keywords
        }

        # Aggregate score
        total_tfidf: float = sum(tfidf_scores.values())

        # Normalize to 0-1 range
        # Use sigmoid-like function to map scores
        score = 1.0 - math.exp(-total_tfidf * 100)

        return min(score, 1.0)

    def calculate_dependency_scores(
        self, keyword_scores: dict[str, float]
    ) -> dict[str, float]:
        """
        Boost score based on dependencies of high-scoring files.

        Files that are dependencies of high-scoring files get boosted.

        Performance: Uses caching to avoid redundant computation.
        Cache invalidation occurs when keyword_scores change.

        Args:
            keyword_scores: Keyword scores for all files

        Returns:
            Dependency scores for all files
        """
        # Generate cache key from keyword scores
        cache_key = self._compute_keyword_scores_hash(keyword_scores)

        # Check cache
        if cache_key in self._dependency_score_cache:
            return self._dependency_score_cache[cache_key]

        # Compute dependency scores
        dependency_scores = self._compute_dependency_scores(keyword_scores)

        # Cache result
        self._dependency_score_cache[cache_key] = dependency_scores

        # Limit cache size to avoid memory growth
        if len(self._dependency_score_cache) > 100:
            # Remove oldest entry (FIFO)
            oldest_key = next(iter(self._dependency_score_cache))
            del self._dependency_score_cache[oldest_key]

        return dependency_scores

    def _compute_keyword_scores_hash(self, keyword_scores: dict[str, float]) -> str:
        """Compute hash of keyword scores for cache key.

        Args:
            keyword_scores: Keyword scores dictionary

        Returns:
            SHA-256 hash as hex string
        """
        # Sort keys for consistent hashing
        sorted_items = sorted(keyword_scores.items())
        # Round scores to 3 decimal places for caching
        rounded_items = [(k, round(v, 3)) for k, v in sorted_items]
        # Convert to string representation
        data_str = str(rounded_items)
        # Hash it
        return hashlib.sha256(data_str.encode()).hexdigest()

    def _compute_dependency_scores(
        self, keyword_scores: dict[str, float]
    ) -> dict[str, float]:
        """Compute dependency scores without caching.

        Performance: O(files × dependencies_per_file).
        This is the core computation that gets cached.

        Args:
            keyword_scores: Keyword scores for all files

        Returns:
            Dependency scores for all files
        """
        dependency_scores: dict[str, float] = {
            file_name: 0.0 for file_name in keyword_scores.keys()
        }

        # For each file, boost its dependencies
        for file_name, keyword_score in keyword_scores.items():
            if keyword_score < 0.3:
                continue  # Skip low-scoring files

            # Get dependencies
            deps: list[str] = self.dependency_graph.get_dependencies(file_name)

            # Boost each dependency
            boost = keyword_score * 0.7  # 70% of the score transfers
            for dep in deps:
                if dep in dependency_scores:
                    dependency_scores[dep] = max(dependency_scores[dep], boost)

        # Also boost files that have high-scoring dependents
        for file_name, keyword_score in keyword_scores.items():
            if keyword_score < 0.3:
                continue

            # Get dependents
            dependents: list[str] = self.dependency_graph.get_dependents(file_name)

            # Boost this file if it has high-scoring dependents
            if dependents:
                boost = keyword_score * 0.5
                dependency_scores[file_name] = max(dependency_scores[file_name], boost)

        return dependency_scores

    def calculate_recency_score(self, metadata: FileMetadataForScoring) -> float:
        """
        Score based on how recently the file was modified.

        Args:
            metadata: File metadata

        Returns:
            Score between 0.0 and 1.0
        """
        last_modified = metadata.last_modified
        if not last_modified:
            return 0.5  # Default to neutral

        try:
            # Parse ISO format timestamp
            last_modified_str: str = str(last_modified)
            modified_time = datetime.fromisoformat(
                last_modified_str.replace("Z", "+00:00")
            )
            now = datetime.now(modified_time.tzinfo)

            # Calculate age in days
            age_days: float = (now - modified_time).total_seconds() / 86400

            # Score function: exponential decay
            # - Files modified today: 1.0
            # - Files modified 30 days ago: ~0.5
            # - Files modified 90+ days ago: < 0.2
            score: float = math.exp(-age_days / 45.0)

            return min(score, 1.0)

        except (ValueError, AttributeError):
            return 0.5  # Default to neutral on error

    def parse_sections(self, content: str) -> dict[str, str]:
        """
        Parse markdown sections from content.

        Args:
            content: Markdown content

        Returns:
            Dict mapping section names to section content
        """
        sections: dict[str, str] = {}
        current_section: str = "preamble"
        current_content: list[str] = []

        lines: list[str] = content.split("\n")

        for line in lines:
            heading_match = None
            # Check for heading
            if line.startswith("#"):
                # Save previous section
                if current_content:
                    sections[current_section] = "\n".join(current_content)

                # Extract heading text
                heading_match = re.match(r"^#+\s+(.+)$", line)
                if heading_match:
                    current_section = heading_match.group(1).strip()
                    current_content = []
            else:
                current_content.append(line)

        # Save last section
        if current_content:
            sections[current_section] = "\n".join(current_content)

        return sections


# Private constants at file level
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
    "was",
    "are",
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
    "i",
    "you",
    "he",
    "she",
    "it",
    "we",
    "they",
    "what",
    "which",
    "who",
    "when",
    "where",
    "why",
    "how",
}
