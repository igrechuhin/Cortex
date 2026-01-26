"""
Context Analysis Operations

This module provides tools to analyze load_context effectiveness
and store statistics for optimization.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import cast

from cortex.core.models import JsonDict, JsonValue, ModelDict
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.session_logger import (
    LoadContextLogEntry,
    get_session_id,
    get_session_log_path,
    list_session_logs,
    read_session_log,
)
from cortex.tools.models import (
    ContextInsights,
    ContextStatisticsResult,
    ContextUsageEntry,
    ContextUsageStatistics,
    CurrentSessionAnalysisResult,
    FileEffectiveness,
    SessionLogsAnalysisResult,
    SessionStats,
    TaskTypeInsight,
)


def _get_statistics_path(project_root: Path) -> Path:
    """Get path to context usage statistics file."""
    session_dir = get_cortex_path(project_root, CortexResourceType.SESSION)
    return session_dir / "context-usage-statistics.json"


def _load_statistics(stats_path: Path) -> ContextUsageStatistics:
    """Load existing statistics or create empty structure."""
    if stats_path.exists():
        with open(stats_path, encoding="utf-8") as f:
            data = json.load(f)
            return ContextUsageStatistics.model_validate(data)

    return ContextUsageStatistics(
        last_updated=datetime.now().isoformat(timespec="minutes"),
        total_sessions_analyzed=0,
        total_load_context_calls=0,
        avg_token_utilization=0.0,
        avg_files_selected=0.0,
        avg_relevance_score=0.0,
        common_task_patterns={},
        insights=_create_empty_insights(),
        entries=[],
    )


def _create_empty_insights() -> ContextInsights:
    """Create empty insights structure."""
    return ContextInsights(
        task_type_recommendations={},
        file_effectiveness={},
        learned_patterns=[],
        budget_recommendations={},
    )


def _save_statistics(stats_path: Path, stats: ContextUsageStatistics) -> None:
    """Save statistics to file."""
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats.model_dump(mode="json"), f, indent=2)


def _extract_task_pattern(task_description: str) -> str:
    """Extract a simplified pattern from task description."""
    # Extract key action words
    task_lower = task_description.lower()

    # Order matters: more specific patterns first
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


def _analyze_log_entry(
    session_id: str, entry: LoadContextLogEntry
) -> ContextUsageEntry:
    """Analyze a single log entry and create usage entry."""
    relevance_scores = list(entry.relevance_scores.values())
    avg_score = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0

    # Store file names and relevances for insight generation
    selected_files = entry.selected_files
    relevance_by_file = entry.relevance_scores

    return ContextUsageEntry(
        session_id=session_id,
        timestamp=entry.timestamp,
        task_description=entry.task_description,
        token_budget=entry.token_budget,
        total_tokens=entry.total_tokens,
        utilization=entry.utilization,
        files_selected=len(selected_files),
        files_excluded=len(entry.excluded_files),
        avg_relevance_score=round(avg_score, 3),
        files_with_high_relevance=sum(1 for s in relevance_scores if s > 0.7),
        files_with_low_relevance=sum(1 for s in relevance_scores if s < 0.3),
        selected_file_names=selected_files,
        relevance_by_file=relevance_by_file,
    )


def _generate_task_type_insights(
    entries: list[ContextUsageEntry],
) -> dict[str, TaskTypeInsight]:
    """Generate insights for each task type."""
    task_entries: dict[str, list[ContextUsageEntry]] = {}
    for entry in entries:
        pattern = _extract_task_pattern(entry.task_description)
        if pattern not in task_entries:
            task_entries[pattern] = []
        task_entries[pattern].append(entry)

    insights: dict[str, TaskTypeInsight] = {}
    for task_type, task_list in task_entries.items():
        insights[task_type] = _compute_task_insight(task_type, task_list)
    return insights


def _compute_recommended_budget(avg_tokens: float) -> int:
    """Compute recommended token budget with 20% buffer."""
    recommended = int(avg_tokens * 1.2)
    # Round to nearest 5000
    recommended = ((recommended + 2500) // 5000) * 5000
    return max(recommended, 10000)  # Minimum 10k


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
        essential_files=essential[:5],  # Top 5
        avg_utilization=round(avg_util, 3),
        avg_relevance=round(avg_rel, 3),
        notes=notes,
    )


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


def _generate_file_effectiveness(
    entries: list[ContextUsageEntry],
) -> dict[str, FileEffectiveness]:
    """Generate effectiveness tracking for each file."""
    file_data: dict[str, dict[str, list[float] | set[str]]] = {}

    for entry in entries:
        task_type = _extract_task_pattern(entry.task_description)
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
    return f"Average {int(avg_util * 100)}% budget utilization - ~{waste}k tokens unused per call"


def _get_file_frequency_pattern(entries: list[ContextUsageEntry]) -> str | None:
    """Generate most frequently loaded file pattern."""
    file_counts: dict[str, int] = {}
    for entry in entries:
        selected_files = entry.selected_file_names or []
        for fname in selected_files:
            file_counts[fname] = file_counts.get(fname, 0) + 1
    if not file_counts:
        return None
    top_file = max(file_counts, key=lambda x: file_counts[x])
    return f"'{top_file}' is most frequently loaded ({file_counts[top_file]}/{len(entries)} calls)"


def _get_task_type_pattern(entries: list[ContextUsageEntry]) -> str | None:
    """Generate most common task type pattern."""
    task_counts: dict[str, int] = {}
    for entry in entries:
        pattern = _extract_task_pattern(entry.task_description)
        task_counts[pattern] = task_counts.get(pattern, 0) + 1
    if not task_counts:
        return None
    top_task = max(task_counts, key=lambda x: task_counts[x])
    return f"Most common task type: '{top_task}' ({task_counts[top_task]} calls)"


def _generate_learned_patterns(entries: list[ContextUsageEntry]) -> list[str]:
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

    return patterns


def _generate_budget_recommendations(
    entries: list[ContextUsageEntry],
) -> dict[str, int]:
    """Generate recommended budgets per task type."""
    task_tokens: dict[str, list[int]] = {}
    for entry in entries:
        pattern = _extract_task_pattern(entry.task_description)
        if pattern not in task_tokens:
            task_tokens[pattern] = []
        task_tokens[pattern].append(entry.total_tokens)

    recommendations: dict[str, int] = {}
    for task_type, tokens in task_tokens.items():
        avg = sum(tokens) / len(tokens)
        # Add 20% buffer, round to nearest 5000, minimum 10000
        recommended = int(avg * 1.2)
        recommended = ((recommended + 2500) // 5000) * 5000
        recommendations[task_type] = max(recommended, 10000)

    return recommendations


def _generate_insights(entries: list[ContextUsageEntry]) -> ContextInsights:
    """Generate all actionable insights from entries."""
    if not entries:
        return _create_empty_insights()

    return ContextInsights(
        task_type_recommendations=_generate_task_type_insights(entries),
        file_effectiveness=_generate_file_effectiveness(entries),
        learned_patterns=_generate_learned_patterns(entries),
        budget_recommendations=_generate_budget_recommendations(entries),
    )


def _update_aggregates(stats: ContextUsageStatistics) -> None:
    """Update aggregate statistics from entries."""
    entries = stats.entries
    if not entries:
        return

    total = len(entries)
    stats.total_load_context_calls = total
    stats.avg_token_utilization = round(sum(e.utilization for e in entries) / total, 3)
    stats.avg_files_selected = round(sum(e.files_selected for e in entries) / total, 2)
    stats.avg_relevance_score = round(
        sum(e.avg_relevance_score for e in entries) / total, 3
    )

    # Count task patterns
    patterns: dict[str, int] = {}
    for entry in entries:
        pattern = _extract_task_pattern(entry.task_description)
        patterns[pattern] = patterns.get(pattern, 0) + 1
    stats.common_task_patterns = patterns

    # Generate actionable insights
    stats.insights = _generate_insights(entries)


def _calculate_session_stats(
    entries: list[ContextUsageEntry],
) -> SessionStats:
    """Calculate statistics for a list of context usage entries."""
    total = len(entries)
    patterns: dict[str, int] = {}
    for entry in entries:
        pattern = _extract_task_pattern(entry.task_description)
        patterns[pattern] = patterns.get(pattern, 0) + 1
    return SessionStats(
        calls_count=total,
        avg_token_utilization=round(sum(e.utilization for e in entries) / total, 3),
        avg_files_selected=round(sum(e.files_selected for e in entries) / total, 2),
        avg_relevance_score=round(
            sum(e.avg_relevance_score for e in entries) / total, 3
        ),
        task_patterns=patterns,
    )


def _update_global_stats(
    project_root: Path, session_id: str, entries: list[ContextUsageEntry]
) -> tuple[ContextUsageStatistics, int]:
    """Update global statistics with new session entries. Returns (stats, new_entries_count)."""
    stats_path = _get_statistics_path(project_root)
    stats = _load_statistics(stats_path)
    existing_sessions = {e.session_id for e in stats.entries}
    new_entries_added = 0
    if session_id not in existing_sessions:
        stats.entries.extend(entries)
        stats.total_sessions_analyzed += 1
        stats.last_updated = datetime.now().isoformat(timespec="minutes")
        _update_aggregates(stats)
        _save_statistics(stats_path, stats)
        new_entries_added = len(entries)
    return stats, new_entries_added


def _build_current_session_result(
    session_id: str,
    current_entries: list[ContextUsageEntry],
    session_stats: SessionStats,
    stats: ContextUsageStatistics,
    new_entries_added: int,
) -> CurrentSessionAnalysisResult:
    """Build result model for current session analysis."""
    from cortex.core.models import JsonDict

    insights = stats.insights or _create_empty_insights()
    return CurrentSessionAnalysisResult(
        status="success",
        session_id=session_id,
        current_session=JsonDict.from_dict(
            {
                "calls_analyzed": len(current_entries),
                "statistics": session_stats.model_dump(mode="json"),
                "entries": [e.model_dump(mode="json") for e in current_entries],
            }
        ),
        global_statistics_updated=new_entries_added > 0,
        new_entries_added=new_entries_added,
        total_sessions=stats.total_sessions_analyzed,
        total_entries=len(stats.entries),
        insights=JsonDict.from_dict(insights.model_dump(mode="json")),
        message=None,
    )


def analyze_current_session(project_root: Path) -> CurrentSessionAnalysisResult:
    """Analyze the current session's load_context calls and update statistics."""
    session_id = get_session_id()
    log_path = get_session_log_path(project_root)
    session_log = read_session_log(log_path)
    if session_log is None or not session_log.load_context_calls:
        return CurrentSessionAnalysisResult(
            status="no_data",
            session_id=session_id,
            current_session=None,
            global_statistics_updated=None,
            new_entries_added=None,
            total_sessions=None,
            total_entries=None,
            insights=None,
            message="No load_context calls in current session.",
        )

    current_entries = [
        _analyze_log_entry(session_id, entry)
        for entry in session_log.load_context_calls
    ]
    session_stats = _calculate_session_stats(current_entries)
    stats, new_entries_added = _update_global_stats(
        project_root, session_id, current_entries
    )
    return _build_current_session_result(
        session_id, current_entries, session_stats, stats, new_entries_added
    )


