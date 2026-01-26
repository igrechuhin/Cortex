"""
Optimization strategies for context selection within token budgets.

This module contains different strategy implementations for selecting
optimal subsets of content while respecting token budget constraints.
"""

from dataclasses import dataclass

from cortex.core.dependency_graph import DependencyGraph
from cortex.core.models import ModelDict
from cortex.core.token_counter import TokenCounter
from cortex.optimization.models import SectionScoreModel

from .relevance_scorer import RelevanceScorer


@dataclass
class OptimizationResult:
    """Result of context optimization."""

    selected_files: list[str]
    selected_sections: dict[str, list[str]]
    total_tokens: int
    utilization: float
    excluded_files: list[str]
    strategy_used: str
    metadata: ModelDict


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

        total_tokens = self._add_mandatory_files_to_priority(
            selected_files, files_content, total_tokens, token_budget
        )
        total_tokens = self._add_greedy_files(
            selected_files, relevance_scores, files_content, total_tokens, token_budget
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
        """
        Dependency-aware: ensure all dependencies of included files are also included.

        Args:
            relevance_scores: Relevance scores for files
            files_content: File contents
            token_budget: Token budget

        Returns:
            OptimizationResult
        """
        selected_files: set[str] = set()
        total_tokens = 0

        selected_files, total_tokens = self._process_mandatory_files_with_dependencies(
            selected_files, total_tokens, files_content, token_budget
        )

        selected_files, total_tokens = self._process_remaining_files_by_relevance(
            selected_files,
            total_tokens,
            relevance_scores,
            files_content,
            token_budget,
        )

        return self._build_dependency_result(
            selected_files, total_tokens, files_content, token_budget
        )

    def _process_mandatory_files_with_dependencies(
        self,
        selected_files: set[str],
        total_tokens: int,
        files_content: dict[str, str],
        token_budget: int,
    ) -> tuple[set[str], int]:
        """Process mandatory files and their dependencies.

        Args:
            selected_files: Currently selected files
            total_tokens: Current token count
            files_content: File contents
            token_budget: Token budget

        Returns:
            Tuple of (updated selected_files, updated total_tokens)
        """
        for mandatory_file in self.mandatory_files:
            if mandatory_file in files_content:
                deps = self.get_all_dependencies(mandatory_file)
                deps.add(mandatory_file)

                cluster_tokens = self._calculate_cluster_tokens(deps, files_content)

                if total_tokens + cluster_tokens <= token_budget:
                    selected_files.update(deps)
                    total_tokens += cluster_tokens

        return selected_files, total_tokens

    def _process_remaining_files_by_relevance(
        self,
        selected_files: set[str],
        total_tokens: int,
        relevance_scores: dict[str, float],
        files_content: dict[str, str],
        token_budget: int,
    ) -> tuple[set[str], int]:
        """Process remaining files sorted by relevance score.

        Args:
            selected_files: Currently selected files
            total_tokens: Current token count
            relevance_scores: Relevance scores for files
            files_content: File contents
            token_budget: Token budget

        Returns:
            Tuple of (updated selected_files, updated total_tokens)
        """
        remaining_files = [
            (file_name, score)
            for file_name, score in relevance_scores.items()
            if file_name not in selected_files
        ]
        remaining_files.sort(key=lambda x: x[1], reverse=True)

        for file_name, _ in remaining_files:
            if file_name in selected_files:
                continue

            deps = self.get_all_dependencies(file_name)
            deps.add(file_name)
            new_deps = deps - selected_files

            cluster_tokens = self._calculate_cluster_tokens(new_deps, files_content)

            if total_tokens + cluster_tokens <= token_budget:
                selected_files.update(new_deps)
                total_tokens += cluster_tokens

        return selected_files, total_tokens

    def _calculate_cluster_tokens(
        self, dependencies: set[str], files_content: dict[str, str]
    ) -> int:
        """Calculate total tokens for a cluster of dependencies.

        Args:
            dependencies: Set of file names in the cluster
            files_content: File contents

        Returns:
            Total token count for the cluster
        """
        cluster_tokens = 0
        for dep in dependencies:
            if dep in files_content:
                dep_tokens = self.token_counter.count_tokens(files_content[dep])
                cluster_tokens += dep_tokens
        return cluster_tokens

    def _build_dependency_result(
        self,
        selected_files: set[str],
        total_tokens: int,
        files_content: dict[str, str],
        token_budget: int,
    ) -> OptimizationResult:
        """Build OptimizationResult for dependency-based optimization.

        Args:
            selected_files: Set of selected file names
            total_tokens: Total token count
            files_content: File contents
            token_budget: Token budget

        Returns:
            OptimizationResult instance
        """
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

    async def optimize_with_sections(
        self,
        task_description: str,
        relevance_scores: dict[str, float],
        files_content: dict[str, str],
        token_budget: int,
    ) -> OptimizationResult:
        """
        Section-level optimization: include partial files when beneficial.

        Args:
            task_description: Task description
            relevance_scores: Relevance scores for files
            files_content: File contents
            token_budget: Token budget

        Returns:
            OptimizationResult
        """
        selected_files: list[str] = []
        selected_sections: dict[str, list[str]] = {}
        total_tokens = 0

        total_tokens = self._add_mandatory_files(
            selected_files, files_content, total_tokens, token_budget
        )
        total_tokens = self._add_high_scoring_files(
            selected_files, relevance_scores, files_content, total_tokens, token_budget
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

        return self._build_sections_result(
            selected_files, selected_sections, files_content, total_tokens, token_budget
        )

    def _add_mandatory_files(
        self,
        selected_files: list[str],
        files_content: dict[str, str],
        total_tokens: int,
        token_budget: int,
    ) -> int:
        """Add mandatory files to selection.

        Args:
            selected_files: List of selected files to update
            files_content: File contents
            total_tokens: Current token count
            token_budget: Token budget

        Returns:
            Updated token count
        """
        # Pre-calculate token counts for all mandatory files
        file_token_pairs = [
            (
                mandatory_file,
                self.token_counter.count_tokens(files_content[mandatory_file]),
            )
            for mandatory_file in self.mandatory_files
            if mandatory_file in files_content
        ]

        # Accumulate files that fit within budget
        current_tokens = total_tokens
        for file_name, file_tokens in file_token_pairs:
            if current_tokens + file_tokens <= token_budget:
                selected_files.append(file_name)
                current_tokens += file_tokens

        return current_tokens

    def _add_high_scoring_files(
        self,
        selected_files: list[str],
        relevance_scores: dict[str, float],
        files_content: dict[str, str],
        total_tokens: int,
        token_budget: int,
    ) -> int:
        """Add high-scoring files to selection.

        Args:
            selected_files: List of selected files to update
            relevance_scores: Relevance scores
            files_content: File contents
            total_tokens: Current token count
            token_budget: Token budget

        Returns:
            Updated token count
        """
        high_score_threshold = 0.7
        # Pre-calculate token counts for high-scoring files
        file_token_pairs = [
            (file_name, self.token_counter.count_tokens(files_content[file_name]))
            for file_name, score in relevance_scores.items()
            if score >= high_score_threshold
            and file_name not in selected_files
            and file_name in files_content
        ]

        # Accumulate files that fit within budget
        current_tokens = total_tokens
        for file_name, file_tokens in file_token_pairs:
            if current_tokens + file_tokens <= token_budget:
                selected_files.append(file_name)
                current_tokens += file_tokens

        return current_tokens

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
        """Add medium-scoring files as sections.

        Args:
            selected_sections: Dictionary of selected sections to update
            task_description: Task description
            relevance_scores: Relevance scores
            files_content: File contents
            selected_files: Already selected files
            total_tokens: Current token count
            token_budget: Token budget

        Returns:
            Updated token count
        """
        medium_scoring_files = _get_medium_scoring_files(
            relevance_scores, selected_files
        )

        for file_name in medium_scoring_files:
            content = files_content[file_name]
            section_scores = await self.relevance_scorer.score_sections(
                task_description, file_name, content
            )

            file_sections, total_tokens = self._process_sections_for_file(
                section_scores, content, total_tokens, token_budget
            )

            if file_sections:
                selected_sections[file_name] = file_sections

        return total_tokens

    def _filter_and_sort_sections(
        self, section_scores: list[SectionScoreModel]
    ) -> list[SectionScoreModel]:
        """Filter and sort sections by score (highest first).

        Args:
            section_scores: List of section scores with 'section' and 'score' keys

        Returns:
            Sorted list of valid sections (score >= 0.5)
        """
        valid_sections = [
            section_data
            for section_data in section_scores
            if section_data.section is not None
            and section_data.section
            and section_data.score >= 0.5
        ]
        return sorted(
            valid_sections,
            key=lambda x: x.score,
            reverse=True,
        )

    def _calculate_section_tokens(
        self, sorted_sections: list[SectionScoreModel], content: str
    ) -> list[tuple[str, int]]:
        """Pre-calculate token counts for all sections.

        Args:
            sorted_sections: Sorted list of section data
            content: Full file content

        Returns:
            List of (section_name, token_count) tuples
        """
        pairs: list[tuple[str, int]] = []
        for section_data in sorted_sections:
            section_name = section_data.section
            if section_name is None:
                continue
            section_tokens = self.token_counter.count_tokens(
                self.extract_section_content(content, section_name)
            )
            pairs.append((section_name, section_tokens))
        return pairs

    def _process_sections_for_file(
        self,
        section_scores: list[SectionScoreModel],
        content: str,
        total_tokens: int,
        token_budget: int,
    ) -> tuple[list[str], int]:
        """Process sections for a file and add them within budget.

        Args:
            section_scores: List of section scores with 'section' and 'score' keys
            content: Full file content
            total_tokens: Current token count
            token_budget: Token budget

        Returns:
            Tuple of (selected section names, updated token count)
        """
        sorted_sections = self._filter_and_sort_sections(section_scores)
        section_token_pairs = self._calculate_section_tokens(sorted_sections, content)

        # Accumulate sections that fit within budget
        file_sections: list[str] = []
        current_tokens = total_tokens
        for section_name, section_tokens in section_token_pairs:
            if current_tokens + section_tokens <= token_budget:
                file_sections.append(section_name)
                current_tokens += section_tokens
            else:
                break

        return file_sections, current_tokens

    def _get_excluded_files(
        self,
        files_content: dict[str, str],
        selected_files: list[str],
        selected_sections: dict[str, list[str]],
    ) -> list[str]:
        """Get list of excluded files.

        Args:
            files_content: All file contents
            selected_files: Selected files
            selected_sections: Selected sections

        Returns:
            List of excluded files
        """
        return [
            file_name
            for file_name in files_content.keys()
            if file_name not in selected_files and file_name not in selected_sections
        ]

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
        phase1 = await self._execute_hybrid_phase1(
            relevance_scores, files_content, token_budget
        )

        remaining_budget = token_budget - phase1.total_tokens
        if remaining_budget > 0:
            phase2 = await self._execute_hybrid_phase2(
                task_description,
                relevance_scores,
                files_content,
                phase1.selected_files,
                remaining_budget,
            )
            return self._combine_hybrid_results(phase1, phase2, token_budget)

        return phase1

    def get_all_dependencies(self, file_name: str) -> set[str]:
        """
        Get all dependencies of a file (transitive closure).

        Args:
            file_name: File name

        Returns:
            Set of all dependencies
        """
        visited: set[str] = set()
        to_visit = [file_name]

        while to_visit:
            current = to_visit.pop()
            if current in visited:
                continue

            visited.add(current)
            deps = self.dependency_graph.get_dependencies(current)
            to_visit.extend(deps)

        # Remove the file itself
        visited.discard(file_name)

        return visited

    def extract_section_content(self, content: str, section_name: str) -> str:
        """
        Extract content of a specific section.

        Args:
            content: Full file content
            section_name: Section name to extract

        Returns:
            Section content
        """
        lines = content.split("\n")
        section_start_idx, section_end_idx = self._find_section_bounds(
            lines, section_name
        )

        if section_start_idx is None:
            return ""

        if section_end_idx is None:
            section_end_idx = len(lines)

        return "\n".join(lines[section_start_idx:section_end_idx])

    def _find_section_bounds(
        self, lines: list[str], section_name: str
    ) -> tuple[int | None, int | None]:
        """Find start and end indices for a section.

        Args:
            lines: List of content lines
            section_name: Section name to find

        Returns:
            Tuple of (start_index, end_index), both may be None
        """
        section_start_idx: int | None = None

        for i, line in enumerate(lines):
            if not line.startswith("#"):
                continue

            # Check if this is the target section
            if section_name in line:
                section_start_idx = i
            elif section_start_idx is not None:
                # Reached next section, stop
                return (section_start_idx, i)

        return (section_start_idx, None)

    def _add_mandatory_files_to_priority(
        self,
        selected_files: list[str],
        files_content: dict[str, str],
        total_tokens: int,
        token_budget: int,
    ) -> int:
        """Add mandatory files to priority selection."""
        # Pre-calculate token counts for all mandatory files
        file_token_pairs = [
            (
                mandatory_file,
                self.token_counter.count_tokens(files_content[mandatory_file]),
            )
            for mandatory_file in self.mandatory_files
            if mandatory_file in files_content
        ]

        # Accumulate files that fit within budget
        current_tokens = total_tokens
        for file_name, file_tokens in file_token_pairs:
            if current_tokens + file_tokens <= token_budget:
                selected_files.append(file_name)
                current_tokens += file_tokens
        return current_tokens

    def _add_greedy_files(
        self,
        selected_files: list[str],
        relevance_scores: dict[str, float],
        files_content: dict[str, str],
        total_tokens: int,
        token_budget: int,
    ) -> int:
        """Add files greedily by score."""
        # Pre-calculate token counts and sort by relevance score
        file_token_pairs = [
            (
                file_name,
                self.token_counter.count_tokens(files_content[file_name]),
                score,
            )
            for file_name, score in relevance_scores.items()
            if file_name not in selected_files and file_name in files_content
        ]
        file_token_pairs.sort(key=lambda x: x[2], reverse=True)

        # Accumulate files that fit within budget
        current_tokens = total_tokens
        for file_name, tokens, _ in file_token_pairs:
            if current_tokens + tokens <= token_budget:
                selected_files.append(file_name)
                current_tokens += tokens
        return current_tokens

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

    def _build_sections_result(
        self,
        selected_files: list[str],
        selected_sections: dict[str, list[str]],
        files_content: dict[str, str],
        total_tokens: int,
        token_budget: int,
    ) -> OptimizationResult:
        """Build sections optimization result."""
        excluded_files = self._get_excluded_files(
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

    async def _execute_hybrid_phase1(
        self,
        relevance_scores: dict[str, float],
        files_content: dict[str, str],
        token_budget: int,
    ) -> OptimizationResult:
        """Execute phase 1 of hybrid optimization."""
        high_score_threshold = 0.6
        high_scoring = {
            k: v for k, v in relevance_scores.items() if v >= high_score_threshold
        }

        return await self.optimize_by_dependencies(
            high_scoring, files_content, token_budget
        )

    async def _execute_hybrid_phase2(
        self,
        task_description: str,
        relevance_scores: dict[str, float],
        files_content: dict[str, str],
        phase1_files: list[str],
        remaining_budget: int,
    ) -> OptimizationResult:
        """Execute phase 2 of hybrid optimization."""
        remaining_files = {
            k: v for k, v in files_content.items() if k not in phase1_files
        }
        remaining_scores = {
            k: v for k, v in relevance_scores.items() if k in remaining_files
        }

        return await self.optimize_with_sections(
            task_description, remaining_scores, remaining_files, remaining_budget
        )

    def _combine_hybrid_results(
        self,
        phase1: OptimizationResult,
        phase2: OptimizationResult,
        token_budget: int,
    ) -> OptimizationResult:
        """Combine phase 1 and phase 2 results."""
        return OptimizationResult(
            selected_files=phase1.selected_files + phase2.selected_files,
            selected_sections=phase2.selected_sections,
            total_tokens=phase1.total_tokens + phase2.total_tokens,
            utilization=(
                (phase1.total_tokens + phase2.total_tokens) / token_budget
                if token_budget > 0
                else 0.0
            ),
            excluded_files=phase2.excluded_files,
            strategy_used="hybrid",
            metadata={
                "phase1_files": len(phase1.selected_files),
                "phase2_files": len(phase2.selected_files),
                "phase2_sections": len(phase2.selected_sections),
            },
        )


def _get_medium_scoring_files(
    relevance_scores: dict[str, float], selected_files: list[str]
) -> list[str]:
    """Get list of medium-scoring files.

    Args:
        relevance_scores: Relevance scores for files
        selected_files: Already selected files

    Returns:
        List of medium-scoring file names
    """
    medium_score_threshold = 0.4
    high_score_threshold = 0.7
    return [
        file_name
        for file_name, score in relevance_scores.items()
        if medium_score_threshold <= score < high_score_threshold
        and file_name not in selected_files
    ]
