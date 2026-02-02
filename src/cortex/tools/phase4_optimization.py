"""
Phase 4: Token Optimization Tools

This module contains tools for context loading, progressive loading,
content summarization, and relevance scoring.

Total: 6 tools, 4 resources (rules tools moved to consolidated.py)
- load_context / load_context_resource
- load_progressive_context / load_progressive_context_resource
- summarize_content / summarize_content_resource
- get_relevance_scores / get_relevance_scores_resource
- analyze_context_effectiveness
- get_context_usage_statistics

Note: index_rules and get_relevant_rules have been consolidated into
rules() tool in consolidated.py

This module now serves as a backward-compatible facade that imports
from the split modules.
"""

# Re-export all tools and resources from the handlers module
# Re-export dependencies needed for testing
from cortex.managers.initialization import get_managers, get_project_root
from cortex.managers.manager_utils import get_manager
from cortex.tools.context_analysis_handlers import (
    analyze_context_effectiveness,
    get_context_usage_statistics,
)
from cortex.tools.phase4_optimization_handlers import (
    get_relevance_scores,
    get_relevance_scores_resource,
    load_context,
    load_context_resource,
    load_progressive_context,
    load_progressive_context_resource,
    summarize_content,
    summarize_content_resource,
)

__all__ = [
    "load_context",
    "load_context_resource",
    "load_progressive_context",
    "load_progressive_context_resource",
    "summarize_content",
    "summarize_content_resource",
    "get_relevance_scores",
    "get_relevance_scores_resource",
    "analyze_context_effectiveness",
    "get_context_usage_statistics",
    "get_managers",
    "get_project_root",
    "get_manager",
]
