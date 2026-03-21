"""
Context Analysis Operations

This module provides tools to analyze load_context effectiveness
and store statistics for optimization.
"""

from datetime import datetime
from pathlib import Path
from typing import cast

from cortex.core.models import JsonDict, JsonValue, ModelDict
from cortex.core.session_logger import (
    LoadContextLogEntry,
    get_session_id,
    get_session_log_path,
    list_session_logs,
    read_session_log,
)
from cortex.core.synapse_usage_config import is_usage_writable
from cortex.tools.context.effectiveness_models import (
    ContextAnalysisStatus,
    ContextInsights,
    ContextStatisticsResult,
    ContextTelemetryRecordQuality,
    ContextUsageEntry,
    ContextUsageStatistics,
    CurrentSessionAnalysisResult,
    SessionLogsAnalysisResult,
    SessionStats,
)
from cortex.tools.context.effectiveness_operations_insights import (
    extract_task_pattern,
    generate_insights,
)
from cortex.tools.context.effectiveness_operations_io import (
    create_empty_insights,
    get_statistics_path,
    load_statistics,
    save_statistics,
)
from cortex.tools.context.effectiveness_telemetry_quality import (
    classify_persisted_context_usage_entry,
    log_and_classify_context_telemetry_entry,
)


def _production_rollup_entries(
    entries: list[ContextUsageEntry],
) -> list[ContextUsageEntry]:
    return [
        e
        for e in entries
        if e.record_quality == ContextTelemetryRecordQuality.PRODUCTION
    ]


def _reset_optimization_aggregates(stats: ContextUsageStatistics) -> None:
    stats.total_load_context_calls = 0
    stats.avg_token_utilization = 0.0
    stats.avg_files_selected = 0.0
    stats.avg_relevance_score = 0.0
    stats.common_task_patterns = {}
    stats.insights = create_empty_insights()


def _rollup_task_patterns(entries: list[ContextUsageEntry]) -> dict[str, int]:
    patterns: dict[str, int] = {}
    for entry in entries:
        pattern = extract_task_pattern(entry.task_description)
        patterns[pattern] = patterns.get(pattern, 0) + 1
    return patterns


def _relevance_aggregates_from_log_entry(
    entry: LoadContextLogEntry,
) -> tuple[list[float], float, int, int]:
    scores = list(entry.relevance_scores.values())
    if not scores:
        return [], 0.0, 0, 0
    avg = sum(scores) / len(scores)
    hi = sum(1 for s in scores if s > 0.7)
    lo = sum(1 for s in scores if s < 0.3)
    return scores, avg, hi, lo


def _apply_rollup_totals(
    stats: ContextUsageStatistics, rollup: list[ContextUsageEntry]
) -> None:
    total = len(rollup)
    stats.total_load_context_calls = total
    stats.avg_token_utilization = round(sum(e.utilization for e in rollup) / total, 3)
    stats.avg_files_selected = round(sum(e.files_selected for e in rollup) / total, 2)
    stats.avg_relevance_score = round(
        sum(e.avg_relevance_score for e in rollup) / total, 3
    )
    stats.common_task_patterns = _rollup_task_patterns(rollup)
    stats.insights = generate_insights(rollup, create_empty_insights)


def _analyze_log_entry(
    session_id: str, entry: LoadContextLogEntry
) -> ContextUsageEntry:
    """Analyze a single log entry and create usage entry."""
    rq, qnote = log_and_classify_context_telemetry_entry(session_id, entry)
    _, avg_r, hi_r, lo_r = _relevance_aggregates_from_log_entry(entry)
    files = entry.selected_files
    return ContextUsageEntry(
        session_id=session_id,
        timestamp=entry.timestamp,
        task_description=entry.task_description,
        token_budget=entry.token_budget,
        total_tokens=entry.total_tokens,
        utilization=entry.utilization,
        files_selected=len(files),
        files_excluded=len(entry.excluded_files),
        avg_relevance_score=round(avg_r, 3),
        files_with_high_relevance=hi_r,
        files_with_low_relevance=lo_r,
        selected_file_names=files,
        relevance_by_file=entry.relevance_scores,
        role=entry.role,
        record_quality=rq,
        telemetry_quality_note=qnote,
    )


def _update_aggregates(stats: ContextUsageStatistics) -> None:
    """Update aggregate statistics from entries."""
    entries = stats.entries
    if not entries:
        return
    rollup = _production_rollup_entries(entries)
    if not rollup:
        _reset_optimization_aggregates(stats)
        return
    _apply_rollup_totals(stats, rollup)


