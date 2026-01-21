"""
Context Analysis Operations

This module provides tools to analyze load_context effectiveness
and store statistics for optimization.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import TypedDict

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.session_logger import (
    LoadContextLogEntry,
    get_session_id,
    get_session_log_path,
    list_session_logs,
    read_session_log,
)


class ContextUsageEntry(TypedDict):
    """Structure for a single context usage analysis entry."""

    session_id: str
    timestamp: str
    task_description: str
    token_budget: int
    total_tokens: int
    utilization: float
    files_selected: int
    files_excluded: int
    avg_relevance_score: float
    files_with_high_relevance: int  # score > 0.7
    files_with_low_relevance: int  # score < 0.3


class ContextUsageStatistics(TypedDict):
    """Structure for aggregated context usage statistics."""

    last_updated: str
    total_sessions_analyzed: int
    total_load_context_calls: int
    avg_token_utilization: float
    avg_files_selected: float
    avg_relevance_score: float
    common_task_patterns: dict[str, int]
    entries: list[ContextUsageEntry]


def _get_statistics_path(project_root: Path) -> Path:
    """Get path to context usage statistics file."""
    session_dir = get_cortex_path(project_root, CortexResourceType.SESSION)
    return session_dir / "context-usage-statistics.json"


def _load_statistics(stats_path: Path) -> ContextUsageStatistics:
    """Load existing statistics or create empty structure."""
    if stats_path.exists():
        with open(stats_path, encoding="utf-8") as f:
            return json.load(f)

    return {
        "last_updated": datetime.now().isoformat(timespec="minutes"),
        "total_sessions_analyzed": 0,
        "total_load_context_calls": 0,
        "avg_token_utilization": 0.0,
        "avg_files_selected": 0.0,
        "avg_relevance_score": 0.0,
        "common_task_patterns": {},
        "entries": [],
    }


def _save_statistics(stats_path: Path, stats: ContextUsageStatistics) -> None:
    """Save statistics to file."""
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)


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
    relevance_scores = list(entry["relevance_scores"].values())
    avg_score = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0

    return {
        "session_id": session_id,
        "timestamp": entry["timestamp"],
        "task_description": entry["task_description"],
        "token_budget": entry["token_budget"],
        "total_tokens": entry["total_tokens"],
        "utilization": entry["utilization"],
        "files_selected": len(entry["selected_files"]),
        "files_excluded": len(entry["excluded_files"]),
        "avg_relevance_score": round(avg_score, 3),
        "files_with_high_relevance": sum(1 for s in relevance_scores if s > 0.7),
        "files_with_low_relevance": sum(1 for s in relevance_scores if s < 0.3),
    }


def _update_aggregates(stats: ContextUsageStatistics) -> None:
    """Update aggregate statistics from entries."""
    entries = stats["entries"]
    if not entries:
        return

    total = len(entries)
    stats["total_load_context_calls"] = total
    stats["avg_token_utilization"] = round(
        sum(e["utilization"] for e in entries) / total, 3
    )
    stats["avg_files_selected"] = round(
        sum(e["files_selected"] for e in entries) / total, 2
    )
    stats["avg_relevance_score"] = round(
        sum(e["avg_relevance_score"] for e in entries) / total, 3
    )

    # Count task patterns
    patterns: dict[str, int] = {}
    for entry in entries:
        pattern = _extract_task_pattern(entry["task_description"])
        patterns[pattern] = patterns.get(pattern, 0) + 1
    stats["common_task_patterns"] = patterns


def _calculate_session_stats(
    entries: list[ContextUsageEntry],
) -> dict[str, int | float | dict[str, int]]:
    """Calculate statistics for a list of context usage entries."""
    total = len(entries)
    patterns: dict[str, int] = {}
    for entry in entries:
        pattern = _extract_task_pattern(entry["task_description"])
        patterns[pattern] = patterns.get(pattern, 0) + 1
    return {
        "calls_count": total,
        "avg_token_utilization": round(
            sum(e["utilization"] for e in entries) / total, 3
        ),
        "avg_files_selected": round(
            sum(e["files_selected"] for e in entries) / total, 2
        ),
        "avg_relevance_score": round(
            sum(e["avg_relevance_score"] for e in entries) / total, 3
        ),
        "task_patterns": patterns,
    }


def _update_global_stats(
    project_root: Path, session_id: str, entries: list[ContextUsageEntry]
) -> tuple[ContextUsageStatistics, int]:
    """Update global statistics with new session entries. Returns (stats, new_entries_count)."""
    stats_path = _get_statistics_path(project_root)
    stats = _load_statistics(stats_path)
    existing_sessions = {e["session_id"] for e in stats["entries"]}
    new_entries_added = 0
    if session_id not in existing_sessions:
        stats["entries"].extend(entries)
        stats["total_sessions_analyzed"] += 1
        stats["last_updated"] = datetime.now().isoformat(timespec="minutes")
        _update_aggregates(stats)
        _save_statistics(stats_path, stats)
        new_entries_added = len(entries)
    return stats, new_entries_added


def analyze_current_session(project_root: Path) -> dict[str, object]:
    """Analyze the current session's load_context calls and update statistics.

    Args:
        project_root: Project root directory

    Returns:
        Analysis result with current session details and statistics update
    """
    session_id = get_session_id()
    log_path = get_session_log_path(project_root)
    session_log = read_session_log(log_path)
    if session_log is None or not session_log["load_context_calls"]:
        return {
            "status": "no_data",
            "session_id": session_id,
            "message": "No load_context calls in current session.",
        }

    current_entries = [
        _analyze_log_entry(session_id, entry)
        for entry in session_log["load_context_calls"]
    ]
    session_stats = _calculate_session_stats(current_entries)
    stats, new_entries_added = _update_global_stats(
        project_root, session_id, current_entries
    )

    return {
        "status": "success",
        "session_id": session_id,
        "current_session": {
            "calls_analyzed": len(current_entries),
            "statistics": session_stats,
            "entries": current_entries,
        },
        "global_statistics_updated": new_entries_added > 0,
        "new_entries_added": new_entries_added,
        "total_sessions": stats["total_sessions_analyzed"],
        "total_entries": len(stats["entries"]),
    }


def _process_log_files(
    log_files: list[Path], existing_sessions: set[str]
) -> tuple[list[ContextUsageEntry], int]:
    """Process log files and return (new_entries, sessions_analyzed)."""
    new_entries: list[ContextUsageEntry] = []
    sessions_analyzed = 0
    for log_file in log_files:
        session_log = read_session_log(log_file)
        if session_log is None or session_log["session_id"] in existing_sessions:
            continue
        sessions_analyzed += 1
        for entry in session_log["load_context_calls"]:
            new_entries.append(_analyze_log_entry(session_log["session_id"], entry))
    return new_entries, sessions_analyzed


def analyze_session_logs(project_root: Path) -> dict[str, object]:
    """Analyze all session logs and update statistics.

    Args:
        project_root: Project root directory

    Returns:
        Analysis result with statistics summary
    """
    log_files = list_session_logs(project_root)
    if not log_files:
        return {
            "status": "no_data",
            "message": "No session logs found. Use load_context to generate data.",
        }

    stats_path = _get_statistics_path(project_root)
    stats = _load_statistics(stats_path)
    existing_sessions = {e["session_id"] for e in stats["entries"]}
    new_entries, sessions_analyzed = _process_log_files(log_files, existing_sessions)

    if new_entries:
        stats["entries"].extend(new_entries)
        stats["total_sessions_analyzed"] += sessions_analyzed
        stats["last_updated"] = datetime.now().isoformat(timespec="minutes")
        _update_aggregates(stats)
        _save_statistics(stats_path, stats)

    return {
        "status": "success",
        "new_sessions_analyzed": sessions_analyzed,
        "new_entries_added": len(new_entries),
        "total_sessions": stats["total_sessions_analyzed"],
        "total_entries": len(stats["entries"]),
        "statistics": {
            "avg_token_utilization": stats["avg_token_utilization"],
            "avg_files_selected": stats["avg_files_selected"],
            "avg_relevance_score": stats["avg_relevance_score"],
            "common_task_patterns": stats["common_task_patterns"],
        },
    }


def get_context_statistics(project_root: Path) -> dict[str, object]:
    """Get current context usage statistics.

    Args:
        project_root: Project root directory

    Returns:
        Current statistics or empty structure if none exist
    """
    stats_path = _get_statistics_path(project_root)
    if not stats_path.exists():
        return {
            "status": "no_data",
            "message": "No statistics found. Run analyze_context_effectiveness first.",
        }

    stats = _load_statistics(stats_path)
    return {
        "status": "success",
        "last_updated": stats["last_updated"],
        "total_sessions": stats["total_sessions_analyzed"],
        "total_calls": stats["total_load_context_calls"],
        "statistics": {
            "avg_token_utilization": stats["avg_token_utilization"],
            "avg_files_selected": stats["avg_files_selected"],
            "avg_relevance_score": stats["avg_relevance_score"],
            "common_task_patterns": stats["common_task_patterns"],
        },
        "recent_entries": stats["entries"][-10:],  # Last 10 entries
    }
