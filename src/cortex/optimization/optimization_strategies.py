"""
Optimization strategies for context selection within token budgets.

This module contains different strategy implementations for selecting
optimal subsets of content while respecting token budget constraints.
"""

from cortex.core.dependency_graph import DependencyGraph
from cortex.core.token_counter import TokenCounter

from .optimization_types import OptimizationResult
from .relevance_scorer import RelevanceScorer
from .strategy_hybrid import (
    combine_hybrid_results,
    execute_hybrid_phase1,
    execute_hybrid_phase2,
)
from .strategy_implementations import (
    extract_section_content as _extract_section_content,
)
from .strategy_implementations import (
    process_sections_for_file,
)
from .strategy_metrics import get_excluded_files
from .strategy_selection import (
    add_greedy_files,
    add_high_scoring_files,
    add_mandatory_files,
    add_mandatory_files_to_priority,
    get_all_dependencies_closure,
    get_medium_scoring_files,
    process_mandatory_files_with_dependencies,
    process_remaining_files_by_relevance,
)

__all__ = ["OptimizationResult", "OptimizationStrategies"]


class OptimizationStrategies:
    """
    Implementation of various optimization strategies.

    Provides different approaches for selecting content within token budgets.
    """

    def __init__(
        self,
        token_counter: TokenCounter,
        relevance_scorer: RelevanceScorer,
        dependency_graph: DependencyGraph,
        mandatory_files: list[str],
    ):
        """
        Initialize optimization strategies.

        Args:
            token_counter: Token counter for accurate tracking
            relevance_scorer: Relevance scorer for prioritization
            dependency_graph: Dependency graph for relationships
            mandatory_files: Files that must always be included
        """
        self.token_counter: TokenCounter = token_counter
        self.relevance_scorer: RelevanceScorer = relevance_scorer
        self.dependency_graph: DependencyGraph = dependency_graph
        self.mandatory_files: list[str] = mandatory_files

    async def optimize_by_priority(
        self,
        relevance_scores: dict[str, float],
        files_content: dict[str, str],
        token_budget: int,
    ) -> OptimizationResult:
        """
        Greedy optimization: select highest-scoring files first.

        Args:
            relevance_scores: Relevance scores for files
            files_content: File contents
            token_budget: Token budget

        Returns:
            OptimizationResult
        """
        selected_files: list[str] = []
        total_tokens = 0

        total_tokens = add_mandatory_files_to_priority(
            self.mandatory_files,
            selected_files,
            files_content,
            total_tokens,
            token_budget,
            self.token_counter,
        )
        total_tokens = add_greedy_files(
            selected_files,
            relevance_scores,
            files_content,
            total_tokens,
            token_budget,
            self.token_counter,
        )

        return self._build_priority_result(
            selected_files, files_content, total_tokens, token_budget
        )

    async def optimize_by_dependencies(
        self,
        relevance_scores: dict[str, float],
        files_content: dict[str, str],
        token_budget: int,
    ) -> OptimizationResult:
        """Dependency-aware: include files and their dependencies."""
        selected_files: set[str] = set()
        total_tokens = 0

        selected_files, total_tokens = process_mandatory_files_with_dependencies(
            self.mandatory_files,
            selected_files,
            total_tokens,
            files_content,
            token_budget,
            self.get_all_dependencies,
            self.token_counter,
        )

        selected_files, total_tokens = process_remaining_files_by_relevance(
            selected_files,
            total_tokens,
            relevance_scores,
            files_content,
            token_budget,
            self.get_all_dependencies,
            self.token_counter,
        )

        return self._build_dependency_result(
            selected_files, total_tokens, files_content, token_budget
        )

    async def optimize_with_sections(
        self,
        task_description: str,
        relevance_scores: dict[str, float],
        files_content: dict[str, str],
        token_budget: int,
    ) -> OptimizationResult:
        """Section-level optimization: include partial files when beneficial."""
        (
            selected_files,
            selected_sections,
            total_tokens,
        ) = await self._run_sections_phase(
            task_description, relevance_scores, files_content, token_budget
        )
        return self._build_sections_result(
            selected_files, selected_sections, files_content, total_tokens, token_budget
        )

    def _run_mandatory_and_high(
        self,
        relevance_scores: dict[str, float],
        files_content: dict[str, str],
        token_budget: int,
    ) -> tuple[list[str], dict[str, list[str]], int]:
        """Run mandatory and high-scoring file selection for sections phase."""
        selected_files: list[str] = []
        selected_sections: dict[str, list[str]] = {}
        total_tokens = add_mandatory_files(
            self.mandatory_files,
            selected_files,
            files_content,
            0,
            token_budget,
            self.token_counter,
        )
        total_tokens = add_high_scoring_files(
            selected_files,
            relevance_scores,
            files_content,
            total_tokens,
            token_budget,
            self.token_counter,
        )
        return selected_files, selected_sections, total_tokens

    async def _run_sections_phase(
        self,
        task_description: str,
        relevance_scores: dict[str, float],
        files_content: dict[str, str],
        token_budget: int,
    ) -> tuple[list[str], dict[str, list[str]], int]:
        """Run mandatory, high-scoring, and medium-scoring section selection."""
        selected_files, selected_sections, total_tokens = self._run_mandatory_and_high(
            relevance_scores, files_content, token_budget
        )
        total_tokens = await self._add_medium_scoring_sections(
            selected_sections,
            task_description,
            relevance_scores,
            files_content,
            selected_files,
            total_tokens,
            token_budget,
        )
        return selected_files, selected_sections, total_tokens

    async def _add_medium_scoring_sections(
        self,
        selected_sections: dict[str, list[str]],
        task_description: str,
        relevance_scores: dict[str, float],
        files_content: dict[str, str],
        selected_files: list[str],
        total_tokens: int,
        token_budget: int,
    ) -> int:
        """Add medium-scoring files as sections."""
        medium_scoring_files = get_medium_scoring_files(
            relevance_scores, selected_files
        )

        for file_name in medium_scoring_files:
            content = files_content[file_name]
            section_scores = await self.relevance_scorer.score_sections(
                task_description, file_name, content
            )

            file_sections, total_tokens = process_sections_for_file(
                section_scores,
                content,
                total_tokens,
                token_budget,
                self.token_counter,
            )

            if file_sections:
                selected_sections[file_name] = file_sections

        return total_tokens

    async def optimize_hybrid(
        self,
        task_description: str,
        relevance_scores: dict[str, float],
        files_content: dict[str, str],
        token_budget: int,
    ) -> OptimizationResult:
        """
        Hybrid optimization: combine multiple strategies.

        1. Start with mandatory files
        2. Add high-relevance files with dependencies
        3. Fill remaining budget with high-value sections

        Args:
            task_description: Task description
            relevance_scores: Relevance scores for files
            files_content: File contents
            token_budget: Token budget

        Returns:
            OptimizationResult
        """
        phase1 = await execute_hybrid_phase1(
            self.optimize_by_dependencies,
            relevance_scores,
            files_content,
            token_budget,
        )

        remaining_budget = token_budget - phase1.total_tokens
        if remaining_budget > 0:
            phase2 = await execute_hybrid_phase2(
                self.optimize_with_sections,
                task_description,
                relevance_scores,
                files_content,
                phase1.selected_files,
                remaining_budget,
            )
            return combine_hybrid_results(phase1, phase2, token_budget)

        return phase1

    def get_all_dependencies(self, file_name: str) -> set[str]:
        """
        Get all dependencies of a file (transitive closure).

        Args:
            file_name: File name

        Returns:
            Set of all dependencies
        """
        return get_all_dependencies_closure(
            self.dependency_graph.get_dependencies, file_name
        )

    def extract_section_content(self, content: str, section_name: str) -> str:
        """
        Extract content of a specific section.

        Args:
            content: Full file content
            section_name: Section name to extract

        Returns:
            Section content
        """
        return _extract_section_content(content, section_name)

    def _build_priority_result(
        self,
        selected_files: list[str],
        files_content: dict[str, str],
        total_tokens: int,
        token_budget: int,
    ) -> OptimizationResult:
        """Build priority optimization result."""
        excluded_files = [
            file_name
            for file_name in files_content.keys()
            if file_name not in selected_files
        ]
        utilization = total_tokens / token_budget if token_budget > 0 else 0.0

        return OptimizationResult(
            selected_files=selected_files,
            selected_sections={},
            total_tokens=total_tokens,
            utilization=utilization,
            excluded_files=excluded_files,
            strategy_used="priority",
            metadata={},
        )

    def _build_dependency_result(
        self,
        selected_files: set[str],
        total_tokens: int,
        files_content: dict[str, str],
        token_budget: int,
    ) -> OptimizationResult:
        """Build OptimizationResult for dependency-based optimization."""
        excluded_files = [
            file_name
            for file_name in files_content.keys()
            if file_name not in selected_files
        ]

        utilization = total_tokens / token_budget if token_budget > 0 else 0.0

        return OptimizationResult(
            selected_files=list(selected_files),
            selected_sections={},
            total_tokens=total_tokens,
            utilization=utilization,
            excluded_files=excluded_files,
            strategy_used="dependency_aware",
            metadata={},
        )

    def _build_sections_result(
        self,
        selected_files: list[str],
        selected_sections: dict[str, list[str]],
        files_content: dict[str, str],
        total_tokens: int,
        token_budget: int,
    ) -> OptimizationResult:
        """Build sections optimization result."""
        excluded_files = get_excluded_files(
            files_content, selected_files, selected_sections
        )
        utilization = total_tokens / token_budget if token_budget > 0 else 0.0

        return OptimizationResult(
            selected_files=selected_files,
            selected_sections=selected_sections,
            total_tokens=total_tokens,
            utilization=utilization,
            excluded_files=excluded_files,
            strategy_used="section_level",
            metadata={},
        )
