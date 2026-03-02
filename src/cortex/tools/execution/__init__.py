"""Execution subpackage: pre-commit, quality, and safe execution.

Contains:
- pre_commit_tools: execute_pre_commit_checks, fix_quality_issues
- safe_execution: apply_refactoring
- feedback: provide_feedback
- configure_learning (via safe_execution)
"""

# Import for side-effect registration (MCP tools)
from . import feedback, pre_commit_tools, safe_execution
from .safe_execution import apply_refactoring

__all__ = [
    "apply_refactoring",
    "feedback",
    "pre_commit_tools",
    "safe_execution",
]
