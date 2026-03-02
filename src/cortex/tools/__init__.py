"""
Tools Package

This package contains all MCP tool implementations organized by phase.

Modules:
- file_operations: File management operations (1 tool) - Phase 9.1.1 split
- validation.operations: Validation operations (1 tool) - Phase 9.1.1 split
- analysis_operations: Analysis operations (1 tool) - Phase 9.1.1 split
- refactoring: Refactoring suggestions (1 tool, 1 resource) - suggest_refactoring
- rules_operations: Rules management (1 tool) - Phase 9.1.1 split
- configuration_operations: Configuration management (1 tool) - Phase 9.1.1 split
- markdown_operations: Markdown file operations (1 tool) - Markdown lint fixing
- foundation_*: Core Memory Bank operations (4 tools split across modules)
- linking_operations: Link management and transclusion (4 tools)
- validation: Validation and quality checks (validate tool)
- optimization: Token optimization and context management (7 tools)
- analysis_usage: Usage pattern and structure analysis (3 tools)
- execution: Safe execution and learning (6 tools)
- synapse_tools: Synapse repository tools for rules and prompts (5 tools)
- structure: Project structure management (6 tools)
- prompts: MCP prompt templates for one-time operations (7 prompts)
- script_capture_tools: Session script capture, analysis, promotion (5 tools)
- usage_analytics: Tool usage statistics and optimization (4 tools) - Phase 29
- cache_json_tools: Concurrent-safe read/write of .cortex/.cache JSON (1 tool: cache_json)
- roadmap_operations: Roadmap entry management (1 tool)
- plan_operations: Structured plan creation and roadmap registration (2 tools)
- plan_completion: Complete plan (move from roadmap to activeContext) (1 tool)
- sequential_thinking: Unified think tool (lightweight + full sequential mode)
- compaction_operations: Session compaction and handoff (1 tool) - Phase 56
Total: 71 tools + 7 prompts
"""

# Import all tool modules to register their decorators
from . import (
    append_entry_dispatcher,  # noqa: F401
    cache_json_tools,  # noqa: F401
    composite_tools,  # noqa: F401
    config,  # noqa: F401 - registers configure tool and get_config_resource
    evaluation,  # noqa: F401
    execution,  # noqa: F401
    health_check_operations,  # noqa: F401
    optimization,  # noqa: F401
    prompts,  # noqa: F401
    query_usage_operations,  # noqa: F401
    refactoring,  # noqa: F401
    script_capture_tools,  # noqa: F401
    sequential_thinking,  # noqa: F401
    skill_pack_operations,  # noqa: F401
    structure,  # noqa: F401
    task_locking,  # noqa: F401
    tool_search_operations,  # noqa: F401
    validation,  # noqa: F401
    workflow_operations,  # noqa: F401
)
from .context import (
    analysis_operations,  # noqa: F401
    analysis_usage,  # noqa: F401
)
from .evaluation import evaluation_optimization_helpers, model_benchmark  # noqa: F401
from .files import (
    file_operations,  # noqa: F401
    markdown_operations,  # noqa: F401
)
from .linking import linking_operations  # noqa: F401
from .memory import (
    compaction_operations,  # noqa: F401
    foundation_dependency,  # noqa: F401
    foundation_rollback,  # noqa: F401
    foundation_stats,  # noqa: F401
    foundation_version,  # noqa: F401
    query_memory_bank_operations,  # noqa: F401
)
from .plans import (
    completion,  # noqa: F401
    corruption,  # noqa: F401
    entries,  # noqa: F401
    operations,  # noqa: F401
    plan,  # noqa: F401
    register,  # noqa: F401
    roadmap,  # noqa: F401
)
from .session import (  # noqa: F401
    connection_health,
    registry,
)
from .session import (
    dispatcher as session_dispatcher,
)
from .session import (
    start_tools as session_start_tools,
)
from .synapse import (  # noqa: F401
    prompts as synapse_prompts,
)
from .synapse import (
    rules_operations,
)
from .synapse import (
    tools as synapse_tools,
)
from .usage import usage_analytics  # noqa: F401

# Explicitly reference modules imported for side effects to satisfy type checker
_ = append_entry_dispatcher
_ = plan
_ = roadmap
_ = synapse_prompts

__all__ = [
    "append_entry_dispatcher",
    "analysis_operations",
    "cache_json_tools",
    "compaction_operations",
    "config",
    "composite_tools",
    "connection_health",
    "file_operations",
    "health_check_operations",
    "markdown_operations",
    "foundation_dependency",
    "foundation_rollback",
    "foundation_stats",
    "foundation_version",
    "linking_operations",
    "optimization",
    "analysis_usage",
    "evaluation",
    "evaluation_optimization_helpers",
    "model_benchmark",
    "execution",
    "synapse_tools",
    "completion",
    "corruption",
    "entries",
    "query_memory_bank_operations",
    "query_usage_operations",
    "sequential_thinking",
    "session_dispatcher",
    "registry",
    "session_start_tools",
    "tool_search_operations",
    "operations",
    "plan",
    "register",
    "roadmap",
    "structure",
    "prompts",
    "refactoring",
    "rules_operations",
    "script_capture_tools",
    "skill_pack_operations",
    "synapse_prompts",
    "task_locking",
    "usage_analytics",
    "validation",
    "workflow_operations",
]
