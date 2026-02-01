"""
Hybrid optimization strategy: phase execution and result combination.

This module contains helpers for running hybrid optimization (dependency-aware
phase 1 then section-level phase 2) and combining results.
"""

from collections.abc import Awaitable, Callable

from cortex.optimization.optimization_types import OptimizationResult


async def execute_hybrid_phase1(
    optimize_by_dependencies: Callable[
        [dict[str, float], dict[str, str], int], Awaitable[OptimizationResult]
    ],
    relevance_scores: dict[str, float],
    files_content: dict[str, str],
    token_budget: int,
) -> OptimizationResult:
    """Run phase 1 of hybrid optimization (high-scoring files with dependencies)."""
    high_score_threshold = 0.6
    high_scoring = {
        k: v for k, v in relevance_scores.items() if v >= high_score_threshold
    }
    return await optimize_by_dependencies(high_scoring, files_content, token_budget)


async def execute_hybrid_phase2(
    optimize_with_sections: Callable[
        [str, dict[str, float], dict[str, str], int],
        Awaitable[OptimizationResult],
    ],
    task_description: str,
    relevance_scores: dict[str, float],
    files_content: dict[str, str],
    phase1_files: list[str],
    remaining_budget: int,
) -> OptimizationResult:
    """Run phase 2 of hybrid optimization (sections from remaining files)."""
    remaining_files = {k: v for k, v in files_content.items() if k not in phase1_files}
    remaining_scores = {
        k: v for k, v in relevance_scores.items() if k in remaining_files
    }
    return await optimize_with_sections(
        task_description, remaining_scores, remaining_files, remaining_budget
    )


def combine_hybrid_results(
    phase1: OptimizationResult,
    phase2: OptimizationResult,
    token_budget: int,
) -> OptimizationResult:
    """Combine phase 1 and phase 2 results into a single OptimizationResult."""
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