def _process_log_files(
    log_files: list[Path], existing_sessions: set[str]
) -> tuple[list[ContextUsageEntry], int]:
    """Process log files and return (new_entries, sessions_analyzed)."""
    new_entries: list[ContextUsageEntry] = []
    sessions_analyzed = 0
    for log_file in log_files:
        session_log = read_session_log(log_file)
        if session_log is None or session_log.session_id in existing_sessions:
            continue
        sessions_analyzed += 1
        for entry in session_log.load_context_calls:
            new_entries.append(_analyze_log_entry(session_log.session_id, entry))
    return new_entries, sessions_analyzed


def _build_session_logs_result(
    sessions_analyzed: int,
    new_entries: list[ContextUsageEntry],
    stats: ContextUsageStatistics,
) -> SessionLogsAnalysisResult:
    """Build result model for session logs analysis."""
    from cortex.core.models import JsonDict, JsonValue

    insights = stats.insights or _create_empty_insights()
    common_task_patterns_json: dict[str, JsonValue] = {
        key: cast(JsonValue, value) for key, value in stats.common_task_patterns.items()
    }
    return SessionLogsAnalysisResult(
        status="success",
        new_sessions_analyzed=sessions_analyzed,
        new_entries_added=len(new_entries),
        total_sessions=stats.total_sessions_analyzed,
        total_entries=len(stats.entries),
        statistics=JsonDict.from_dict(
            {
                "avg_token_utilization": stats.avg_token_utilization,
                "avg_files_selected": stats.avg_files_selected,
                "avg_relevance_score": stats.avg_relevance_score,
                "common_task_patterns": cast(JsonValue, common_task_patterns_json),
            }
        ),
        insights=JsonDict.from_dict(insights.model_dump(mode="json")),
        message=None,
    )


