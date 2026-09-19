# ruff: noqa: I001
"""
Content summarization for token usage reduction.

This module provides functionality to generate summaries of content
to reduce token usage while preserving key information.
"""

from pathlib import Path

from pydantic import ConfigDict

from cortex.core.cache_utils import CacheType
from cortex.core.metadata_index import MetadataIndex
from cortex.core.models import ModelDict
from cortex.core.path_resolver import get_cache_path
from cortex.core.token_counter import TokenCounter
from cortex.optimization.models import (
    DroppedSection,
    DropReason,
    OptimizationBaseModel,
    ParsedSectionModel,
    SummarizationResultModel,
)
from cortex.optimization.summarization_engine_cache import (
    cache_result_async,
    compute_content_hash,
    compute_variant_hash,
    get_cached_result,
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
from cortex.optimization.section_scorer import HeuristicSectionScorer, SectionScorer
from cortex.optimization.summarization_engine_sections import (
    parse_sections,
    passthrough_unsectioned,
    reconstruct_content,
    score_all_sections,
    select_sections_by_budget,
)


class _SummaryRequest(OptimizationBaseModel):
    """Inputs and cache identity for one generated summary.

    # AI: bundled rather than passed as eight positional parameters so the
    # cache-identity fields (content_hash + variant_hash) travel together and
    # cannot be silently reordered at a call site.
    """

    model_config = ConfigDict(frozen=True)

    file_name: str
    content: str
    target_reduction: float
    strategy: str
    strategy_effective: str
    content_hash: str
    variant_hash: str
    original_tokens: int
    target_tokens: int


class SummarizationEngine:
    """Generate summaries to reduce token usage."""

    def __init__(
        self,
        token_counter: TokenCounter,
        metadata_index: MetadataIndex,
        cache_dir: Path | None = None,
        section_scorer: SectionScorer | None = None,
    ):
        """
        Initialize summarization engine.

        Args:
            token_counter: Token counter for tracking
            metadata_index: Metadata index for file information
            cache_dir: Optional directory for summary cache
            section_scorer: Section relevance scorer; defaults to the
                built-in keyword/length heuristic
        """
        self.token_counter: TokenCounter = token_counter
        self.metadata_index: MetadataIndex = metadata_index
        self.cache_dir: Path = cache_dir or get_cache_path(
            Path(metadata_index.project_root), CacheType.SUMMARIES.value
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.section_scorer: SectionScorer = section_scorer or HeuristicSectionScorer()

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
            self._build_request(
                file_name, content, target_reduction, strategy, strategy_effective
            )
        )

    def _build_request(
        self,
        file_name: str,
        content: str,
        target_reduction: float,
        strategy: str,
        strategy_effective: str,
    ) -> _SummaryRequest:
        """Resolve the content hash, variant hash and token budget once."""
        original_tokens = self.token_counter.count_tokens(content)
        target_tokens = int(original_tokens * (1 - target_reduction))
        return _SummaryRequest(
            file_name=file_name,
            content=content,
            target_reduction=target_reduction,
            strategy=strategy,
            strategy_effective=strategy_effective,
            content_hash=compute_content_hash(content),
            # AI: target_tokens (not the raw target_reduction ratio) is what
            # actually drives section selection -- two ratios that are equal
            # up to rounding can still floor to different integer budgets on
            # large content, so the cache key uses the budget itself.
            variant_hash=compute_variant_hash(
                strategy_effective, target_tokens, self.section_scorer.identity
            ),
            original_tokens=original_tokens,
            target_tokens=target_tokens,
        )

    def _normalize_strategy(self, strategy: str) -> str:
        """Normalize strategy to valid value."""
        valid_strategies = {
            "extract_key_sections",
            "compress_verbose",
            "headers_only",
        }
        return strategy if strategy in valid_strategies else "extract_key_sections"

    async def _summarize_with_cache(self, request: _SummaryRequest) -> ModelDict:
        """Serve a matching cache entry, else generate and store a new one."""
        cached_result = self._check_cache_and_return(
            request.file_name,
            request.content_hash,
            request.strategy_effective,
            request.variant_hash,
            request.original_tokens,
        )
        if cached_result:
            return result_to_legacy_dict(
                cached_result, cached=True, strategy_used=request.strategy
            )
        return await self._generate_and_cache_summary(request)

    async def _generate_and_cache_summary(self, request: _SummaryRequest) -> ModelDict:
        """Generate summary and cache it."""
        target_tokens = request.target_tokens
        summary, kept, removed, dropped = await self._generate_summary_by_strategy(
            request.content,
            target_tokens,
            request.target_reduction,
            request.strategy_effective,
        )
        await cache_result_async(
            self.cache_dir,
            request.file_name,
            request.content_hash,
            request.strategy_effective,
            request.variant_hash,
            summary,
            sections_kept=kept,
            sections_removed=removed,
            dropped_sections=dropped,
        )
        result = build_summary_result(
            request.original_tokens,
            self.token_counter.count_tokens(summary),
            summary,
            request.strategy_effective,
            sections_kept=kept,
            sections_removed=removed,
            dropped_sections=dropped,
        )
        return result_to_legacy_dict(
            result, cached=False, strategy_used=request.strategy
        )

    async def extract_key_sections(self, content: str, target_tokens: int) -> str:
        """
        Extract only the most important sections.

        Args:
            content: Full content
            target_tokens: Target token count

        Returns:
            Summarized content with key sections
        """
        summary, _, _, _ = await self._extract_key_sections_detailed(
            content, target_tokens
        )
        return summary

    async def _extract_key_sections_detailed(
        self, content: str, target_tokens: int
    ) -> tuple[str, int, int, list[DroppedSection]]:
        """Extract key sections, also reporting which sections were dropped."""
        sections, has_heading = parse_sections(content)

        # AI: headerless content still yields one synthetic "preamble" section,
        # so `not sections` alone never fires for plain prose. Reconstructing it
        # would re-emit the body verbatim with nothing else to select between,
        # so it takes the same pass-through path as no sections at all.
        # `has_heading` (not the section's name) decides this -- a real
        # document whose sole heading is literally "# preamble" still has one
        # countable section and must not be treated as headerless.
        if not sections or not has_heading:
            return passthrough_unsectioned(content), 0, 0, []

        section_scores = score_all_sections(
            sections, self.token_counter, self.section_scorer
        )
        section_scores.sort(key=lambda section: section.score, reverse=True)

        selected, dropped = select_sections_by_budget(section_scores, target_tokens)
        # AI: selection ranks by score, but the document's own order carries
        # meaning -- restore source order before replaying kept sections and
        # naming drops, so the summary reads like the original narrative
        # instead of a ranked digest.
        selected_in_order = sorted(selected, key=lambda section: section.index)
        dropped_in_order = sorted(dropped, key=lambda section: section.index)
        dropped_sections = [
            DroppedSection(
                name=s.name,
                score=s.score,
                tokens=s.tokens,
                reason=DropReason.BUDGET_EXCEEDED,
            )
            for s in dropped_in_order
        ]
        return (
            reconstruct_content(selected_in_order, dropped_in_order),
            len(selected),
            len(dropped),
            dropped_sections,
        )

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

    def parse_sections(self, content: str) -> list[ParsedSectionModel]:
        """
        Parse markdown sections from content.

        Args:
            content: Markdown content

        Returns:
            Ordered list of verbatim section slices (position-identified,
            not name-identified -- see the module-level `parse_sections`).
        """
        sections, _ = parse_sections(content)
        return sections

    def score_section_importance(self, section_name: str, content: str) -> float:
        """
        Score section importance.

        Args:
            section_name: Section name
            content: Section content

        Returns:
            Importance score (0.0 - 1.0)
        """
        return self.section_scorer.score(section_name, content)

    def compute_hash(self, content: str) -> str:
        """Compute hash of content."""
        return compute_content_hash(content)

    def _check_cache_and_return(
        self,
        file_name: str,
        content_hash: str,
        strategy: str,
        variant_hash: str,
        original_tokens: int,
    ) -> SummarizationResultModel | None:
        """Check cache and return cached result (with full provenance) if hit."""
        cached = get_cached_result(
            self.cache_dir, file_name, content_hash, strategy, variant_hash
        )
        if cached is None:
            return None

        summarized_tokens = self.token_counter.count_tokens(cached.summary)
        return build_summary_result(
            original_tokens,
            summarized_tokens,
            cached.summary,
            strategy,
            sections_kept=cached.sections_kept,
            sections_removed=cached.sections_removed,
            dropped_sections=cached.dropped_sections,
        )

    async def _generate_summary_by_strategy(
        self,
        content: str,
        target_tokens: int,
        target_reduction: float,
        strategy: str,
    ) -> tuple[str, int, int, list[DroppedSection]]:
        """Generate summary based on strategy, with section provenance if any."""
        if strategy == "extract_key_sections":
            return await self._extract_key_sections_detailed(content, target_tokens)
        if strategy == "compress_verbose":
            summary = await self.compress_verbose_content(content, target_reduction)
            return summary, 0, 0, []
        if strategy == "headers_only":
            summary = await self.extract_headers_only(content)
            return summary, 0, 0, []
        # Default to key sections
        return await self._extract_key_sections_detailed(content, target_tokens)
