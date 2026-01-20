"""
Phase 4: Token Optimization Tools

This module contains tools for context loading, progressive loading,
content summarization, and relevance scoring.

Total: 4 tools (rules tools moved to consolidated.py)
- load_context
- load_progressive_context
- summarize_content
- get_relevance_scores

Note: index_rules and get_relevant_rules have been consolidated into rules() tool in consolidated.py

This module now serves as a backward-compatible facade that imports from the split modules.
"""

# Re-export all tools from the handlers module
# Re-export dependencies needed for testing
from cortex.managers.initialization import get_managers, get_project_root
from cortex.managers.manager_utils import get_manager
from cortex.tools.phase4_optimization_handlers import (
    get_relevance_scores,
    load_context,
    load_progressive_context,
    summarize_content,
)

__all__ = [
    "load_context",
    "load_progressive_context",
    "summarize_content",
    "get_relevance_scores",
    "get_managers",
    "get_project_root",
    "get_manager",
]
