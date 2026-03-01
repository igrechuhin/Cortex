"""
Tools Package

This package contains all MCP tool implementations organized by phase.

Modules:
- file_operations: File management operations (1 tool) - Phase 9.1.1 split
- validation_operations: Validation operations (1 tool) - Phase 9.1.1 split
- analysis_operations: Analysis operations (1 tool) - Phase 9.1.1 split
- refactoring_operations: Refactoring suggestions (1 tool) - Split from
  analysis_operations
- rules_operations: Rules management (1 tool) - Phase 9.1.1 split
- configuration_operations: Configuration management (1 tool) - Phase 9.1.1 split
- markdown_operations: Markdown file operations (1 tool) - Markdown lint fixing
- phase1_foundation_*: Core Memory Bank operations (4 tools split across modules)
- phase2_linking: Link management and transclusion (4 tools)
- phase3_validation: Validation and quality checks (5 tools)
- phase4_optimization: Token optimization and context management (7 tools)
- phase5_analysis: Usage pattern and structure analysis (3 tools)
- phase5_refactoring: Refactoring suggestions (4 tools)
- phase5_execution: Safe execution and learning (6 tools)
- synapse_tools: Synapse repository tools for rules and prompts (5 tools)
- phase8_structure: Project structure management (6 tools)
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
    analysis_operations,  # noqa: F401
    append_entry_dispatcher,  # noqa: F401
    cache_json_tools,  # noqa: F401
    compaction_operations,  # noqa: F401
    composite_tools,  # noqa: F401
    configuration_hybrid,  # noqa: F401
    configuration_operations,  # noqa: F401
    connection_health,  # noqa: F401
    file_operations,  # noqa: F401
    health_check_operations,  # noqa: F401
    markdown_operations,  # noqa: F401
    phase1_foundation_dependency,  # noqa: F401
    phase1_foundation_rollback,  # noqa: F401
    phase1_foundation_stats,  # noqa: F401
    phase1_foundation_version,  # noqa: F401
    phase2_linking,  # noqa: F401
    phase3_validation,  # noqa: F401
    phase4_optimization,  # noqa: F401
    phase5_analysis,  # noqa: F401
    phase5_evaluation,  # noqa: F401
    phase5_evaluation_optimization_helpers,  # noqa: F401
    phase5_execution,  # noqa: F401
    phase5_execution_feedback,  # noqa: F401
    phase5_model_benchmark,  # noqa: F401
    phase5_refactoring,  # noqa: F401
    phase8_structure,  # noqa: F401
    plan_completion,  # noqa: F401
    plan_dispatcher,  # noqa: F401
    plan_operations,  # noqa: F401
    pre_commit_tools,  # noqa: F401
    prompts,  # noqa: F401
    query_memory_bank_operations,  # noqa: F401
    query_usage_operations,  # noqa: F401
    refactoring_operations,  # noqa: F401
    roadmap_corruption,  # noqa: F401
    roadmap_dispatcher,  # noqa: F401
    roadmap_operations,  # noqa: F401
    rules_operations,  # noqa: F401
    script_capture_tools,  # noqa: F401
    sequential_thinking,  # noqa: F401
    session_dispatcher,  # noqa: F401
    session_registry,  # noqa: F401
    session_start_tools,  # noqa: F401
    skill_pack_operations,  # noqa: F401
    synapse_prompts,  # noqa: F401  # Dynamic Synapse prompts registration
    synapse_tools,  # noqa: F401
    task_locking,  # noqa: F401
    tool_search_operations,  # noqa: F401
    usage_analytics,  # noqa: F401
    validation_operations,  # noqa: F401
    workflow_operations,  # noqa: F401
)

# Explicitly reference modules imported for side effects to satisfy type checker
_ = append_entry_dispatcher
_ = phase5_execution_feedback
_ = plan_dispatcher
_ = roadmap_dispatcher
_ = synapse_prompts

__all__ = [
    "append_entry_dispatcher",
    "analysis_operations",
    "cache_json_tools",
    "compaction_operations",
    "configuration_hybrid",
    "configuration_operations",
    "composite_tools",
    "connection_health",
    "file_operations",
    "health_check_operations",
    "markdown_operations",
    "phase1_foundation_dependency",
    "phase1_foundation_rollback",
    "phase1_foundation_stats",
    "phase1_foundation_version",
    "phase2_linking",
    "phase3_validation",
    "phase4_optimization",
    "phase5_analysis",
    "phase5_evaluation",
    "phase5_evaluation_optimization_helpers",
    "phase5_model_benchmark",
    "phase5_refactoring",
    "phase5_execution",
    "synapse_tools",
    "roadmap_corruption",
    "roadmap_operations",
    "plan_completion",
    "query_memory_bank_operations",
    "query_usage_operations",
    "sequential_thinking",
    "session_dispatcher",
    "session_registry",
    "session_start_tools",
    "tool_search_operations",
    "plan_operations",
    "phase8_structure",
    "pre_commit_tools",
    "prompts",
    "refactoring_operations",
    "rules_operations",
    "script_capture_tools",
    "skill_pack_operations",
    "synapse_prompts",
    "task_locking",
    "usage_analytics",
    "validation_operations",
    "workflow_operations",
]
