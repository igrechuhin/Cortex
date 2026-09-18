"""Execution subpackage: pre-commit, quality, and safe execution.

Contains:
- safe_execution: apply_refactoring
- feedback: provide_feedback
- configure_learning (via safe_execution)
"""

# Import for side-effect registration (MCP tools)
from . import (
    composite_tools,
    feedback,
    pre_commit_zero_arg_tools,
    safe_execution,
)
from .safe_execution import apply_refactoring

__all__ = [
    "apply_refactoring",
    "composite_tools",
    "feedback",
    "pre_commit_zero_arg_tools",
    "safe_execution",
]
