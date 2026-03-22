"""
Context Analysis Operations - Insights Generation

Insight generation from context usage entries.
"""

from collections.abc import Callable
from typing import cast

from cortex.core.models import JsonValue, ModelDict
from cortex.tools.context.effectiveness_models import (
    ContextInsights,
    ContextUsageEntry,
    ContextUsageStatistics,
    FileEffectiveness,
    TaskTypeInsight,
)


def is_non_trivial_task(task_description: str) -> bool:
    """Check if task description indicates a non-trivial task requiring context.

    Non-trivial tasks are those that require project context to complete correctly:
    - refactor, fix, debug, implement, add, create tasks
    - These tasks MUST use non-zero token budgets for proper context loading.

    Args:
        task_description: Task description to check

    Returns:
        True if task is non-trivial and requires context
    """
    task_lower = task_description.lower()
    non_trivial_keywords = [
        "refactor",
        "fix",
        "bug",
        "debug",
        "implement",
        "add",
        "create",
        "testing",
        "test ",
    ]
    return any(keyword in task_lower for keyword in non_trivial_keywords)


def extract_task_pattern(task_description: str) -> str:
    """Extract a simplified pattern from task description."""
    task_lower = task_description.lower()
    patterns = [
        ("security", "security"),
        ("document", "documentation"),
        ("optimize", "optimization"),
        ("review", "review"),
        ("test", "testing"),
        ("refactor", "refactor"),
        ("fix", "fix/debug"),
        ("bug", "fix/debug"),
        ("debug", "fix/debug"),
        ("implement", "implement/add"),
        ("add", "implement/add"),
        ("create", "implement/add"),
        ("update", "update/modify"),
        ("modify", "update/modify"),
        ("change", "update/modify"),
    ]
    for keyword, pattern in patterns:
        if keyword in task_lower:
            return pattern
    return "other"


def build_statistics_dict(
    stats: ContextUsageStatistics, common_task_patterns_json: dict[str, JsonValue]
) -> ModelDict:
    """Build statistics dictionary for context statistics MCP responses."""
    return {
        "avg_token_utilization": stats.avg_token_utilization,
        "avg_files_selected": stats.avg_files_selected,
        "avg_relevance_score": stats.avg_relevance_score,
        "common_task_patterns": cast(JsonValue, common_task_patterns_json),
    }


