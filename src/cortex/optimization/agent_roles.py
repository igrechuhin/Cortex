"""
Agent role detection and profiles for role-aware context loading.

Phase 58 introduces specialized agent roles (feature, quality, testing,
docs, planning, debugging, review) and lightweight heuristics to infer
the most appropriate role from a task description. These roles are used
by higher-level tools (e.g. load_context) to tailor context loading and
tool selection.

This module focuses on:
- AgentRole enum (string-valued for easy JSON serialization)
- AgentRoleProfile describing role presets (tools/context focus/budget)
- Keyword-based role detection from task_description
- Normalization of user-provided role strings to AgentRole

The actual application of these profiles (e.g. altering token budgets
or file priorities) is handled by callers and can evolve independently
of this module.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum

from cortex.core.constants import MemoryBankFile


class AgentRole(str, Enum):
    """Supported agent roles for multi-agent specialization.

    String values are used so the enum can be serialized directly into
    JSON without additional conversion.
    """

    FEATURE = "feature"  # Implementing new features or enhancements
    QUALITY = "quality"  # Code quality, formatting, linting
    TESTING = "testing"  # Writing/fixing tests, coverage work
    DOCS = "docs"  # Documentation updates
    PLANNING = "planning"  # Creating/updating plans and roadmap work
    DEBUGGING = "debugging"  # Bug investigation and fix/debug flows
    REVIEW = "review"  # Code review and analysis


@dataclass(frozen=True)
class AgentRoleProfile:
    """Static profile describing preferences for an agent role.

    These presets are intentionally lightweight and descriptive; callers
    decide how aggressively to apply them (e.g. adjusting token budgets
    or deferring specific tools).
    """

    # MCP tool names this role is most likely to use.
    priority_tools: tuple[str, ...]
    # MCP tool names that are rarely needed for this role and can be
    # deprioritized in tool search / loading.
    deprioritized_tools: tuple[str, ...]
    # Memory bank files or sections this role most often needs.
    context_focus: tuple[str, ...]
    # Recommended default token budget for this role when the caller
    # has not explicitly chosen a budget.
    default_token_budget: int


def _make_profile(
    priority_tools: Iterable[str],
    deprioritized_tools: Iterable[str],
    context_focus: Iterable[str],
    default_token_budget: int,
) -> AgentRoleProfile:
    """Small helper to build immutable profiles."""

    return AgentRoleProfile(
        priority_tools=tuple(priority_tools),
        deprioritized_tools=tuple(deprioritized_tools),
        context_focus=tuple(context_focus),
        default_token_budget=default_token_budget,
    )


# Default role profiles inspired by the implement/analyze prompts'
# task-type token budget guidance and memory bank file priorities.
ROLE_PROFILES: dict[AgentRole, AgentRoleProfile] = {
    AgentRole.FEATURE: _make_profile(
        priority_tools=[
            "manage_file",
            "load_context",
            "get_relevance_scores",
            "execute_pre_commit_checks",
        ],
        deprioritized_tools=[
            "fix_markdown_lint",
            "fix_quality_issues",
        ],
        context_focus=[
            MemoryBankFile.PROJECT_BRIEF,
            MemoryBankFile.SYSTEM_PATTERNS,
            MemoryBankFile.ACTIVE_CONTEXT,
            MemoryBankFile.TECH_CONTEXT,
        ],
        # Small feature / implementation work typically needs broader
        # context; align with 20k–30k guidance.
        default_token_budget=20000,
    ),
    AgentRole.QUALITY: _make_profile(
        priority_tools=[
            "execute_pre_commit_checks",
            "fix_quality_issues",
            "fix_markdown_lint",
        ],
        deprioritized_tools=[
            "plan",
            "suggest_refactoring",
        ],
        context_focus=[
            MemoryBankFile.TECH_CONTEXT,
            MemoryBankFile.SYSTEM_PATTERNS,
        ],
        # Fix/debug or quality passes tend to use medium budgets.
        default_token_budget=15000,
    ),
    AgentRole.TESTING: _make_profile(
        priority_tools=[
            "execute_pre_commit_checks",
        ],
        deprioritized_tools=[
            "fix_markdown_lint",
        ],
        context_focus=[
            MemoryBankFile.TECH_CONTEXT,
            MemoryBankFile.SYSTEM_PATTERNS,
            MemoryBankFile.PROGRESS,
        ],
        default_token_budget=15000,
    ),
    AgentRole.DOCS: _make_profile(
        priority_tools=[
            "manage_file",
            "fix_markdown_lint",
        ],
        deprioritized_tools=[
            "execute_pre_commit_checks",
            "fix_quality_issues",
        ],
        context_focus=[
            MemoryBankFile.PROJECT_BRIEF,
            MemoryBankFile.PRODUCT_CONTEXT,
            MemoryBankFile.ACTIVE_CONTEXT,
        ],
        # Documentation changes are usually lighter on token usage.
        default_token_budget=10000,
    ),
    AgentRole.PLANNING: _make_profile(
        priority_tools=[
            "plan",
            "register_plan_in_roadmap",
            "manage_file",
        ],
        deprioritized_tools=[
            "fix_quality_issues",
            "execute_pre_commit_checks",
        ],
        context_focus=[
            MemoryBankFile.ROADMAP,
            MemoryBankFile.ACTIVE_CONTEXT,
            MemoryBankFile.PROJECT_BRIEF,
        ],
        default_token_budget=20000,
    ),
    AgentRole.DEBUGGING: _make_profile(
        priority_tools=[
            "load_context",
            "execute_pre_commit_checks",
        ],
        deprioritized_tools=[
            "plan",
        ],
        context_focus=[
            MemoryBankFile.ACTIVE_CONTEXT,
            MemoryBankFile.SYSTEM_PATTERNS,
            MemoryBankFile.TECH_CONTEXT,
        ],
        default_token_budget=15000,
    ),
    AgentRole.REVIEW: _make_profile(
        priority_tools=[
            "load_context",
            "get_relevance_scores",
        ],
        deprioritized_tools=[
            "plan",
            "fix_quality_issues",
        ],
        context_focus=[
            MemoryBankFile.ACTIVE_CONTEXT,
            MemoryBankFile.ROADMAP,
            MemoryBankFile.PROJECT_BRIEF,
        ],
        default_token_budget=15000,
    ),
}


# Keyword heuristics for auto-detecting roles from task_description.
_ROLE_KEYWORDS: dict[AgentRole, tuple[str, ...]] = {
    # Order matters: more specific / diagnostic roles first.
    AgentRole.DEBUGGING: (
        "fix",
        "bug",
        "error",
        "failure",
        "exception",
        "traceback",
        "debug",
    ),
    AgentRole.TESTING: (
        "test",
        "tests",
        "pytest",
        "fixture",
        "coverage",
        "ci failure",
        "flaky",
    ),
    AgentRole.QUALITY: (
        "format",
        "formatter",
        "lint",
        "quality",
        "pre-commit",
        "ruff",
        "black",
        "mypy",
        "type_check",
    ),
    AgentRole.PLANNING: (
        "plan",
        "roadmap",
        "design",
        "phase ",
        "investigate",
        "investigation",
        "session optimization",
    ),
    AgentRole.DOCS: (
        "docs",
        "documentation",
        "readme",
        "guide",
        "tutorial",
        "markdown",
    ),
    AgentRole.REVIEW: (
        "review",
        "code review",
        "pr ",
        "pull request",
    ),
    # FEATURE is the default fallback and intentionally has no keywords.
    AgentRole.FEATURE: (),
}


_ROLE_ALIASES: dict[str, AgentRole] = {
    # Canonical names
    "feature": AgentRole.FEATURE,
    "quality": AgentRole.QUALITY,
    "testing": AgentRole.TESTING,
    "docs": AgentRole.DOCS,
    "planning": AgentRole.PLANNING,
    "debugging": AgentRole.DEBUGGING,
    "review": AgentRole.REVIEW,
    # Common synonyms / shorthands
    "test": AgentRole.TESTING,
    "tests": AgentRole.TESTING,
    "doc": AgentRole.DOCS,
    "documentation": AgentRole.DOCS,
    "plan": AgentRole.PLANNING,
    "design": AgentRole.PLANNING,
    "debug": AgentRole.DEBUGGING,
    "bugfix": AgentRole.DEBUGGING,
    "bug": AgentRole.DEBUGGING,
    "qa": AgentRole.QUALITY,
    "lint": AgentRole.QUALITY,
    "format": AgentRole.QUALITY,
    "code_review": AgentRole.REVIEW,
}


def normalize_role_name(role: str | None) -> AgentRole | None:
    """Normalize a user-provided role string to AgentRole.

    Returns None when the input is empty or cannot be mapped; callers
    should then fall back to auto-detection.
    """

    if not role:
        return None
    key = role.strip().lower().replace("-", "_")
    if key in _ROLE_ALIASES:
        return _ROLE_ALIASES[key]
    # Allow direct enum value usage even if not listed in aliases
    try:
        return AgentRole(key)
    except ValueError:
        return None


def detect_agent_role(task_description: str) -> AgentRole:
    """Detect the most likely agent role from task_description.

    The heuristic applies role-specific keyword lists in a fixed
    priority order so that, for example, debugging beats feature work
    when "fix" or "bug" are present.
    """

    text = task_description.lower()
    for role, keywords in _ROLE_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return role
    return AgentRole.FEATURE


def get_role_profile(role: AgentRole) -> AgentRoleProfile:
    """Return the static profile for the given role.

    Falls back to a conservative default profile if the role is not
    present in ROLE_PROFILES (should not happen in practice).
    """

    profile = ROLE_PROFILES.get(role)
    if profile is not None:
        return profile
    return _make_profile(
        priority_tools=("load_context",),
        deprioritized_tools=(),
        context_focus=(MemoryBankFile.PROJECT_BRIEF,),
        default_token_budget=15000,
    )