def analyze_session_logs(project_root: Path) -> SessionLogsAnalysisResult:
    """Analyze all session logs and update statistics."""
    log_files = list_session_logs(project_root)
    if not log_files:
        return SessionLogsAnalysisResult(
            status="no_data",
            new_sessions_analyzed=None,
            new_entries_added=None,
            total_sessions=None,
            total_entries=None,
            statistics=None,
            insights=None,
            message="No session logs found. Use load_context to generate data.",
        )

    stats_path = _get_statistics_path(project_root)
    stats = _load_statistics(stats_path)
    existing_sessions = {e.session_id for e in stats.entries}
    new_entries, sessions_analyzed = _process_log_files(log_files, existing_sessions)

    if new_entries:
        stats.entries.extend(new_entries)
        stats.total_sessions_analyzed += sessions_analyzed
        stats.last_updated = datetime.now().isoformat(timespec="minutes")
        _update_aggregates(stats)
        _save_statistics(stats_path, stats)

    return _build_session_logs_result(sessions_analyzed, new_entries, stats)


def _build_statistics_dict(
    stats: ContextUsageStatistics, common_task_patterns_json: dict[str, JsonValue]
) -> ModelDict:
    """Build statistics dictionary."""
    return {
        "avg_token_utilization": stats.avg_token_utilization,
        "avg_files_selected": stats.avg_files_selected,
        "avg_relevance_score": stats.avg_relevance_score,
        "common_task_patterns": cast(JsonValue, common_task_patterns_json),
    }