def _compute_recommended_budget(avg_tokens: float) -> int:
    """Compute recommended token budget with 20% buffer."""
    recommended = int(avg_tokens * 1.2)
    recommended = ((recommended + 2500) // 5000) * 5000
    return max(recommended, 10000)


def _find_essential_files(entries: list[ContextUsageEntry]) -> list[str]:
    """Find files that appear in >50% of entries with high relevance."""
    file_counts: dict[str, int] = {}
    file_relevances: dict[str, list[float]] = {}
    for entry in entries:
        selected_files = entry.selected_file_names or []
        relevance_by_file = entry.relevance_by_file or {}
        for fname in selected_files:
            file_counts[fname] = file_counts.get(fname, 0) + 1
            if fname not in file_relevances:
                file_relevances[fname] = []
            rel = relevance_by_file.get(fname, 0.5)
            file_relevances[fname].append(rel)

    essential: list[str] = []
    threshold = len(entries) * 0.5
    for fname, count in file_counts.items():
        if count >= threshold:
            avg_file_rel = sum(file_relevances[fname]) / len(file_relevances[fname])
            if avg_file_rel > 0.5:
                essential.append(fname)
    return essential


def _generate_task_notes(avg_util: float, avg_rel: float, count: int) -> str:
    """Generate human-readable notes for a task type."""
    notes: list[str] = []
    if avg_util < 0.3:
        notes.append("Low utilization - consider smaller token budgets")
    elif avg_util < 0.5:
        notes.append("Moderate utilization - some budget optimization possible")
    elif avg_util > 0.8:
        notes.append("High utilization - budget well-matched to needs")
    if avg_rel > 0.7:
        notes.append("High relevance - file selection is effective")
    elif avg_rel < 0.5:
        notes.append("Low relevance - consider refining file selection")
    if count < 3:
        notes.append("Limited data - insights will improve with more samples")
    return "; ".join(notes) if notes else "Adequate performance"


def _compute_task_insight(
    task_type: str, entries: list[ContextUsageEntry]
) -> TaskTypeInsight:
    """Compute insight for a specific task type."""
    avg_util = sum(e.utilization for e in entries) / len(entries)
    avg_rel = sum(e.avg_relevance_score for e in entries) / len(entries)
    avg_tokens = sum(e.total_tokens for e in entries) / len(entries)
    recommended = _compute_recommended_budget(avg_tokens)
    essential = _find_essential_files(entries)
    notes = _generate_task_notes(avg_util, avg_rel, len(entries))
    return TaskTypeInsight(
        calls_count=len(entries),
        recommended_budget=recommended,
        essential_files=essential[:5],
        avg_utilization=round(avg_util, 3),
        avg_relevance=round(avg_rel, 3),
        notes=notes,
    )


def generate_task_type_insights(
    entries: list[ContextUsageEntry],
) -> dict[str, TaskTypeInsight]:
    """Generate insights for each task type."""
    task_entries: dict[str, list[ContextUsageEntry]] = {}
    for entry in entries:
        pattern = extract_task_pattern(entry.task_description)
        if pattern not in task_entries:
            task_entries[pattern] = []
        task_entries[pattern].append(entry)
    insights: dict[str, TaskTypeInsight] = {}
    for task_type, task_list in task_entries.items():
        insights[task_type] = _compute_task_insight(task_type, task_list)
    return insights


def generate_role_insights(
    entries: list[ContextUsageEntry],
) -> dict[str, TaskTypeInsight]:
    """Generate insights for each agent role."""
    role_entries: dict[str, list[ContextUsageEntry]] = {}
    for entry in entries:
        if entry.role:
            if entry.role not in role_entries:
                role_entries[entry.role] = []
            role_entries[entry.role].append(entry)
    insights: dict[str, TaskTypeInsight] = {}
    for role, role_list in role_entries.items():
        insights[role] = _compute_task_insight(role, role_list)
    return insights


def _compute_file_effectiveness(
    fname: str, relevances: list[float], task_types: list[str]
) -> FileEffectiveness:
    """Compute effectiveness for a single file."""
    avg_rel = sum(relevances) / len(relevances) if relevances else 0
    if avg_rel > 0.7:
        rec = "High value - prioritize for loading"
    elif avg_rel > 0.5:
        rec = "Moderate value - include when relevant"
    else:
        rec = "Lower relevance - consider excluding for most tasks"
    return FileEffectiveness(
        times_selected=len(relevances),
        avg_relevance=round(avg_rel, 3),
        task_types_used=task_types,
        recommendation=rec,
    )


def generate_file_effectiveness(
    entries: list[ContextUsageEntry],
) -> dict[str, FileEffectiveness]:
    """Generate effectiveness tracking for each file."""
    file_data: dict[str, dict[str, list[float] | set[str]]] = {}
    for entry in entries:
        task_type = extract_task_pattern(entry.task_description)
        selected_files = entry.selected_file_names or []
        relevance_by_file = entry.relevance_by_file or {}
        for fname in selected_files:
            if fname not in file_data:
                file_data[fname] = {"relevances": [], "task_types": set()}
            rel = relevance_by_file.get(fname, 0.5)
            relevances = file_data[fname]["relevances"]
            if isinstance(relevances, list):
                relevances.append(rel)
            task_types = file_data[fname]["task_types"]
            if isinstance(task_types, set):
                task_types.add(task_type)

    effectiveness: dict[str, FileEffectiveness] = {}
    for fname, data in file_data.items():
        relevances = data["relevances"]
        task_types = data["task_types"]
        if isinstance(relevances, list) and isinstance(task_types, set):
            effectiveness[fname] = _compute_file_effectiveness(
                fname, relevances, list(task_types)
            )
    return effectiveness


def _get_budget_efficiency_pattern(
    entries: list[ContextUsageEntry],
    avg_util: float,
    avg_budget: float,
    avg_tokens: float,
) -> str | None:
    """Generate budget efficiency pattern message if utilization is low."""
    if avg_util >= 0.5:
        return None
    waste = int((avg_budget - avg_tokens) / 1000)
    return (
        f"Average {int(avg_util * 100)}% budget utilization - "
        f"~{waste}k tokens unused per call"
    )


def _get_file_frequency_pattern(entries: list[ContextUsageEntry]) -> str | None:
    """Generate most frequently loaded file pattern."""
    file_counts: dict[str, int] = {}
    for entry in entries:
        for fname in entry.selected_file_names or []:
            file_counts[fname] = file_counts.get(fname, 0) + 1
    if not file_counts:
        return None
    top_file = max(file_counts, key=lambda x: file_counts[x])
    return (
        f"'{top_file}' is most frequently loaded "
        f"({file_counts[top_file]}/{len(entries)} calls)"
    )


def _get_task_type_pattern(entries: list[ContextUsageEntry]) -> str | None:
    """Generate most common task type pattern."""
    task_counts: dict[str, int] = {}
    for entry in entries:
        pattern = extract_task_pattern(entry.task_description)
        task_counts[pattern] = task_counts.get(pattern, 0) + 1
    if not task_counts:
        return None
    top_task = max(task_counts, key=lambda x: task_counts[x])
    return f"Most common task type: '{top_task}' ({task_counts[top_task]} calls)"


def _get_zero_budget_warning(entries: list[ContextUsageEntry]) -> str | None:
    """Generate warning for zero-budget/zero-files load_context calls."""
    non_trivial_tasks = [
        e
        for e in entries
        if (e.token_budget == 0 or e.files_selected == 0)
        and is_non_trivial_task(e.task_description)
    ]
    if non_trivial_tasks:
        return (
            "⚠️ CRITICAL: At least one load_context call had token_budget=0 "
            "or files_selected=0 for a non-trivial task (refactor/fix/debug/implement/testing). "
            "This is a configuration error - these tasks MUST use a non-zero token budget "
            "(typically 10k-15k for fix/debug, 20k-30k for implement/add). "
            "Re-run load_context with an appropriate budget to ensure proper context loading. "
            "Zero-budget/zero-files calls for non-trivial tasks indicate the agent ran without "
            "memory-bank guidance, which violates the documented workflow."
        )
    zero_budget = any(e.token_budget == 0 for e in entries)
    zero_files = any(e.files_selected == 0 for e in entries)
    if zero_budget or zero_files:
        return (
            "Warning: at least one load_context call had token_budget=0 or "
            "no selected files. For non-trivial tasks (refactor/fix/debug/implement/testing), "
            "this is a configuration error - use a non-zero token budget "
            "(typically 10k-15k for fix/debug, 20k-30k for implement/add)."
        )
    return None


def generate_learned_patterns(entries: list[ContextUsageEntry]) -> list[str]:
    """Generate human-readable learned patterns from data."""
    if not entries:
        return []
    patterns: list[str] = []
    avg_util = sum(e.utilization for e in entries) / len(entries)
    avg_budget = sum(e.token_budget for e in entries) / len(entries)
    avg_tokens = sum(e.total_tokens for e in entries) / len(entries)

    budget_pattern = _get_budget_efficiency_pattern(
        entries, avg_util, avg_budget, avg_tokens
    )
    if budget_pattern:
        patterns.append(budget_pattern)
    file_pattern = _get_file_frequency_pattern(entries)
    if file_pattern:
        patterns.append(file_pattern)
    task_pattern = _get_task_type_pattern(entries)
    if task_pattern:
        patterns.append(task_pattern)
    zero_budget_warning = _get_zero_budget_warning(entries)
    if zero_budget_warning:
        patterns.append(zero_budget_warning)
    return patterns


def generate_budget_recommendations(
    entries: list[ContextUsageEntry],
) -> dict[str, int]:
    """Generate recommended budgets per task type."""
    task_tokens: dict[str, list[int]] = {}
    for entry in entries:
        pattern = extract_task_pattern(entry.task_description)
        if pattern not in task_tokens:
            task_tokens[pattern] = []
        task_tokens[pattern].append(entry.total_tokens)
    recommendations: dict[str, int] = {}
    for task_type, tokens in task_tokens.items():
        avg = sum(tokens) / len(tokens)
        recommended = int(avg * 1.2)
        recommended = ((recommended + 2500) // 5000) * 5000
        recommendations[task_type] = max(recommended, 10000)
    return recommendations


def generate_role_budget_recommendations(
    entries: list[ContextUsageEntry],
) -> dict[str, int]:
    """Generate budget recommendations by agent role."""
    role_tokens: dict[str, list[int]] = {}
    for entry in entries:
        if entry.role:
            if entry.role not in role_tokens:
                role_tokens[entry.role] = []
            role_tokens[entry.role].append(entry.total_tokens)
    recommendations: dict[str, int] = {}
    for role, tokens in role_tokens.items():
        avg = sum(tokens) / len(tokens)
        recommended = int(avg * 1.2)
        recommended = ((recommended + 2500) // 5000) * 5000
        recommendations[role] = max(recommended, 10000)
    return recommendations


def generate_insights(
    entries: list[ContextUsageEntry],
    create_empty: Callable[[], ContextInsights],
) -> ContextInsights:
    """Generate all actionable insights from entries."""
    if not entries:
        return create_empty()
    return ContextInsights(
        task_type_recommendations=generate_task_type_insights(entries),
        file_effectiveness=generate_file_effectiveness(entries),
        learned_patterns=generate_learned_patterns(entries),
        budget_recommendations=generate_budget_recommendations(entries),
        role_recommendations=generate_role_insights(entries),
        role_budget_recommendations=generate_role_budget_recommendations(entries),
    )
