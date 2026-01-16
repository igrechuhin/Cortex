"""
Pattern Normalization - Normalize access log data from JSON.

This module handles normalization of raw JSON data into structured AccessLog format.
"""

from typing import cast

from cortex.analysis.pattern_types import (
    AccessLog,
    AccessRecord,
    FileStatsEntry,
    TaskPatternEntry,
)


def create_default_access_log() -> AccessLog:
    """Create a default empty access log structure.

    Returns:
        Empty AccessLog with default values
    """
    return {
        "version": "1.0",
        "accesses": [],
        "file_stats": {},
        "co_access_patterns": {},
        "task_patterns": {},
    }


def _create_access_record(access_dict: dict[str, object]) -> AccessRecord:
    """Create AccessRecord from dictionary."""
    context_files_raw: object = access_dict.get("context_files")
    context_files_list: list[object] = (
        cast(list[object], context_files_raw)
        if isinstance(context_files_raw, list)
        else []
    )
    return {
        "timestamp": str(access_dict.get("timestamp", "")),
        "file": str(access_dict.get("file", "")),
        "task_id": (
            str(task_id_raw)
            if (task_id_raw := access_dict.get("task_id")) is not None
            else None
        ),
        "task_description": (
            str(desc_raw)
            if (desc_raw := access_dict.get("task_description")) is not None
            else None
        ),
        "context_files": [str(f) for f in context_files_list],
    }


def _normalize_accesses(accesses_raw: object) -> list[AccessRecord]:
    """Normalize raw accesses data into AccessRecord list."""
    if not isinstance(accesses_raw, list):
        return []

    accesses_list: list[object] = cast(list[object], accesses_raw)
    accesses: list[AccessRecord] = []
    for access_item in accesses_list:
        if not isinstance(access_item, dict):
            continue
        access_dict: dict[str, object] = cast(dict[str, object], access_item)
        accesses.append(_create_access_record(access_dict))
    return accesses


def _normalize_file_stats(file_stats_raw: object) -> dict[str, FileStatsEntry]:
    """Normalize raw file stats data into FileStatsEntry dict."""
    file_stats: dict[str, FileStatsEntry] = {}
    if not isinstance(file_stats_raw, dict):
        return file_stats

    file_stats_dict: dict[str, object] = cast(dict[str, object], file_stats_raw)
    for file_path_raw, stats_dict_raw in file_stats_dict.items():
        file_path = str(file_path_raw)
        if isinstance(stats_dict_raw, dict):
            stats_dict: dict[str, object] = cast(dict[str, object], stats_dict_raw)
            tasks_raw: object = stats_dict.get("tasks")
            tasks_list: list[object] = (
                cast(list[object], tasks_raw) if isinstance(tasks_raw, list) else []
            )
            file_stats[file_path] = {
                "total_accesses": (
                    int(total_raw)
                    if isinstance(
                        total_raw := stats_dict.get("total_accesses", 0),
                        (int, float),
                    )
                    else 0
                ),
                "first_access": str(stats_dict.get("first_access", "")),
                "last_access": str(stats_dict.get("last_access", "")),
                "tasks": [str(t) for t in tasks_list if t is not None],
            }
    return file_stats


def _normalize_co_access_patterns(co_access_patterns_raw: object) -> dict[str, int]:
    """Normalize raw co-access patterns data into dict."""
    co_access_patterns: dict[str, int] = {}
    if not isinstance(co_access_patterns_raw, dict):
        return co_access_patterns

    co_access_dict: dict[str, object] = cast(dict[str, object], co_access_patterns_raw)
    for key_item, value_item in co_access_dict.items():
        key_str = str(key_item)
        value = int(value_item) if isinstance(value_item, (int, float)) else 0
        co_access_patterns[key_str] = value
    return co_access_patterns


def _normalize_task_patterns(
    task_patterns_raw: object,
) -> dict[str, TaskPatternEntry]:
    """Normalize raw task patterns data into TaskPatternEntry dict."""
    task_patterns: dict[str, TaskPatternEntry] = {}
    if not isinstance(task_patterns_raw, dict):
        return task_patterns

    task_patterns_dict: dict[str, object] = cast(dict[str, object], task_patterns_raw)
    for task_id_key, pattern_item in task_patterns_dict.items():
        task_id_str = str(task_id_key)
        if isinstance(pattern_item, dict):
            pattern_dict: dict[str, object] = cast(dict[str, object], pattern_item)
            files_raw: object = pattern_dict.get("files")
            files_list: list[object] = (
                cast(list[object], files_raw) if isinstance(files_raw, list) else []
            )
            task_patterns[task_id_str] = {
                "description": (
                    str(desc_raw)
                    if (desc_raw := pattern_dict.get("description")) is not None
                    else None
                ),
                "files": [str(f) for f in files_list],
                "timestamp": str(pattern_dict.get("timestamp", "")),
            }
    return task_patterns


def normalize_access_log(data_raw: object) -> AccessLog:
    """Normalize raw JSON data into AccessLog format.

    Args:
        data_raw: Raw JSON data from file

    Returns:
        Normalized AccessLog structure
    """
    if not isinstance(data_raw, dict):
        return create_default_access_log()

    data: dict[str, object] = cast(dict[str, object], data_raw)

    return {
        "version": str(data.get("version", "1.0")),
        "accesses": _normalize_accesses(data.get("accesses", [])),
        "file_stats": _normalize_file_stats(data.get("file_stats", {})),
        "co_access_patterns": _normalize_co_access_patterns(
            data.get("co_access_patterns", {})
        ),
        "task_patterns": _normalize_task_patterns(data.get("task_patterns", {})),
    }
