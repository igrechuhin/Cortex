#!/usr/bin/env python3
"""Optimization protocols for MCP Memory Bank.

This module defines Protocol classes (PEP 544) for context optimization,
relevance scoring, progressive loading, and content summarization.
"""

from typing import Protocol

from cortex.core.models import ModelDict
from cortex.optimization.models import (
    FileMetadataForScoring,
    OptimizationResultModel,
)
from cortex.optimization.optimization_types import OptimizationResult


class ContextOptimizerProtocol(Protocol):
    """Protocol for context optimization operations using structural
    subtyping (PEP 544).

    This protocol defines the interface for optimizing context selection within
    token budgets using various strategies (relevance-based, dependency-based,
    or hybrid). Context optimization ensures the most valuable information fits
    within model context limits. A class implementing these methods
    automatically satisfies this protocol.

    Used by:
        - ContextOptimizer: Multi-strategy context optimizer with token budgeting
        - MCP Tools: For load_context operations
        - ProgressiveLoader: For budget-aware context loading
        - Client Applications: For intelligent context management

    Example implementation:
        ```python
        class SimpleContextOptimizer:
            async def optimize(
                self,
                task_description: str,
                files_content: dict[str, str],
                files_metadata: dict[str, FileMetadataForScoring],
                strategy: str = "hybrid",
                token_budget: int | None = None,
                mandatory_files: list[str] | None = None,
            ) -> OptimizationResultModel:
                # Score files by relevance
                scored = await self.scorer.score_files(
                    task_description, files_content, files_metadata
                )
                sorted_files = sorted(
                    scored.items(),
                    key=lambda x: x[1].relevance_score,
                    reverse=True,
                )

                # Select files within budget
                selected = {}
                total_tokens = 0

                # Mandatory files first
                for fname in (mandatory_files or []):
                    selected[fname] = files_content[fname]
                    total_tokens += self.token_counter.count_tokens(
                        files_content[fname]
                    )

                # Add by relevance
                for fname, _ in sorted_files:
                    if fname in selected:
                        continue
                    tokens = self.token_counter.count_tokens(files_content[fname])
                    if token_budget and (total_tokens + tokens) > token_budget:
                        break
                    selected[fname] = files_content[fname]
                    total_tokens += tokens

                return OptimizationResultModel(
                    selected_files=list(selected.keys()),
                    total_tokens=total_tokens,
                    utilization=total_tokens / token_budget if token_budget else 0.0,
                    excluded_files=[f for f in files_content if f not in selected],
                    strategy_used=strategy,
                )

        # SimpleContextOptimizer automatically satisfies ContextOptimizerProtocol
        ```

    Note:
        - Multiple strategies: relevance, dependency, hybrid
        - Mandatory files always included
        - Token budget enforced strictly
    """

    async def optimize(
        self,
        task_description: str,
        files_content: dict[str, str],
        files_metadata: dict[str, FileMetadataForScoring],
        strategy: str = "hybrid",
        token_budget: int | None = None,
        mandatory_files: list[str] | None = None,
    ) -> OptimizationResultModel:
        """Optimize context within token budget.

        Args:
            task_description: Description of task
            files_content: Available files content
            files_metadata: Files metadata
            strategy: Optimization strategy
            token_budget: Max tokens allowed
            mandatory_files: Files that must be included

        Returns:
            Optimization result model
        """
        ...

    async def optimize_context(
        self,
        task_description: str,
        files_content: dict[str, str],
        files_metadata: dict[str, ModelDict],
        token_budget: int,
        strategy: str = "dependency_aware",
        quality_scores: dict[str, float] | None = None,
    ) -> OptimizationResult:
        """Select optimal context within budget (ContextOptimizer-style API).

        Args:
            task_description: Description of task
            files_content: Available files with content
            files_metadata: File metadata (ModelDict-compatible)
            token_budget: Maximum tokens allowed
            strategy: Optimization strategy
            quality_scores: Optional quality scores for files

        Returns:
            OptimizationResult with selected content
        """
        ...


__all__ = [
    "ContextOptimizerProtocol",
]