def reconcile_context_usage_statistics_entries(stats: ContextUsageStatistics) -> bool:
    """Re-classify persisted rows and refresh aggregates when quality labels change."""
    changed = False
    new_entries: list[ContextUsageEntry] = []
    for entry in stats.entries:
        rq, note = classify_persisted_context_usage_entry(entry)
        if rq != entry.record_quality or note != entry.telemetry_quality_note:
            changed = True
            new_entries.append(
                entry.model_copy(
                    update={
                        "record_quality": rq,
                        "telemetry_quality_note": note,
                    },
                )
            )
        else:
            new_entries.append(entry)
    if not changed:
        return False
    stats.entries = new_entries
    _update_aggregates(stats)
    return True


def _calculate_session_stats(
    entries: list[ContextUsageEntry],
) -> SessionStats:
    """Calculate statistics for a list of context usage entries."""
    calls_count = len(entries)
    rollup = _production_rollup_entries(entries)
    if not rollup:
        return SessionStats(
            calls_count=calls_count,
            avg_token_utilization=0.0,
            avg_files_selected=0.0,
            avg_relevance_score=0.0,
            task_patterns={},
        )
    total = len(rollup)
    return SessionStats(
        calls_count=calls_count,
        avg_token_utilization=round(sum(e.utilization for e in rollup) / total, 3),
        avg_files_selected=round(sum(e.files_selected for e in rollup) / total, 2),
        avg_relevance_score=round(
            sum(e.avg_relevance_score for e in rollup) / total, 3
        ),
        task_patterns=_rollup_task_patterns(rollup),
    )


def _update_global_stats(
    project_root: Path, session_id: str, entries: list[ContextUsageEntry]
) -> tuple[ContextUsageStatistics, int]:
    """Update global statistics with new session entries. Returns
    (stats, new_entries_count). When usage_writable is false, skips persist."""
    stats_path = get_statistics_path(project_root)
    stats = load_statistics(stats_path)
    existing_sessions = {e.session_id for e in stats.entries}
    new_entries_added = 0
    if session_id not in existing_sessions:
        stats.entries.extend(entries)
        stats.total_sessions_analyzed += 1
        stats.last_updated = datetime.now().isoformat(timespec="minutes")
        _update_aggregates(stats)
        if is_usage_writable(project_root):
            save_statistics(stats_path, stats)
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
    insights = stats.insights or create_empty_insights()
    return CurrentSessionAnalysisResult(
        status=ContextAnalysisStatus.SUCCESS,
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
            status=ContextAnalysisStatus.NO_DATA,
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
    insights: ContextInsights = stats.insights or create_empty_insights()
    common_task_patterns_json: dict[str, JsonValue] = {
        key: cast(JsonValue, value) for key, value in stats.common_task_patterns.items()
    }
    return SessionLogsAnalysisResult(
        status=ContextAnalysisStatus.SUCCESS,
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
            status=ContextAnalysisStatus.NO_DATA,
            new_sessions_analyzed=None,
            new_entries_added=None,
            total_sessions=None,
            total_entries=None,
            statistics=None,
            insights=None,
            message="No session logs found. Use load_context to generate data.",
        )

    stats_path = get_statistics_path(project_root)
    stats = load_statistics(stats_path)
    existing_sessions = {e.session_id for e in stats.entries}
    new_entries, sessions_analyzed = _process_log_files(log_files, existing_sessions)

    if new_entries:
        stats.entries.extend(new_entries)
        stats.total_sessions_analyzed += sessions_analyzed
        stats.last_updated = datetime.now().isoformat(timespec="minutes")
        _update_aggregates(stats)
        if is_usage_writable(project_root):
            save_statistics(stats_path, stats)

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
    insights = stats.insights or create_empty_insights()
    return ContextStatisticsResult(
        status=ContextAnalysisStatus.SUCCESS,
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
    stats_path = get_statistics_path(project_root)
    if not stats_path.exists():
        return ContextStatisticsResult(
            status=ContextAnalysisStatus.NO_DATA,
            last_updated=None,
            total_sessions=None,
            total_calls=None,
            statistics=None,
            insights=None,
            recent_entries=None,
            message="No statistics found. Run analyze(target='context') first.",
        )

    stats = load_statistics(stats_path)
    common_task_patterns_json: dict[str, JsonValue] = {
        key: cast(JsonValue, value) for key, value in stats.common_task_patterns.items()
    }
    return _build_success_statistics_result(stats, common_task_patterns_json)
