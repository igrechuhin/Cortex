"""Manager initialization and lifecycle management."""

from .container_factory import (
    AnalysisManagers,
    ExecutionManagers,
    FoundationManagers,
    LinkingManagers,
    OptimizationManagers,
    RefactoringManagers,
    create_all_managers,
)
from .initialization import get_managers, get_project_root, handle_file_change

__all__ = [
    # Container factory
    "AnalysisManagers",
    "ExecutionManagers",
    "FoundationManagers",
    "LinkingManagers",
    "OptimizationManagers",
    "RefactoringManagers",
    "create_all_managers",
    # Initialization
    "get_managers",
    "get_project_root",
    "handle_file_change",
]
