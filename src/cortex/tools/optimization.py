"""
Phase 4: Token Optimization Tools

This module contains tools for context loading, content summarization,
and relevance scoring.

Total: 3 tools, 3 resources (rules tools moved to consolidated.py)
- load_context / load_context_resource
- summarize_content / summarize_content_resource
- get_relevance_scores / get_relevance_scores_resource

Note: index_rules and get_relevant_rules have been consolidated into
rules() tool in consolidated.py
load_progressive_context has been merged into load_context with strategy="progressive"

This module now serves as a backward-compatible facade that imports
from the split modules.
"""

# Re-export all tools and resources from the handlers module
# Re-export dependencies needed for testing
from cortex.managers.initialization import get_managers, get_project_root
from cortex.managers.manager_utils import get_manager
from cortex.tools.optimization_handlers import (
    get_relevance_scores,
    get_relevance_scores_resource,
    load_context,
    load_context_resource,
    summarize_content,
    summarize_content_resource,
)

__all__ = [
    "load_context",
    "load_context_resource",
    "summarize_content",
    "summarize_content_resource",
    "get_relevance_scores",
    "get_relevance_scores_resource",
    "get_managers",
    "get_project_root",
    "get_manager",
]
