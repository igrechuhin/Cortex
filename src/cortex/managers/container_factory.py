"""Factory methods for creating manager instances.

This module orchestrates creation of all manager groups and re-exports
types and create_* functions for backward compatibility.
"""

from pathlib import Path

from .container_analysis import create_analysis_managers_from_deps
from .container_config import (
    AllManagers,
    AnalysisManagers,
    ExecutionManagers,
    FoundationManagers,
    LinkingManagers,
    OptimizationManagers,
    RefactoringManagers,
)
from .container_execution import create_execution_managers_from_deps
from .container_foundation import create_foundation_managers
from .container_linking import create_linking_managers_from_foundation
from .container_optimization import create_optimization_managers_from_deps
from .container_refactoring import create_refactoring_managers_from_optimization


def create_all_managers(
    project_root: Path,
) -> AllManagers:
    """Create all managers grouped by phase.

    Args:
        project_root: Project root directory

    Returns:
        Tuple of manager groups: (foundation, linking, optimization,
        analysis, refactoring, execution)
    """
    foundation_managers = create_foundation_managers(project_root)
    linking_managers = create_linking_managers_from_foundation(foundation_managers)
    optimization_managers = create_optimization_managers_from_deps(
        project_root, foundation_managers
    )
    analysis_managers = create_analysis_managers_from_deps(
        project_root, foundation_managers
    )
    refactoring_managers = create_refactoring_managers_from_optimization(
        project_root, optimization_managers
    )
    execution_managers = create_execution_managers_from_deps(
        project_root, foundation_managers, linking_managers, optimization_managers
    )

    return (
        foundation_managers,
        linking_managers,
        optimization_managers,
        analysis_managers,
        refactoring_managers,
        execution_managers,
    )


__all__ = [
    "AllManagers",
    "AnalysisManagers",
    "ExecutionManagers",
    "FoundationManagers",
    "LinkingManagers",
    "OptimizationManagers",
    "RefactoringManagers",
    "create_all_managers",
    "create_analysis_managers_from_deps",
    "create_execution_managers_from_deps",
    "create_foundation_managers",
    "create_linking_managers_from_foundation",
    "create_optimization_managers_from_deps",
    "create_refactoring_managers_from_optimization",
]
