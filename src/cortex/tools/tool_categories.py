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

import re
from enum import Enum

from pydantic import BaseModel, ConfigDict

# Tool budget constraints (see tool consolidation plans).
# MAX_REGISTERED_TOOLS is enforced by governance tests; if new tools are added,
# either consolidate/remove other tools or explicitly raise this constant in
# tandem with the consolidation plans and documentation.
MAX_REGISTERED_TOOLS = 51

# Long-term target from consolidation plans (not enforced in tests).
TARGET_REGISTERED_TOOLS = 24


# Type alias for category names used in function signatures.
class ToolCategory(str, Enum):
    """Loading priority tier for an MCP tool."""

    ALWAYS_LOADED = "always_loaded"
    DEFERRED_MEDIUM = "deferred_medium"
    DEFERRED_LOW = "deferred_low"


# Type alias for backward compatibility.
ToolCategoryName = ToolCategory


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
        name="query_memory_bank",
        category=ToolCategory.ALWAYS_LOADED,
        rationale="Memory bank stats, version history, graphs, links, validation (Phase 50)",
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
        name="remove_roadmap_section",
        category=ToolCategory.ALWAYS_LOADED,
        rationale="Used in implement workflow step 5 to remove orphan sections without full-content write",
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
    ToolCategoryEntry(
        name="search_tools",
        category=ToolCategory.ALWAYS_LOADED,
        rationale="Discover deferred tools by query when tool search is enabled",
    ),
    ToolCategoryEntry(
        name="list_available_tools",
        category=ToolCategory.ALWAYS_LOADED,
        rationale="List tools by tier (agent-skills Step 3 tool discovery)",
    ),
    ToolCategoryEntry(
        name="session_start",
        category=ToolCategory.ALWAYS_LOADED,
        rationale="Session orientation brief used at the start of non-trivial tasks",
    ),
    # ── Deferred medium (specific workflows) ──────────────────────────
    ToolCategoryEntry(
        name="analyze",
        category=ToolCategory.DEFERRED_MEDIUM,
        rationale="Periodic memory bank analysis (usage, structure, insights)",
    ),
    ToolCategoryEntry(
        name="summarize_content",
        category=ToolCategory.DEFERRED_MEDIUM,
        rationale="Token reduction when budget is tight",
    ),
    ToolCategoryEntry(
        name="run_tool_evaluation",
        category=ToolCategory.DEFERRED_MEDIUM,
        rationale="Evaluation framework for MCP tools (Phase 57)",
    ),
    ToolCategoryEntry(
        name="benchmark_model",
        category=ToolCategory.DEFERRED_MEDIUM,
        rationale="Eval-guided model upgrade: run full eval, store and compare (Phase 57 extension)",
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
        name="sync_synapse",
        category=ToolCategory.DEFERRED_MEDIUM,
        rationale="Synapse repo pull/push operations",
    ),
    ToolCategoryEntry(
        name="get_synapse",
        category=ToolCategory.DEFERRED_MEDIUM,
        rationale="Retrieve Synapse rules or prompts (content_type=rules|prompts)",
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
        name="think",
        category=ToolCategory.DEFERRED_MEDIUM,
        rationale="Lightweight thinking for quick deliberation moments",
    ),
    ToolCategoryEntry(
        name="cache_json",
        category=ToolCategory.DEFERRED_MEDIUM,
        rationale="Concurrent-safe cache read/write (operation=read|write)",
    ),
    ToolCategoryEntry(
        name="compact_session",
        category=ToolCategory.DEFERRED_MEDIUM,
        rationale="End-of-session compaction and handoff (Phase 56)",
    ),
    ToolCategoryEntry(
        name="skill_pack",
        category=ToolCategory.DEFERRED_MEDIUM,
        rationale="Discover skill packs for task or load pack manifest (operation=discover|load)",
    ),
    ToolCategoryEntry(
        name="quick_start",
        category=ToolCategory.DEFERRED_MEDIUM,
        rationale="Composite: session_start + load_context (agent-skills Step 2)",
    ),
    ToolCategoryEntry(
        name="quality_check",
        category=ToolCategory.DEFERRED_MEDIUM,
        rationale="Composite: pre_commit quality + fix_quality_issues (agent-skills Step 2)",
    ),
    ToolCategoryEntry(
        name="safe_manage_file",
        category=ToolCategory.DEFERRED_MEDIUM,
        rationale="Composite: validate + manage_file + validate (agent-skills Step 2)",
    ),
    ToolCategoryEntry(
        name="suggest_workflow",
        category=ToolCategory.DEFERRED_MEDIUM,
        rationale="Recommend workflow templates for task (agent-skills Step 4)",
    ),
    # ── Deferred low (admin / analytics / rare) ───────────────────────
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
        name="update_synapse",
        category=ToolCategory.DEFERRED_LOW,
        rationale="Modify shared rule or prompt (content_type=rule|prompt, rare admin)",
    ),
    ToolCategoryEntry(
        name="query_usage",
        category=ToolCategory.DEFERRED_LOW,
        rationale="Usage stats, unused tools, report, search, events, timeline (Phase 50)",
    ),
    ToolCategoryEntry(
        name="session_scripts",
        category=ToolCategory.DEFERRED_LOW,
        rationale="Consolidated script capture tools (capture/list/analyze/suggest/promote)",
    ),
    ToolCategoryEntry(
        name="cleanup_metadata_index",
        category=ToolCategory.DEFERRED_LOW,
        rationale="One-time metadata index cleanup (admin)",
    ),
    ToolCategoryEntry(
        name="analyze_error_patterns",
        category=ToolCategory.DEFERRED_LOW,
        rationale="Evaluation error-pattern analysis for optimization debugging",
    ),
)


