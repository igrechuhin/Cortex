# ruff: noqa: I001
"""
Content summarization for token usage reduction.

This module provides functionality to generate summaries of content
to reduce token usage while preserving key information.
"""

import hashlib
import json
import re
from pathlib import Path
from typing import cast

from cortex.core.async_file_utils import open_async_text_file
from cortex.core.cache_utils import CacheType
from cortex.core.models import ModelDict
from cortex.core.metadata_index import MetadataIndex
from cortex.core.path_resolver import get_cache_path
from cortex.core.token_counter import TokenCounter
from cortex.optimization.models import (
    ScoredSectionModel,
    SummarizationResultModel,
    SummarizationState,
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
            return self._result_to_legacy_dict(
                self._build_empty_summary_result(strategy_effective),
                cached=False,
                strategy_used=strategy,
            )
        return await self._summarize_with_cache(
            file_name, content, target_reduction, strategy, strategy_effective
        )

    def _normalize_strategy(self, strategy: str) -> str:
        """Normalize strategy to valid value."""
        valid_strategies = {"extract_key_sections", "compress_verbose", "headers_only"}
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
        target_tokens = int(original_tokens * (1 - target_reduction))
        content_hash = self.compute_hash(content)
        cached_result = self._check_cache_and_return(
            file_name, content_hash, strategy_effective, original_tokens
        )
        if cached_result:
            return self._result_to_legacy_dict(
                cached_result,
                cached=True,
                strategy_used=strategy,
            )
        return await self._generate_and_cache_summary(
            file_name,
            content,
            target_tokens,
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
        target_tokens: int,
        target_reduction: float,
        strategy: str,
        strategy_effective: str,
        content_hash: str,
        original_tokens: int,
    ) -> ModelDict:
        """Generate summary and cache it."""
        summary = await self._generate_summary_by_strategy(
            content, target_tokens, target_reduction, strategy_effective
        )
        summarized_tokens = self.token_counter.count_tokens(summary)
        await self.cache_summary(file_name, content_hash, strategy_effective, summary)
        return self._build_final_summary_result(
            original_tokens, summarized_tokens, summary, strategy_effective, strategy
        )

    def _build_final_summary_result(
        self,
        original_tokens: int,
        summarized_tokens: int,
        summary: str,
        strategy_effective: str,
        strategy: str,
    ) -> ModelDict:
        """Build final summary result dictionary."""
        return self._result_to_legacy_dict(
            self._build_summary_result(
                original_tokens,
                summarized_tokens,
                summary,
                strategy_effective,
                cached=False,
            ),
            cached=False,
            strategy_used=strategy,
        )

        return self._result_to_legacy_dict(
            self._build_summary_result(
                original_tokens,
                summarized_tokens,
                summary,
                strategy_effective,
                cached=False,
            ),
            cached=False,
            strategy_used=strategy,
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
        sections = self.parse_sections(content)

        if not sections:
            return _handle_no_sections(content)

        section_scores = _score_all_sections(self, sections, self.token_counter)
        section_scores.sort(key=lambda x: float(x.score), reverse=True)

        selected_sections = _select_sections_by_budget(section_scores, target_tokens)
        return _reconstruct_content(selected_sections, len(section_scores))

    async def compress_verbose_content(
        self,
        content: str,
        target_reduction: float,  # noqa: ARG002
    ) -> str:
        """
        Remove verbose examples and compress repeated info.

        Args:
            content: Full content
            target_reduction: Target reduction ratio

        Returns:
            Compressed content
        """
        lines = content.split("\n")
        result_lines: list[str] = []
        state = SummarizationState()

        for line in lines:
            processed = _process_code_block(line, state, result_lines)
            if processed:
                continue

            processed = _process_example_section(line, state, result_lines)
            if processed:
                continue

            _process_line(line, result_lines)

        return "\n".join(result_lines)

    async def extract_headers_only(self, content: str) -> str:
        """
        Extract only headers and first paragraph of each section.

        Args:
            content: Full content

        Returns:
            Headers and brief descriptions
        """
        lines = content.split("\n")
        result_lines: list[str] = []

        current_section_lines: list[str] = []
        in_section = False

        for line in lines:
            if line.startswith("#"):
                self._finalize_previous_section(
                    in_section, current_section_lines, result_lines
                )
                result_lines.append(line)
                current_section_lines = []
                in_section = True
            elif in_section and line.strip():
                current_section_lines.append(line)

        self._finalize_previous_section(True, current_section_lines, result_lines)

        return "\n".join(result_lines)

    def _finalize_previous_section(
        self,
        in_section: bool,
        current_section_lines: list[str],
        result_lines: list[str],
    ) -> None:
        """Finalize and save previous section if it exists."""
        if not in_section or not current_section_lines:
            return

        result_lines.extend(current_section_lines[:5])
        if len(current_section_lines) > 5:
            result_lines.append("[...]")
        result_lines.append("")

    def parse_sections(self, content: str) -> dict[str, str]:
        """
        Parse markdown sections from content.

        Args:
            content: Markdown content

        Returns:
            Dict mapping section names to content
        """
        sections: dict[str, str] = {}
        current_section = "preamble"
        current_content: list[str] = []

        lines = content.split("\n")

        for line in lines:
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

    def score_section_importance(self, section_name: str, content: str) -> float:
        """
        Score section importance.

        Args:
            section_name: Section name
            content: Section content

        Returns:
            Importance score (0.0 - 1.0)
        """
        score = 0.5  # Base score
        section_lower = section_name.lower()

        score += _calculate_keyword_bonus(section_lower)
        score += _calculate_length_bonus(len(content))

        return max(0.0, min(1.0, score))

    def compute_hash(self, content: str) -> str:
        """Compute hash of content."""
        return hashlib.sha256(content.encode()).hexdigest()[:16]

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
        cache_file = self.cache_dir / f"{file_name}.{strategy}.{content_hash}.json"

        if cache_file.exists():
            try:
                with open(cache_file) as f:
                    data = json.load(f)
                    return data.get("summary")
            except (OSError, json.JSONDecodeError):
                return None

        return None

    async def cache_summary(
        self, file_name: str, content_hash: str, strategy: str, summary: str
    ):
        """
        Cache generated summary.

        Args:
            file_name: File name
            content_hash: Content hash
            strategy: Strategy used
            summary: Generated summary
        """
        cache_file = self.cache_dir / f"{file_name}.{strategy}.{content_hash}.json"

        try:
            async with open_async_text_file(cache_file, "w", "utf-8") as f:
                _ = await f.write(
                    json.dumps(
                        {
                            "file_name": file_name,
                            "content_hash": content_hash,
                            "strategy": strategy,
                            "summary": summary,
                        },
                        indent=2,
                    )
                )
        except OSError:
            pass  # Silently fail on cache write errors

    def _build_empty_summary_result(self, strategy: str) -> SummarizationResultModel:
        """Build result model for empty content."""
        return SummarizationResultModel(
            original_tokens=0,
            summary_tokens=0,
            reduction=0.0,
            summary="",
            strategy=strategy,
            sections_kept=0,
            sections_removed=0,
        )

    def _check_cache_and_return(
        self,
        file_name: str,
        content_hash: str,
        strategy: str,
        original_tokens: int,
    ) -> SummarizationResultModel | None:
        """Check cache and return cached result if available."""
        cached_summary = self.get_cached_summary(file_name, content_hash, strategy)
        if not cached_summary:
            return None

        summarized_tokens = self.token_counter.count_tokens(cached_summary)
        return SummarizationResultModel(
            original_tokens=original_tokens,
            summary_tokens=summarized_tokens,
            reduction=self._calculate_reduction(original_tokens, summarized_tokens),
            summary=cached_summary,
            strategy=strategy,
            sections_kept=0,  # Cache doesn't track sections
            sections_removed=0,
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

    def _build_summary_result(
        self,
        original_tokens: int,
        summarized_tokens: int,
        summary: str,
        strategy: str,
        cached: bool,  # noqa: ARG002
    ) -> SummarizationResultModel:
        """Build summary result model."""
        # Calculate sections kept/removed if possible (simplified for now)
        sections_kept = 0
        sections_removed = 0

        return SummarizationResultModel(
            original_tokens=original_tokens,
            summary_tokens=summarized_tokens,
            reduction=self._calculate_reduction(original_tokens, summarized_tokens),
            summary=summary,
            strategy=strategy,
            sections_kept=sections_kept,
            sections_removed=sections_removed,
        )

    def _result_to_legacy_dict(
        self,
        result: SummarizationResultModel,
        cached: bool,
        strategy_used: str,
    ) -> ModelDict:
        """Convert typed model to legacy dict shape expected by tools/tests."""
        data = cast(ModelDict, result.model_dump(mode="json"))
        data["summarized_tokens"] = data["summary_tokens"]
        data["strategy_used"] = strategy_used
        data["cached"] = cached
        return data

    def _calculate_reduction(
        self, original_tokens: int, summarized_tokens: int
    ) -> float:
        """Calculate reduction percentage."""
        if original_tokens > 0:
            return (original_tokens - summarized_tokens) / original_tokens
        return 0.0


def _calculate_keyword_bonus(section_lower: str) -> float:
    """Calculate bonus/penalty based on section name keywords.

    Args:
        section_lower: Lowercase section name

    Returns:
        Bonus/penalty score adjustment
    """
    important_keywords = [
        "goal",
        "objective",
        "requirement",
        "overview",
        "summary",
        "introduction",
        "problem",
        "solution",
        "status",
        "progress",
    ]

    for keyword in important_keywords:
        if keyword in section_lower:
            return 0.3

    low_value_keywords = [
        "example",
        "reference",
        "appendix",
        "note",
        "detail",
        "history",
    ]

    for keyword in low_value_keywords:
        if keyword in section_lower:
            return -0.2

    return 0.0


def _calculate_length_bonus(content_length: int) -> float:
    """Calculate bonus/penalty based on content length.

    Args:
        content_length: Length of content in characters

    Returns:
        Bonus/penalty score adjustment
    """
    if content_length < 500:
        return 0.1
    elif content_length > 2000:
        return -0.1
    return 0.0


def _handle_no_sections(content: str) -> str:
    """Handle case when no sections are found in content.

    Args:
        content: Full content

    Returns:
        Truncated content with message
    """
    words = content.split()
    truncated_words = words[: int(len(words) * 0.5)]
    return " ".join(truncated_words) + "\n\n[Content truncated...]"


def _score_all_sections(
    engine: SummarizationEngine,
    sections: dict[str, str],
    token_counter: TokenCounter,
) -> list[ScoredSectionModel]:
    """Score all sections by importance.

    Args:
        engine: SummarizationEngine instance
        sections: Dictionary of section names to content
        token_counter: Token counter instance

    Returns:
        List of scored section models
    """
    section_scores: list[ScoredSectionModel] = []

    for section_name, section_content in sections.items():
        score = engine.score_section_importance(section_name, section_content)
        tokens = token_counter.count_tokens(section_content)

        section_scores.append(
            ScoredSectionModel(
                name=section_name,
                content=section_content,
                score=score,
                tokens=tokens,
            )
        )

    return section_scores


def _select_sections_by_budget(
    section_scores: list[ScoredSectionModel], target_tokens: int
) -> list[ScoredSectionModel]:
    """Select sections within token budget.

    Args:
        section_scores: List of scored sections (already sorted)
        target_tokens: Target token count

    Returns:
        List of selected sections
    """
    selected_sections: list[ScoredSectionModel] = []
    total_tokens = 0

    for section in section_scores:
        if total_tokens + section.tokens <= target_tokens:
            selected_sections.append(section)
            total_tokens += section.tokens
        elif not selected_sections:
            # Include at least one section
            selected_sections.append(section)
            break

    return selected_sections


def _reconstruct_content(
    selected_sections: list[ScoredSectionModel], total_sections: int
) -> str:
    """Reconstruct content from selected sections.

    Args:
        selected_sections: List of selected sections
        total_sections: Total number of sections (for omission message)

    Returns:
        Reconstructed content string
    """
    result_parts: list[str] = []

    for section in selected_sections:
        result_parts.append(f"## {section.name}")
        result_parts.append(section.content)
        result_parts.append("")

    if len(selected_sections) < total_sections:
        result_parts.append(
            f"[{total_sections - len(selected_sections)} sections omitted]"
        )

    return "\n".join(result_parts)


def _process_code_block(
    line: str, state: SummarizationState, result_lines: list[str]
) -> bool:
    """Process code block line.

    Args:
        line: Current line
        state: Processing state model
        result_lines: Result lines list

    Returns:
        True if line was processed, False otherwise
    """
    if line.strip().startswith("```"):
        if not state.in_code_block:
            state.in_code_block = True
            state.code_block_lines = [line]
        else:
            state.in_code_block = False
            state.code_block_lines.append(line)

            if len(state.code_block_lines) > 20:
                result_lines.append(state.code_block_lines[0])
                result_lines.append("# ... code omitted ...")
                result_lines.append(state.code_block_lines[-1])
            else:
                result_lines.extend(state.code_block_lines)

            state.code_block_lines = []
        return True

    if state.in_code_block:
        state.code_block_lines.append(line)
        return True

    return False


def _process_example_section(
    line: str, state: SummarizationState, result_lines: list[str]
) -> bool:
    """Process example section line.

    Args:
        line: Current line
        state: Processing state dictionary
        result_lines: Result lines list

    Returns:
        True if line was processed, False otherwise
    """
    if re.match(r"^#+\s+Example", line, re.IGNORECASE):
        state.in_example = True
        result_lines.append(line)
        result_lines.append("[Example omitted]")
        return True

    if state.in_example and line.startswith("#"):
        state.in_example = False
        # Add the new header line when exiting example section
        result_lines.append(line)
        return True

    if state.in_example:
        return True

    return False


def _process_line(line: str, result_lines: list[str]) -> None:
    """Process regular line.

    Args:
        line: Current line
        result_lines: Result lines list
    """
    if len(line) > 500:
        result_lines.append(line[:200] + " ... [truncated]")
    else:
        result_lines.append(line)
