"""
MCP tool implementations and related modules under ``src/cortex/tools``.

**Published MCP surface:** the tools the server registers for clients are listed in
:data:`~cortex.tools.structure.categories.TOOL_CATEGORIES` (see also
:mod:`cortex.discovery.published_inventory`). Submodules here include handlers
that are internal, consolidated, or exposed only via resources — do not infer
the live ``tools/list`` from this package layout alone.
"""

# Import all tool modules to register their decorators
from . import (
    cache_json_tools,  # noqa: F401
    config,  # noqa: F401 - registers configure tool and get_config_resource
    evaluation,  # noqa: F401
    execution,  # noqa: F401
    optimization,  # noqa: F401
    prompts,  # noqa: F401
    refactoring,  # noqa: F401
    skill_pack,  # noqa: F401
    structure,  # noqa: F401
    validation,  # noqa: F401
)
from .context import (
    analysis_operations,  # noqa: F401
    analysis_usage,  # noqa: F401
)
from .evaluation import evaluation_optimization_helpers, model_benchmark  # noqa: F401
from .execution import composite_tools  # noqa: F401 - backward compat
from .files import (
    markdown_operations,  # noqa: F401
)
from .files import (
    operations as file_operations,  # noqa: F401 - alias for backward compat
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
    update_memory_bank,  # noqa: F401
)
from .session import (  # noqa: F401  # noqa: F401
    connection_health,
    health_check_operations,
    pipeline_handoff,  # noqa: F401
    registry,
    script_capture_tools,  # noqa: F401
    sequential_thinking,  # noqa: F401
    task_locking,
)
from .session import (
    dispatcher as session_dispatcher,
)
from .session import (
    start_tools as session_start_tools,
)
from .skill_pack import operations as skill_pack_operations  # noqa: F401
from .structure import tool_search as tool_search_operations  # noqa: F401
from .synapse import (  # noqa: F401
    prompts as synapse_prompts,
)
from .synapse import (
    rules_operations,
)
from .synapse import (
    tools as synapse_tools,
)
from .usage import query_operations, usage_analytics  # noqa: F401

# Explicitly reference modules imported for side effects to satisfy type checker
_ = skill_pack
_ = plan
_ = update_memory_bank
_ = synapse_prompts

__all__ = [
    "analysis_operations",
    "cache_json_tools",
    "compaction_operations",
    "config",
    "composite_tools",
    "connection_health",
    "pipeline_handoff",
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
    "query_operations",
    "sequential_thinking",
    "session_dispatcher",
    "registry",
    "session_start_tools",
    "tool_search_operations",  # alias for structure.tool_search
    "operations",
    "plan",
    "register",
    "update_memory_bank",
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
]
