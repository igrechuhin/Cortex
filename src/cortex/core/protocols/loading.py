#!/usr/bin/env python3
"""Progressive loading and summarization protocols for MCP Memory Bank.

This module defines Protocol classes (PEP 544) for progressive content loading
and summarization operations.
"""

from pathlib import Path
from typing import Protocol

from cortex.optimization.models import (
    ProgressiveLoadResult,
    SummarizationResultModel,
)


class ProgressiveLoaderProtocol(Protocol):
    """Protocol for progressive context loading operations using structural subtyping (PEP 544).

    This protocol defines the interface for loading Memory Bank context progressively
    based on priority, dependencies, or relevance. Progressive loading enables
    efficient context management within token budgets. A class implementing these
    methods automatically satisfies this protocol.

    Used by:
        - ProgressiveLoader: Loads context using multiple strategies
        - ContextOptimizer: For budget-aware context assembly
        - MCP Tools: For load_progressively operations
        - Client Applications: For incremental context loading

    Example implementation:
        ```python
        class SimpleProgressiveLoader:
            async def load_by_priority(
                self,
                memory_bank_path: Path,
                priority_order: list[str] | None = None,
                token_budget: int | None = None,
            ) -> ProgressiveLoadResult:
                priority = priority_order or ["projectBrief.md", "activeContext.md"]
                loaded = {}
                total_tokens = 0
                loading_order = []

                for file_name in priority:
                    file_path = memory_bank_path / file_name
                    if file_path.exists():
                        content = await self._read_file(file_path)
                        tokens = self.token_counter.count_tokens(content)
                        if token_budget and (total_tokens + tokens) > token_budget:
                            break
                        loaded[file_name] = content
                        total_tokens += tokens
                        loading_order.append(file_name)

                return ProgressiveLoadResult(
                    loaded_files=loaded,
                    total_tokens=total_tokens,
                    files_count=len(loaded),
                    budget_remaining=token_budget - total_tokens if token_budget else None,
                    truncated=token_budget is not None and total_tokens >= token_budget,
                    loading_order=loading_order,
                )

            async def load_by_dependencies(
                self,
                memory_bank_path: Path,
                start_files: list[str] | None = None,
                token_budget: int | None = None,
            ) -> ProgressiveLoadResult:
                loading_order = self.dependency_graph.compute_loading_order(start_files)
                return await self._load_files_in_order(loading_order, memory_bank_path, token_budget)

            async def load_by_relevance(
                self,
                memory_bank_path: Path,
                task_description: str,
                token_budget: int | None = None,
            ) -> ProgressiveLoadResult:
                scores = await self.scorer.score_files(task_description, self._get_all_files(memory_bank_path))
                sorted_files = sorted(scores.items(), key=lambda x: x[1]["relevance_score"], reverse=True)
                return await self._load_files_in_order([f[0] for f in sorted_files], memory_bank_path, token_budget)

        # SimpleProgressiveLoader automatically satisfies ProgressiveLoaderProtocol
        ```

    Note:
        - Three loading strategies: priority, dependency, relevance
        - Token budget enforcement
        - Incremental context assembly
    """

    async def load_by_priority(
        self,
        memory_bank_path: Path,
        priority_order: list[str] | None = None,
        token_budget: int | None = None,
    ) -> ProgressiveLoadResult:
        """Load context progressively by priority.

        Args:
            memory_bank_path: Path to Memory Bank directory
            priority_order: Priority order for loading (default if None)
            token_budget: Maximum tokens to load (no limit if None)

        Returns:
            Progressive load result model
        """
        ...

    async def load_by_dependencies(
        self,
        memory_bank_path: Path,
        start_files: list[str] | None = None,
        token_budget: int | None = None,
    ) -> ProgressiveLoadResult:
        """Load context progressively by dependencies.

        Args:
            memory_bank_path: Path to Memory Bank directory
            start_files: Starting files (auto-detect if None)
            token_budget: Maximum tokens to load (no limit if None)

        Returns:
            Progressive load result model
        """
        ...

    async def load_by_relevance(
        self,
        memory_bank_path: Path,
        task_description: str,
        token_budget: int | None = None,
    ) -> ProgressiveLoadResult:
        """Load context progressively by relevance.

        Args:
            memory_bank_path: Path to Memory Bank directory
            task_description: Task description for relevance scoring
            token_budget: Maximum tokens to load (no limit if None)

        Returns:
            Progressive load result model
        """
        ...


class SummarizationEngineProtocol(Protocol):
    """Protocol for content summarization operations using structural subtyping (PEP 544).

    This protocol defines the interface for summarizing file content when full
    content exceeds token budgets. Summarization enables including more files
    within context limits. A class implementing these methods automatically
    satisfies this protocol.

    Used by:
        - SummarizationEngine: Summarizes content using multiple strategies
        - ContextOptimizer: For fitting more content within budgets
        - ProgressiveLoader: For loading summarized versions
        - MCP Tools: For summarize_content operations

    Example implementation:
        ```python
        class SimpleSummarizationEngine:
            async def summarize_file(
                self,
                file_path: Path,
                strategy: str = "key_sections",
                target_reduction: float = 0.5,
            ) -> SummarizationResultModel:
                content = await self._read_file(file_path)
                original_tokens = self.token_counter.count_tokens(content)
                target_tokens = int(original_tokens * (1 - target_reduction))

                if strategy == "key_sections":
                    summarized = await self.extract_key_sections(content, target_tokens)
                else:
                    summarized = content[:target_tokens]  # Simple truncation

                summary_tokens = self.token_counter.count_tokens(summarized)

                return SummarizationResultModel(
                    original_tokens=original_tokens,
                    summary_tokens=summary_tokens,
                    reduction=(original_tokens - summary_tokens) / original_tokens if original_tokens > 0 else 0.0,
                    summary=summarized,
                    strategy=strategy,
                )

            async def extract_key_sections(self, content: str, target_tokens: int) -> str:
                sections = self._parse_sections(content)
                scored_sections = [(s, self._score_section(s)) for s in sections]
                scored_sections.sort(key=lambda x: x[1], reverse=True)

                result_sections = []
                current_tokens = 0
                for section, score in scored_sections:
                    section_tokens = self.token_counter.count_tokens(section["content"])
                    if current_tokens + section_tokens <= target_tokens:
                        result_sections.append(section)
                        current_tokens += section_tokens

                result_sections.sort(key=lambda s: s["start_line"])
                return "\n\n".join(s["content"] for s in result_sections)

        # SimpleSummarizationEngine automatically satisfies SummarizationEngineProtocol
        ```

    Note:
        - Multiple summarization strategies
        - Token-aware summarization
        - Preserves key information
    """

    async def summarize_file(
        self,
        file_path: Path,
        strategy: str = "key_sections",
        target_reduction: float = 0.5,
    ) -> SummarizationResultModel:
        """Summarize a file's content.

        Args:
            file_path: Path to file to summarize
            strategy: Summarization strategy
            target_reduction: Target reduction percentage (0-1)

        Returns:
            Summarization result model
        """
        ...

    async def extract_key_sections(self, content: str, target_tokens: int) -> str:
        """Extract key sections from content.

        Args:
            content: Content to extract from
            target_tokens: Target token count

        Returns:
            Extracted content string
        """
        ...


__all__ = [
    "ProgressiveLoaderProtocol",
    "SummarizationEngineProtocol",
]