def _build_success_statistics_result(
    stats: ContextUsageStatistics, common_task_patterns_json: dict[str, JsonValue]
) -> ContextStatisticsResult:
    """Build success statistics result."""
    insights = stats.insights or _create_empty_insights()
    return ContextStatisticsResult(
        status="success",
        last_updated=stats.last_updated,
        total_sessions=stats.total_sessions_analyzed,
        total_calls=stats.total_load_context_calls,
        statistics=JsonDict.from_dict(
            _build_statistics_dict(stats, common_task_patterns_json)
        ),
        insights=JsonDict.from_dict(insights.model_dump(mode="json")),
        recent_entries=[
            JsonDict.from_dict(e.model_dump(mode="json")) for e in stats.entries[-10:]
        ],
        message=None,
    )


def get_context_statistics(project_root: Path) -> ContextStatisticsResult:
    """Get current context usage statistics.

    Args:
        project_root: Project root directory

    Returns:
        Current statistics or empty structure if none exist
    """
    stats_path = _get_statistics_path(project_root)
    if not stats_path.exists():
        return ContextStatisticsResult(
            status="no_data",
            last_updated=None,
            total_sessions=None,
            total_calls=None,
            statistics=None,
            insights=None,
            recent_entries=None,
            message="No statistics found. Run analyze_context_effectiveness first.",
        )

    stats = _load_statistics(stats_path)
    common_task_patterns_json: dict[str, JsonValue] = {
        key: cast(JsonValue, value) for key, value in stats.common_task_patterns.items()
    }
    return _build_success_statistics_result(stats, common_task_patterns_json)