# ---------------------------------------------------------------------------
# Programmatic tool calling (Phase 49 Step 8)
# ---------------------------------------------------------------------------

# Anthropic code execution caller ID; when present in tool meta, clients may
# allow the tool to be invoked from code execution context.
ALLOWED_CALLERS_CODE_EXECUTION: tuple[str, ...] = ("code_execution_20250825",)

# Tools that support programmatic calling (validation, refactoring, batch file).
# Used in @mcp.tool(meta={"allowed_callers": list(ALLOWED_CALLERS_CODE_EXECUTION)}).
TOOLS_WITH_ALLOWED_CALLERS: tuple[str, ...] = (
    "validate",
    "suggest_refactoring",
    "apply_refactoring",
    "manage_file",
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


# ---------------------------------------------------------------------------
# Tool search (regex over name + rationale)
# ---------------------------------------------------------------------------


class ToolSearchResult(BaseModel):
    """Single deferred tool match for search_tools response."""

    model_config = ConfigDict(frozen=True)

    name: str
    category: ToolCategory
    rationale: str


def _deferred_entries(
    category: ToolCategoryName | None,
) -> list[ToolCategoryEntry]:
    """Return deferred tool entries, optionally filtered by category."""
    deferred = [
        e
        for e in TOOL_CATEGORIES
        if e.category in (ToolCategory.DEFERRED_MEDIUM, ToolCategory.DEFERRED_LOW)
    ]
    if category is not None:
        deferred = [e for e in deferred if e.category == ToolCategory(category)]
    return deferred


def search_deferred_tools(
    query: str,
    *,
    category: ToolCategoryName | None = None,
    limit: int = 20,
) -> list[ToolSearchResult]:
    """Search deferred tools by regex over name and rationale.

    Args:
        query: Search string; compiled as case-insensitive regex.
        category: If set, restrict to this category (deferred_medium or deferred_low).
        limit: Maximum number of results to return (default 20).

    Returns:
        List of matching deferred tools, ordered by category (medium first) then name.
    """
    if not query or not query.strip():
        return []
    try:
        pattern = re.compile(re.escape(query.strip()), re.IGNORECASE)
    except re.error:
        return []
    matches: list[ToolSearchResult] = []
    for entry in _deferred_entries(category):
        if pattern.search(entry.name) or pattern.search(entry.rationale):
            matches.append(
                ToolSearchResult(
                    name=entry.name,
                    category=entry.category,
                    rationale=entry.rationale,
                )
            )
        if len(matches) >= limit:
            break
    return matches[:limit]
