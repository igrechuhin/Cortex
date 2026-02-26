# ruff: noqa: I001
"""
Content summarization for token usage reduction.

This module provides functionality to generate summaries of content
to reduce token usage while preserving key information.
"""

from pathlib import Path

from cortex.core.cache_utils import CacheType
from cortex.core.metadata_index import MetadataIndex
from cortex.core.models import ModelDict
from cortex.core.path_resolver import get_cache_path
from cortex.core.token_counter import TokenCounter
from cortex.optimization.models import SummarizationResultModel
from cortex.optimization.summarization_engine_cache import (
    cache_summary_async,
    compute_content_hash,
    get_cached_summary as _get_cached_summary,
)
from cortex.optimization.summarization_engine_compress import (
    compress_verbose_content as _compress_verbose_content,
    extract_headers_only as _extract_headers_only,
)
from cortex.optimization.summarization_engine_result import (
    build_empty_summary_result,
    build_summary_result,
    result_to_legacy_dict,
)
from cortex.optimization.summarization_engine_sections import (
    handle_no_sections,
    parse_sections,
    reconstruct_content,
    score_all_sections,
    score_section_importance,
    select_sections_by_budget,
)


class SummarizationEngine:
    """Generate summaries to reduce token usage."""

    def __init__(
        self,
        token_counter: TokenCounter,
        metadata_index: MetadataIndex,
        cache_dir: Path | None = None,
    ):
        """
        Initialize summarization engine.

        Args:
            token_counter: Token counter for tracking
            metadata_index: Metadata index for file information
            cache_dir: Optional directory for summary cache
        """
        self.token_counter: TokenCounter = token_counter
        self.metadata_index: MetadataIndex = metadata_index
        self.cache_dir: Path = cache_dir or get_cache_path(
            Path(metadata_index.project_root), CacheType.SUMMARIES.value
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    async def summarize_file(
        self,
        file_name: str,
        content: str,
        target_reduction: float = 0.5,
        strategy: str = "extract_key_sections",
    ) -> ModelDict:
        """
        Summarize file content.

        Args:
            file_name: Name of file
            content: File content
            target_reduction: Target token reduction (0.5 = reduce by 50%)
            strategy: Summarization strategy

        Returns:
            {
                "original_tokens": 10000,
                "summarized_tokens": 5000,
                "reduction": 0.50,
                "summary": "...",
                "strategy_used": "extract_key_sections"
            }
        """
        strategy_effective = self._normalize_strategy(strategy)
        if not content:
            return result_to_legacy_dict(
                build_empty_summary_result(strategy_effective),
                cached=False,
                strategy_used=strategy,
            )
        return await self._summarize_with_cache(
            file_name, content, target_reduction, strategy, strategy_effective
        )

    def _normalize_strategy(self, strategy: str) -> str:
        """Normalize strategy to valid value."""
        valid_strategies = {
            "extract_key_sections",
            "compress_verbose",
            "headers_only",
        }
        return strategy if strategy in valid_strategies else "extract_key_sections"

    async def _summarize_with_cache(
        self,
        file_name: str,
        content: str,
        target_reduction: float,
        strategy: str,
        strategy_effective: str,
    ) -> ModelDict:
        """Summarize file with cache checking."""
        original_tokens = self.token_counter.count_tokens(content)
        content_hash = compute_content_hash(content)
        cached_result = self._check_cache_and_return(
            file_name, content_hash, strategy_effective, original_tokens
        )
        if cached_result:
            return result_to_legacy_dict(
                cached_result, cached=True, strategy_used=strategy
            )
        return await self._generate_and_cache_summary(
            file_name,
            content,
            target_reduction,
            strategy,
            strategy_effective,
            content_hash,
            original_tokens,
        )

    async def _generate_and_cache_summary(
        self,
        file_name: str,
        content: str,
        target_reduction: float,
        strategy: str,
        strategy_effective: str,
        content_hash: str,
        original_tokens: int,
    ) -> ModelDict:
        """Generate summary and cache it."""
        target_tokens = int(original_tokens * (1 - target_reduction))
        summary = await self._generate_summary_by_strategy(
            content, target_tokens, target_reduction, strategy_effective
        )
        summarized_tokens = self.token_counter.count_tokens(summary)
        await cache_summary_async(
            self.cache_dir, file_name, content_hash, strategy_effective, summary
        )
        result = build_summary_result(
            original_tokens, summarized_tokens, summary, strategy_effective
        )
        return result_to_legacy_dict(result, cached=False, strategy_used=strategy)

    async def extract_key_sections(self, content: str, target_tokens: int) -> str:
        """
        Extract only the most important sections.

        Args:
            content: Full content
            target_tokens: Target token count

        Returns:
            Summarized content with key sections
        """
        sections = parse_sections(content)

        if not sections:
            return handle_no_sections(content)

        section_scores = score_all_sections(sections, self.token_counter)
        section_scores.sort(key=lambda x: float(x.score), reverse=True)

        selected_sections = select_sections_by_budget(section_scores, target_tokens)
        return reconstruct_content(selected_sections, len(section_scores))

    async def compress_verbose_content(
        self,
        content: str,
        target_reduction: float,
    ) -> str:
        """
        Remove verbose examples and compress repeated info.

        Args:
            content: Full content
            target_reduction: Target reduction ratio

        Returns:
            Compressed content
        """
        return _compress_verbose_content(content)

    async def extract_headers_only(self, content: str) -> str:
        """
        Extract only headers and first paragraph of each section.

        Args:
            content: Full content

        Returns:
            Headers and brief descriptions
        """
        return _extract_headers_only(content)

    def parse_sections(self, content: str) -> dict[str, str]:
        """
        Parse markdown sections from content.

        Args:
            content: Markdown content

        Returns:
            Dict mapping section names to content
        """
        return parse_sections(content)

    def score_section_importance(self, section_name: str, content: str) -> float:
        """
        Score section importance.

        Args:
            section_name: Section name
            content: Section content

        Returns:
            Importance score (0.0 - 1.0)
        """
        return score_section_importance(section_name, content)

    def compute_hash(self, content: str) -> str:
        """Compute hash of content."""
        return compute_content_hash(content)

    def get_cached_summary(
        self, file_name: str, content_hash: str, strategy: str
    ) -> str | None:
        """
        Get cached summary if available.

        Args:
            file_name: File name
            content_hash: Content hash
            strategy: Strategy used

        Returns:
            Cached summary or None
        """
        return _get_cached_summary(self.cache_dir, file_name, content_hash, strategy)

    async def cache_summary(
        self, file_name: str, content_hash: str, strategy: str, summary: str
    ) -> None:
        """
        Cache generated summary.

        Args:
            file_name: File name
            content_hash: Content hash
            strategy: Strategy used
            summary: Generated summary
        """
        await cache_summary_async(
            self.cache_dir, file_name, content_hash, strategy, summary
        )

    def _check_cache_and_return(
        self,
        file_name: str,
        content_hash: str,
        strategy: str,
        original_tokens: int,
    ) -> SummarizationResultModel | None:
        """Check cache and return cached result if available."""
        cached_summary = _get_cached_summary(
            self.cache_dir, file_name, content_hash, strategy
        )
        if not cached_summary:
            return None

        summarized_tokens = self.token_counter.count_tokens(cached_summary)
        return build_summary_result(
            original_tokens, summarized_tokens, cached_summary, strategy
        )

    async def _generate_summary_by_strategy(
        self,
        content: str,
        target_tokens: int,
        target_reduction: float,
        strategy: str,
    ) -> str:
        """Generate summary based on strategy."""
        if strategy == "extract_key_sections":
            return await self.extract_key_sections(content, target_tokens)
        if strategy == "compress_verbose":
            return await self.compress_verbose_content(content, target_reduction)
        if strategy == "headers_only":
            return await self.extract_headers_only(content)
        # Default to key sections
        return await self.extract_key_sections(content, target_tokens)
