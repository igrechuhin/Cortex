"""
Strategy metrics and result building utilities.

This module contains utilities for building OptimizationResult objects
and calculating metrics for different optimization strategies.
"""

from .models import OptimizationMetadata
from .optimization_types import OptimizationResultModel as OptimizationResult


def build_priority_result(
    selected_files: list[str],
    files_content: dict[str, str],
    total_tokens: int,
    token_budget: int,
) -> OptimizationResult:
    """Build priority optimization result.

    Args:
        selected_files: List of selected file names
        files_content: File contents
        total_tokens: Total token count
        token_budget: Token budget

    Returns:
        OptimizationResult instance
    """
    excluded_files = [
        file_name for file_name in files_content if file_name not in selected_files
    ]
    utilization = total_tokens / token_budget if token_budget > 0 else 0.0

    return OptimizationResult(
        selected_files=selected_files,
        selected_sections={},
        total_tokens=total_tokens,
        utilization=utilization,
        excluded_files=excluded_files,
        strategy_used="priority",
        metadata=OptimizationMetadata(),
    )


def build_dependency_result(
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
        file_name for file_name in files_content if file_name not in selected_files
    ]

    utilization = total_tokens / token_budget if token_budget > 0 else 0.0

    return OptimizationResult(
        selected_files=list(selected_files),
        selected_sections={},
        total_tokens=total_tokens,
        utilization=utilization,
        excluded_files=excluded_files,
        strategy_used="dependency_aware",
        metadata=OptimizationMetadata(),
    )


def build_sections_result(
    selected_files: list[str],
    selected_sections: dict[str, list[str]],
    files_content: dict[str, str],
    total_tokens: int,
    token_budget: int,
) -> OptimizationResult:
    """Build sections optimization result.

    Args:
        selected_files: List of selected file names
        selected_sections: Dictionary of selected sections
        files_content: File contents
        total_tokens: Total token count
        token_budget: Token budget

    Returns:
        OptimizationResult instance
    """
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
        metadata=OptimizationMetadata(),
    )


def combine_hybrid_results(
    phase1: OptimizationResult,
    phase2: OptimizationResult,
    token_budget: int,
) -> OptimizationResult:
    """Combine phase 1 and phase 2 results.

    Args:
        phase1: Phase 1 optimization result
        phase2: Phase 2 optimization result
        token_budget: Token budget

    Returns:
        Combined OptimizationResult
    """
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
        metadata=OptimizationMetadata(
            phase1_files=len(phase1.selected_files),
            phase2_files=len(phase2.selected_files),
            phase2_sections=len(phase2.selected_sections),
        ),
    )


def get_excluded_files(
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
        for file_name in files_content
        if file_name not in selected_files and file_name not in selected_sections
    ]
