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
# MAX_REGISTERED_TOOLS is enforced by governance tests. Hard cap: to raise it,
# create a plan documenting why the new tool cannot be consolidated into an
# existing one, then bump this constant in the same change as the registration.
MAX_REGISTERED_TOOLS = 10

# Long-term target from consolidation plans (not enforced in tests).
TARGET_REGISTERED_TOOLS = 10


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
    # ── Always loaded tools (core workflow — 8 tools) ─────────────────
    ToolCategoryEntry(
        name="manage_file",
        category=ToolCategory.ALWAYS_LOADED,
        rationale="Core file read/write/metadata used every session",
    ),
    ToolCategoryEntry(
        name="plan",
        category=ToolCategory.ALWAYS_LOADED,
        rationale="Plan lifecycle: create, list, get, complete, register",
    ),
    ToolCategoryEntry(
        name="update_memory_bank",
        category=ToolCategory.ALWAYS_LOADED,
        rationale="Memory bank mutations: roadmap, progress_append, active_context_append",
    ),
    ToolCategoryEntry(
        name="session",
        category=ToolCategory.ALWAYS_LOADED,
        rationale="Session lifecycle: start, register, deregister, compact",
    ),
    ToolCategoryEntry(
        name="run_quality_gate",
        category=ToolCategory.ALWAYS_LOADED,
        rationale="Zero-arg Phase A quality gate",
    ),
    ToolCategoryEntry(
        name="autofix",
        category=ToolCategory.ALWAYS_LOADED,
        rationale="Zero-arg auto-fix for formatting, linting, type, and markdown errors",
    ),
    ToolCategoryEntry(
        name="think",
        category=ToolCategory.ALWAYS_LOADED,
        rationale="Reasoning scratchpad: lightweight or full sequential mode",
    ),
    # ── Deferred medium tools (3 tools) ───────────────────────────────
    ToolCategoryEntry(
        name="run_docs_gate",
        category=ToolCategory.DEFERRED_MEDIUM,
        rationale="Zero-arg Phase B docs/memory-bank validation",
    ),
    ToolCategoryEntry(
        name="pipeline_handoff",
        category=ToolCategory.DEFERRED_MEDIUM,
        rationale="Inter-phase state exchange via session-scoped JSON files",
    ),
    ToolCategoryEntry(
        name="write_artifact",
        category=ToolCategory.DEFERRED_MEDIUM,
        rationale="Allowlisted writes for skill JSON and Synapse rule artifacts",
    ),
)

# Static MCP resources (read-only, not in TOOL_CATEGORIES): see
# cortex.discovery.published_inventory.PUBLISHED_STATIC_RESOURCE_URIS (must match
# @mcp.resource registrations).


# ---------------------------------------------------------------------------
# Programmatic tool calling (Phase 49 Step 8)
# ---------------------------------------------------------------------------

# Anthropic code execution caller ID; when present in tool meta, clients may
# allow the tool to be invoked from code execution context.
ALLOWED_CALLERS_CODE_EXECUTION: tuple[str, ...] = ("code_execution_20250825",)

# Tools that support programmatic calling (validation, refactoring, batch file).
# Used in @mcp.tool(meta={"allowed_callers": list(ALLOWED_CALLERS_CODE_EXECUTION)}).
TOOLS_WITH_ALLOWED_CALLERS: tuple[str, ...] = ("manage_file",)


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


def _match_deferred_entries(
    pattern: re.Pattern[str],
    category: ToolCategoryName | None,
    limit: int,
) -> list[ToolSearchResult]:
    """Return deferred entries matching pattern, up to limit."""
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


def search_deferred_tools(
    query: str,
    *,
    category: ToolCategoryName | None = None,
    limit: int = 20,
) -> list[ToolSearchResult]:
    """Search deferred tools by regex over name and rationale."""
    if not query or not query.strip():
        return []
    try:
        pattern = re.compile(re.escape(query.strip()), re.IGNORECASE)
    except re.error:
        return []
    return _match_deferred_entries(pattern, category, limit)
