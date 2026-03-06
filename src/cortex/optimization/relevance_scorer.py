"""
Relevance scoring for intelligent context selection.

This module provides RelevanceScorer to score files and sections based on
relevance to a task description, delegating to keyword, scoring, and parsing helpers.
"""

import hashlib

from cortex.core.dependency_graph import DependencyGraph
from cortex.core.metadata_index import MetadataIndex
from cortex.optimization.models import FileMetadataForScoring, SectionScoreModel
from cortex.optimization.relevance_keywords import extract_keywords as _extract_keywords
from cortex.optimization.relevance_scoring import (
    calculate_keyword_score as _calculate_keyword_score,
)
from cortex.optimization.relevance_scoring import (
    calculate_keyword_scores_for_files as _calculate_keyword_scores_for_files,
)
from cortex.optimization.relevance_scoring import (
    calculate_recency_score as _calculate_recency_score,
)
from cortex.optimization.relevance_scoring import (
    calculate_recency_scores_for_files as _calculate_recency_scores_for_files,
)
from cortex.optimization.relevance_scoring import (
    compute_dependency_scores as _compute_dependency_scores,
)
from cortex.optimization.relevance_scoring import (
    parse_sections as _parse_sections,
)


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
        self.dependency_graph: DependencyGraph = dependency_graph
        self.metadata_index: MetadataIndex = metadata_index
        self.keyword_weight: float = keyword_weight
        self.dependency_weight: float = dependency_weight
        self.recency_weight: float = recency_weight
        self.quality_weight: float = quality_weight
        self._dependency_score_cache: dict[str, dict[str, float]] = {}

    async def score_files(
        self,
        task_description: str,
        files_content: dict[str, str],
        files_metadata: dict[str, FileMetadataForScoring],
        quality_scores: dict[str, float] | None = None,
    ) -> dict[str, dict[str, float | str]]:
        """Score files by relevance to task."""
        if not files_content:
            return {}

        task_keywords = self.extract_keywords(task_description)
        keyword_scores = _calculate_keyword_scores_for_files(
            task_keywords, files_content
        )
        dependency_scores = self.calculate_dependency_scores(keyword_scores)
        recency_scores = _calculate_recency_scores_for_files(files_metadata)
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
        """Score sections within a file."""
        task_keywords = self.extract_keywords(task_description)
        sections = self.parse_sections(content)
        results: list[SectionScoreModel] = []

        for section_name, section_content in sections.items():
            score = self.calculate_keyword_score(task_keywords, section_content)
            content_lower = section_content.lower()
            matching_keywords = [kw for kw in task_keywords if kw in content_lower]
            reason = (
                f"Contains keywords: {', '.join(repr(kw) for kw in matching_keywords[:3])}"
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
        results.sort(key=lambda x: x.score, reverse=True)
        return results

    def extract_keywords(self, text: str) -> list[str]:
        """Extract important keywords from text (lowercased)."""
        return _extract_keywords(text)

    def calculate_keyword_score(self, task_keywords: list[str], content: str) -> float:
        """Calculate TF-IDF based keyword score (0.0–1.0)."""
        return _calculate_keyword_score(task_keywords, content)

    def calculate_dependency_scores(
        self, keyword_scores: dict[str, float]
    ) -> dict[str, float]:
        """Boost score based on dependencies of high-scoring files; uses caching."""
        cache_key = self._compute_keyword_scores_hash(keyword_scores)
        if cache_key in self._dependency_score_cache:
            return self._dependency_score_cache[cache_key]
        dependency_scores = _compute_dependency_scores(
            keyword_scores, self.dependency_graph
        )
        self._dependency_score_cache[cache_key] = dependency_scores
        if len(self._dependency_score_cache) > 100:
            oldest_key = next(iter(self._dependency_score_cache))
            del self._dependency_score_cache[oldest_key]
        return dependency_scores

    def calculate_recency_score(self, metadata: FileMetadataForScoring) -> float:
        """Score based on how recently the file was modified (0.0–1.0)."""
        return _calculate_recency_score(metadata)

    def parse_sections(self, content: str) -> dict[str, str]:
        """Parse markdown sections from content."""
        return _parse_sections(content)

    def _compute_keyword_scores_hash(self, keyword_scores: dict[str, float]) -> str:
        """Compute hash of keyword scores for cache key."""
        sorted_items = sorted(keyword_scores.items())
        rounded_items = [(k, round(v, 3)) for k, v in sorted_items]
        return hashlib.sha256(str(rounded_items).encode()).hexdigest()

    def _normalize_quality_scores(
        self, quality_scores: dict[str, float] | None
    ) -> dict[str, float]:
        """Normalize quality scores if provided."""
        if not quality_scores:
            return {}
        max_quality = max(quality_scores.values()) if quality_scores.values() else 1.0
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
        """Combine all scores into final results per file."""
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
        """Build score result dict for a single file."""
        keyword_score = keyword_scores.get(file_name, 0.0)
        dependency_score = dependency_scores.get(file_name, 0.0)
        recency_score = recency_scores.get(file_name, 0.0)
        quality_score = normalized_quality.get(file_name, 0.5)
        total_score = (
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
        """Generate reason string for score."""
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
