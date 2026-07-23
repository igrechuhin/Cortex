"""Optimization subpackage: progressive loading, relevance, summarization.

Phase 4: Token Optimization Tools

This package contains tools for context loading, content summarization,
and relevance scoring.

Total: 3 tools, 3 resources (rules tools moved to consolidated.py)
- load_context (resource: cortex://context)
- summarize_content / summarize_content_resource
- get_relevance_scores / get_relevance_scores_resource

Note: index_rules and get_relevant_rules have been consolidated into
rules() tool in consolidated.py
load_progressive_context has been merged into load_context with strategy="progressive"

This package serves as a backward-compatible facade that imports
from the split modules.
"""

# Re-export all tools and resources from the handlers module
# Re-export dependencies needed for testing
from cortex.managers.initialization import get_managers, get_project_root
from cortex.managers.utils import get_manager

from .handlers import (
    get_relevance_scores,
    get_relevance_scores_resource,
    is_non_trivial_task,
    load_context,
    load_context_impl,
    summarize_content,
    summarize_content_resource,
)
from .propose_framework_optimization import (
    propose_framework_optimization,  # noqa: F401 - registers @mcp.tool()
)

__all__ = [
    "get_managers",
    "get_project_root",
    "get_manager",
    "get_relevance_scores",
    "get_relevance_scores_resource",
    "is_non_trivial_task",
    "load_context",
    "load_context_impl",
    "propose_framework_optimization",
    "summarize_content",
    "summarize_content_resource",
]
