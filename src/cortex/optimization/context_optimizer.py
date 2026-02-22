"""
Context optimization for intelligent token budget management.

This module provides functionality to select optimal subsets of content
that fit within token budgets while maximizing information value.
Delegates strategy implementations to OptimizationStrategies.
"""

from collections.abc import Awaitable, Callable

from cortex.core.dependency_graph import DependencyGraph
from cortex.core.models import ModelDict
from cortex.core.token_counter import TokenCounter
from cortex.optimization.models import FileMetadataForScoring

from .optimization_strategies import OptimizationResult, OptimizationStrategies
from .relevance_scorer import RelevanceScorer


class ContextOptimizer:
    """
    Optimize context selection within token budget.

    Delegates strategy implementations to OptimizationStrategies.
    """

    token_counter: TokenCounter
    relevance_scorer: RelevanceScorer
    dependency_graph: DependencyGraph
    mandatory_files: list[str]
    strategies: OptimizationStrategies

    def __init__(
        self,
        token_counter: TokenCounter,
        relevance_scorer: RelevanceScorer,
        dependency_graph: DependencyGraph,
        mandatory_files: list[str] | None = None,
    ):
        """
        Initialize context optimizer.

        Args:
            token_counter: Token counter for accurate tracking
            relevance_scorer: Relevance scorer for prioritization
            dependency_graph: Dependency graph for relationships
            mandatory_files: Files that must always be included
        """
        self.token_counter = token_counter
        self.relevance_scorer = relevance_scorer
        self.dependency_graph = dependency_graph
        self.mandatory_files = mandatory_files or ["memorybankinstructions.md"]

        # Create strategies instance
        self.strategies = OptimizationStrategies(
            token_counter=token_counter,
            relevance_scorer=relevance_scorer,
            dependency_graph=dependency_graph,
            mandatory_files=self.mandatory_files,
        )

    async def optimize_context(
        self,
        task_description: str,
        files_content: dict[str, str],
        files_metadata: dict[str, ModelDict],
        token_budget: int,
        strategy: str = "dependency_aware",
        quality_scores: dict[str, float] | None = None,
    ) -> OptimizationResult:
        """
        Select optimal context within budget.

        Args:
            task_description: Description of task
            files_content: Available files with content
            files_metadata: File metadata
            token_budget: Maximum tokens allowed
            strategy: Optimization strategy (priority, dependency_aware,
            section_level, hybrid)
            quality_scores: Optional quality scores for files

        Returns:
            OptimizationResult with selected content
        """
        if not files_content:
            return _create_empty_result(strategy)

        # Score files and extract relevance scores
        relevance_scores = await _score_files_for_optimization(
            self.relevance_scorer,
            task_description,
            files_content,
            files_metadata,
            quality_scores,
        )

        # Apply strategy and update metadata
        result = await _apply_optimization_strategy(
            self.strategies,
            strategy,
            task_description,
            relevance_scores,
            files_content,
            token_budget,
        )

        return _update_result_metadata(result, strategy, relevance_scores)

    async def optimize_by_priority(
        self,
        relevance_scores: dict[str, float],
        files_content: dict[str, str],
        token_budget: int,
    ) -> OptimizationResult:
        """
        Optimize context by priority (relevance scores).

        Args:
            relevance_scores: Dictionary mapping file names to relevance scores
            files_content: Dictionary mapping file names to content
            token_budget: Maximum tokens allowed

        Returns:
            OptimizationResult with selected content
        """
        return await self.strategies.optimize_by_priority(
            relevance_scores, files_content, token_budget
        )


def _create_empty_result(strategy: str) -> OptimizationResult:
    """Create empty optimization result for no files case.

    Args:
        strategy: Strategy name used

    Returns:
        OptimizationResult with empty selection
    """
    return OptimizationResult(
        selected_files=[],
        selected_sections={},
        total_tokens=0,
        utilization=0.0,
        excluded_files=[],
        strategy_used=strategy,
        metadata={"error": "No files provided"},
    )


