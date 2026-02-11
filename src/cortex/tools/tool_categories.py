"""Tool categorization for Anthropic Tool Search feature.

Categorizes all Cortex MCP tools into loading priority tiers to support
deferred tool loading. Tools are classified as:

- **always_loaded**: Core tools used in nearly every session (file ops,
  validation, quality gates, implement-workflow helpers).
- **deferred_medium**: Tools used in specific workflows but not every
  session (refactoring, analysis, link ops, synapse, configuration).
- **deferred_low**: Rarely used admin/analytics tools (usage analytics,
  script capture, rollback, corruption fix).

Categorization is based on tool purpose and observed usage patterns from
the implement-prompt workflow. When Phase 29 usage analytics data is
available, categories can be refined with empirical frequency data.

Reference: Phase 49 – Introduce Anthropic Advanced Tool Use Features.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict

# Type alias for category names used in function signatures.
ToolCategoryName = Literal["always_loaded", "deferred_medium", "deferred_low"]


class ToolCategory(str, Enum):
    """Loading priority tier for an MCP tool."""

    ALWAYS_LOADED = "always_loaded"
    DEFERRED_MEDIUM = "deferred_medium"
    DEFERRED_LOW = "deferred_low"


class ToolCategoryEntry(BaseModel):
    """Single tool-to-category mapping with rationale."""

    model_config = ConfigDict(frozen=True)

    name: str
    category: ToolCategory
    rationale: str


class ToolCategoryConfig(BaseModel):
    """Serializable categorization configuration for optimization.json."""

    model_config = ConfigDict(frozen=True)

    enabled: bool = False
    always_loaded: list[str] = []
    deferred_medium: list[str] = []
    deferred_low: list[str] = []


# ---------------------------------------------------------------------------
# Canonical tool → category mapping
# ---------------------------------------------------------------------------

TOOL_CATEGORIES: tuple[ToolCategoryEntry, ...] = (
    # ── Always loaded (core workflow) ─────────────────────────────────
    ToolCategoryEntry(
        name="manage_file",
        category=ToolCategory.ALWAYS_LOADED,
        rationale="Core file read/write/metadata used every session",
    ),
    ToolCategoryEntry(
        name="write_file",
        category=ToolCategory.ALWAYS_LOADED,
        rationale="Core file write shortcut used every session",
    ),
    ToolCategoryEntry(
        name="validate",
        category=ToolCategory.ALWAYS_LOADED,
        rationale="Core validation (schema, quality, roadmap_sync) in workflow",
    ),
    ToolCategoryEntry(
        name="load_context",
        category=ToolCategory.ALWAYS_LOADED,
        rationale="Called at session start for every task",
    ),
    ToolCategoryEntry(
        name="get_memory_bank_stats",
        category=ToolCategory.ALWAYS_LOADED,
        rationale="Monitoring token budget and memory bank health",
    ),
    ToolCategoryEntry(
        name="rules",
        category=ToolCategory.ALWAYS_LOADED,
        rationale="Loaded at start of implement workflow for coding standards",
    ),
    ToolCategoryEntry(
        name="add_roadmap_entry",
        category=ToolCategory.ALWAYS_LOADED,
        rationale="Used in plan-creation and implement workflows",
    ),
    ToolCategoryEntry(
        name="remove_roadmap_entry",
        category=ToolCategory.ALWAYS_LOADED,
        rationale="Used in implement workflow step 5 (memory bank update)",
    ),
    ToolCategoryEntry(
        name="complete_plan",
        category=ToolCategory.ALWAYS_LOADED,
        rationale="Used in implement workflow step 5 for plan completion",
    ),
    ToolCategoryEntry(
        name="append_progress_entry",
        category=ToolCategory.ALWAYS_LOADED,
        rationale="Used in implement workflow step 5 (progress update)",
    ),
    ToolCategoryEntry(
        name="append_active_context_entry",
        category=ToolCategory.ALWAYS_LOADED,
        rationale="Used in implement workflow step 5 (active context update)",
    ),
    ToolCategoryEntry(
        name="execute_pre_commit_checks",
        category=ToolCategory.ALWAYS_LOADED,
        rationale="Quality gate mandatory before every commit",
    ),
    ToolCategoryEntry(
        name="fix_quality_issues",
        category=ToolCategory.ALWAYS_LOADED,
        rationale="Auto-fix lint/format/type errors in every session",
    ),
    ToolCategoryEntry(
        name="check_mcp_connection_health",
        category=ToolCategory.ALWAYS_LOADED,
        rationale="Health check for MCP connection diagnostics",
    ),
    ToolCategoryEntry(
        name="get_structure_info",
        category=ToolCategory.ALWAYS_LOADED,
        rationale="Project path discovery used in every implement session",
    ),
    # ── Deferred medium (specific workflows) ──────────────────────────
    ToolCategoryEntry(
        name="analyze",
        category=ToolCategory.DEFERRED_MEDIUM,
        rationale="Periodic memory bank analysis (usage, structure, insights)",
    ),
    ToolCategoryEntry(
        name="load_progressive_context",
        category=ToolCategory.DEFERRED_MEDIUM,
        rationale="Alternative context loading strategy",
    ),
    ToolCategoryEntry(
        name="summarize_content",
        category=ToolCategory.DEFERRED_MEDIUM,
        rationale="Token reduction when budget is tight",
    ),
    ToolCategoryEntry(
        name="get_relevance_scores",
        category=ToolCategory.DEFERRED_MEDIUM,
        rationale="File prioritization before loading context",
    ),
    ToolCategoryEntry(
        name="suggest_refactoring",
        category=ToolCategory.DEFERRED_MEDIUM,
        rationale="Refactoring workflow (consolidation, splits, reorg)",
    ),
    ToolCategoryEntry(
        name="apply_refactoring",
        category=ToolCategory.DEFERRED_MEDIUM,
        rationale="Execute approved refactoring suggestions",
    ),
    ToolCategoryEntry(
        name="configure",
        category=ToolCategory.DEFERRED_MEDIUM,
        rationale="View/update validation/optimization/learning config",
    ),
    ToolCategoryEntry(
        name="update_config",
        category=ToolCategory.DEFERRED_MEDIUM,
        rationale="Write-only config updates",
    ),
    ToolCategoryEntry(
        name="get_version_history",
        category=ToolCategory.DEFERRED_MEDIUM,
        rationale="File version inspection before rollback decisions",
    ),
    ToolCategoryEntry(
        name="get_dependency_graph",
        category=ToolCategory.DEFERRED_MEDIUM,
        rationale="Dependency visualization for architecture tasks",
    ),
    ToolCategoryEntry(
        name="parse_file_links",
        category=ToolCategory.DEFERRED_MEDIUM,
        rationale="Link extraction for specific file analysis",
    ),
    ToolCategoryEntry(
        name="get_link_graph",
        category=ToolCategory.DEFERRED_MEDIUM,
        rationale="Cross-file link visualization",
    ),
    ToolCategoryEntry(
        name="validate_links",
        category=ToolCategory.DEFERRED_MEDIUM,
        rationale="Broken link detection in memory bank",
    ),
    ToolCategoryEntry(
        name="resolve_transclusions",
        category=ToolCategory.DEFERRED_MEDIUM,
        rationale="Expand transclusion directives in files",
    ),
    ToolCategoryEntry(
        name="fix_markdown_lint",
        category=ToolCategory.DEFERRED_MEDIUM,
        rationale="Markdown formatting fixes (part of quality workflow)",
    ),
    ToolCategoryEntry(
        name="create_plan",
        category=ToolCategory.DEFERRED_MEDIUM,
        rationale="Plan creation workflow",
    ),
    ToolCategoryEntry(
        name="register_plan_in_roadmap",
        category=ToolCategory.DEFERRED_MEDIUM,
        rationale="Plan registration in roadmap",
    ),
    ToolCategoryEntry(
        name="run_preflight_checks",
        category=ToolCategory.DEFERRED_MEDIUM,
        rationale="Commit pipeline Phase A preflight",
    ),
    ToolCategoryEntry(
        name="run_docs_and_memory_bank_sync",
        category=ToolCategory.DEFERRED_MEDIUM,
        rationale="Commit pipeline Phase B docs/memory bank sync",
    ),
    ToolCategoryEntry(
        name="sync_synapse",
        category=ToolCategory.DEFERRED_MEDIUM,
        rationale="Synapse repo pull/push operations",
    ),
    ToolCategoryEntry(
        name="get_synapse_rules",
        category=ToolCategory.DEFERRED_MEDIUM,
        rationale="Retrieve Synapse rules for task context",
    ),
    ToolCategoryEntry(
        name="get_synapse_prompts",
        category=ToolCategory.DEFERRED_MEDIUM,
        rationale="Retrieve Synapse prompt templates",
    ),
    ToolCategoryEntry(
        name="check_structure_health",
        category=ToolCategory.DEFERRED_MEDIUM,
        rationale="Project structure health check and cleanup",
    ),
    ToolCategoryEntry(
        name="sequentialthinking",
        category=ToolCategory.DEFERRED_MEDIUM,
        rationale="Stepwise reasoning for complex planning",
    ),
    ToolCategoryEntry(
        name="read_cache_json",
        category=ToolCategory.DEFERRED_MEDIUM,
        rationale="Concurrent-safe cache reads",
    ),
    ToolCategoryEntry(
        name="write_cache_json",
        category=ToolCategory.DEFERRED_MEDIUM,
        rationale="Concurrent-safe cache writes",
    ),
    ToolCategoryEntry(
        name="analyze_context_effectiveness",
        category=ToolCategory.DEFERRED_MEDIUM,
        rationale="End-of-session context analysis",
    ),
    # ── Deferred low (admin / analytics / rare) ───────────────────────
    ToolCategoryEntry(
        name="analyze_health_check",
        category=ToolCategory.DEFERRED_LOW,
        rationale="Prompts/rules/tools merge analysis (admin)",
    ),
    ToolCategoryEntry(
        name="provide_feedback",
        category=ToolCategory.DEFERRED_LOW,
        rationale="Refactoring feedback for learning engine",
    ),
    ToolCategoryEntry(
        name="rollback_file_version",
        category=ToolCategory.DEFERRED_LOW,
        rationale="Rare undo operation for memory bank files",
    ),
    ToolCategoryEntry(
        name="fix_roadmap_corruption",
        category=ToolCategory.DEFERRED_LOW,
        rationale="One-time corruption repair",
    ),
    ToolCategoryEntry(
        name="update_synapse_rule",
        category=ToolCategory.DEFERRED_LOW,
        rationale="Modify shared rules (rare admin action)",
    ),
    ToolCategoryEntry(
        name="update_synapse_prompt",
        category=ToolCategory.DEFERRED_LOW,
        rationale="Modify shared prompts (rare admin action)",
    ),
    ToolCategoryEntry(
        name="get_usage_observation",
        category=ToolCategory.DEFERRED_LOW,
        rationale="Single usage event inspection (analytics)",
    ),
    ToolCategoryEntry(
        name="get_usage_events",
        category=ToolCategory.DEFERRED_LOW,
        rationale="Batch usage event retrieval (analytics)",
    ),
    ToolCategoryEntry(
        name="get_tool_usage_stats",
        category=ToolCategory.DEFERRED_LOW,
        rationale="Tool usage frequency statistics (analytics)",
    ),
    ToolCategoryEntry(
        name="get_unused_tools",
        category=ToolCategory.DEFERRED_LOW,
        rationale="Identify unused tools for deprecation (analytics)",
    ),
    ToolCategoryEntry(
        name="search_usage",
        category=ToolCategory.DEFERRED_LOW,
        rationale="Search usage events by query/filter (analytics)",
    ),
    ToolCategoryEntry(
        name="get_usage_timeline",
        category=ToolCategory.DEFERRED_LOW,
        rationale="Chronological usage context (analytics)",
    ),
    ToolCategoryEntry(
        name="get_tool_usage_report",
        category=ToolCategory.DEFERRED_LOW,
        rationale="Comprehensive usage report generation (analytics)",
    ),
    ToolCategoryEntry(
        name="get_optimization_recommendations",
        category=ToolCategory.DEFERRED_LOW,
        rationale="Tool optimization suggestions (analytics)",
    ),
    ToolCategoryEntry(
        name="get_context_usage_statistics",
        category=ToolCategory.DEFERRED_LOW,
        rationale="Context usage metrics (analytics)",
    ),
    ToolCategoryEntry(
        name="capture_session_script",
        category=ToolCategory.DEFERRED_LOW,
        rationale="Record session scripts for promotion review",
    ),
    ToolCategoryEntry(
        name="list_session_scripts",
        category=ToolCategory.DEFERRED_LOW,
        rationale="List captured scripts (admin)",
    ),
    ToolCategoryEntry(
        name="analyze_session_scripts",
        category=ToolCategory.DEFERRED_LOW,
        rationale="Script analysis for promotion (admin)",
    ),
    ToolCategoryEntry(
        name="suggest_tool_improvements",
        category=ToolCategory.DEFERRED_LOW,
        rationale="Recommend existing tools before generating scripts",
    ),
    ToolCategoryEntry(
        name="promote_session_script",
        category=ToolCategory.DEFERRED_LOW,
        rationale="Promote captured script to permanent tool (admin)",
    ),
    ToolCategoryEntry(
        name="cleanup_metadata_index",
        category=ToolCategory.DEFERRED_LOW,
        rationale="One-time metadata index cleanup (admin)",
    ),
)


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------

# Indexed mapping: tool name → entry (built once at import time).
_TOOL_CATEGORY_INDEX: dict[str, ToolCategoryEntry] = {
    entry.name: entry for entry in TOOL_CATEGORIES
}


def get_tool_category(tool_name: str) -> ToolCategory | None:
    """Return the category for *tool_name*, or ``None`` if not catalogued."""
    entry = _TOOL_CATEGORY_INDEX.get(tool_name)
    return entry.category if entry else None


def get_tools_by_category(
    category: ToolCategory,
) -> list[ToolCategoryEntry]:
    """Return all entries belonging to *category*."""
    return [e for e in TOOL_CATEGORIES if e.category == category]


def get_always_loaded_tool_names() -> list[str]:
    """Return sorted list of tool names that should always be loaded."""
    return sorted(
        e.name for e in TOOL_CATEGORIES if e.category == ToolCategory.ALWAYS_LOADED
    )


def get_deferred_tool_names() -> list[str]:
    """Return sorted list of tool names that can be deferred."""
    return sorted(
        e.name
        for e in TOOL_CATEGORIES
        if e.category in (ToolCategory.DEFERRED_MEDIUM, ToolCategory.DEFERRED_LOW)
    )


def build_category_config() -> ToolCategoryConfig:
    """Build a :class:`ToolCategoryConfig` from the canonical mapping."""
    always = get_always_loaded_tool_names()
    medium = sorted(
        e.name for e in TOOL_CATEGORIES if e.category == ToolCategory.DEFERRED_MEDIUM
    )
    low = sorted(
        e.name for e in TOOL_CATEGORIES if e.category == ToolCategory.DEFERRED_LOW
    )
    return ToolCategoryConfig(
        enabled=False,
        always_loaded=always,
        deferred_medium=medium,
        deferred_low=low,
    )


def get_category_summary() -> dict[str, int]:
    """Return a count of tools per category."""
    return {cat.value: len(get_tools_by_category(cat)) for cat in ToolCategory}