async def _score_files_for_optimization(
    relevance_scorer: RelevanceScorer,
    task_description: str,
    files_content: dict[str, str],
    files_metadata: dict[str, ModelDict],
    quality_scores: dict[str, float] | None,
) -> dict[str, float]:
    """Score files by relevance and extract total scores.

    Args:
        relevance_scorer: RelevanceScorer instance
        task_description: Description of task
        files_content: Available files with content
        files_metadata: File metadata
        quality_scores: Optional quality scores for files

    Returns:
        Dictionary mapping file names to total relevance scores
    """
    metadata_models: dict[str, FileMetadataForScoring] = {
        file_name: FileMetadataForScoring.model_validate(meta)
        for file_name, meta in files_metadata.items()
    }
    relevance_results: dict[str, dict[str, float | str]] = (
        await relevance_scorer.score_files(
            task_description,
            files_content,
            metadata_models,
            quality_scores or {},
        )
    )
    return _extract_relevance_scores(relevance_results)


def _extract_relevance_scores(
    relevance_results: dict[str, dict[str, float | str]],
) -> dict[str, float]:
    """Extract total scores from relevance results.

    Args:
        relevance_results: Dictionary mapping file names to relevance result dicts

    Returns:
        Dictionary mapping file names to total relevance scores
    """
    relevance_scores: dict[str, float] = {}
    for file_name, result in relevance_results.items():
        total_score_val = result.get("total_score", 0.0)
        if isinstance(total_score_val, (int, float)):
            relevance_scores[file_name] = float(total_score_val)
        else:
            relevance_scores[file_name] = 0.0
    return relevance_scores


def _create_strategy_handlers(
    strategies: OptimizationStrategies,
    task_description: str,
    relevance_scores: dict[str, float],
    files_content: dict[str, str],
    token_budget: int,
) -> dict[str, Callable[[], Awaitable[OptimizationResult]]]:
    """Create strategy handler functions.

    Args:
        strategies: OptimizationStrategies instance
        task_description: Description of task
        relevance_scores: Dictionary mapping file names to relevance scores
        files_content: Dictionary mapping file names to content
        token_budget: Maximum tokens allowed

    Returns:
        Dictionary mapping strategy names to handler functions
    """

    async def _priority_handler() -> OptimizationResult:
        return await strategies.optimize_by_priority(
            relevance_scores, files_content, token_budget
        )

    async def _dependency_handler() -> OptimizationResult:
        return await strategies.optimize_by_dependencies(
            relevance_scores, files_content, token_budget
        )

    async def _section_handler() -> OptimizationResult:
        return await strategies.optimize_with_sections(
            task_description, relevance_scores, files_content, token_budget
        )

    async def _hybrid_handler() -> OptimizationResult:
        return await strategies.optimize_hybrid(
            task_description, relevance_scores, files_content, token_budget
        )

    return {
        "priority": _priority_handler,
        "dependency_aware": _dependency_handler,
        "section_level": _section_handler,
        "hybrid": _hybrid_handler,
    }


async def _apply_optimization_strategy(
    strategies: OptimizationStrategies,
    strategy: str,
    task_description: str,
    relevance_scores: dict[str, float],
    files_content: dict[str, str],
    token_budget: int,
) -> OptimizationResult:
    """Apply optimization strategy based on strategy name.

    Args:
        strategies: OptimizationStrategies instance
        strategy: Strategy name (priority, dependency_aware, section_level, hybrid)
        task_description: Description of task
        relevance_scores: Dictionary mapping file names to relevance scores
        files_content: Dictionary mapping file names to content
        token_budget: Maximum tokens allowed

    Returns:
        OptimizationResult with selected content
    """
    handlers = _create_strategy_handlers(
        strategies, task_description, relevance_scores, files_content, token_budget
    )
    handler = handlers.get(strategy, handlers["dependency_aware"])
    return await handler()


def _update_result_metadata(
    result: OptimizationResult,
    strategy: str,
    relevance_scores: dict[str, float],
) -> OptimizationResult:
    """Update result metadata with strategy and relevance scores.

    Args:
        result: OptimizationResult to update
        strategy: Strategy name used
        relevance_scores: Dictionary mapping file names to relevance scores

    Returns:
        Updated OptimizationResult
    """
    result.strategy_used = strategy
    metadata_dict: ModelDict = dict(result.metadata) if result.metadata else {}
    metadata_dict["relevance_scores"] = {
        file_name: round(float(score), 3)
        for file_name, score in relevance_scores.items()
    }
    result.metadata = metadata_dict
    return result
