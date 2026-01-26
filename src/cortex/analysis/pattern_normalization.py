"""
Pattern Normalization - Normalize access log data from JSON.

This module normalizes raw JSON-compatible data into Pydantic models defined in
`cortex.analysis.pattern_types`.
"""

from typing import cast

from cortex.analysis.pattern_types import (
    AccessLog,
    AccessRecord,
    FileStatsEntry,
    TaskPatternEntry,
)
from cortex.core.models import JsonValue, ModelDict


def create_default_access_log() -> AccessLog:
    """Create a default empty access log structure.

    Returns:
        Empty AccessLog with default values
    """
    return AccessLog(version="1.0")


def _create_access_record(access_dict: ModelDict) -> AccessRecord:
    """Create AccessRecord from a JSON dictionary."""
    context_files_raw: JsonValue = access_dict.get("context_files")
    context_files_list: list[str] = (
        [
            str(file_item)
            for file_item in cast(list[JsonValue], context_files_raw)
            if isinstance(file_item, (str, int, float))
        ]
        if isinstance(context_files_raw, list)
        else []
    )
    task_id_raw = access_dict.get("task_id")
    task_desc_raw = access_dict.get("task_description")
    return AccessRecord(
        timestamp=str(access_dict.get("timestamp", "")),
        file=str(access_dict.get("file", "")),
        task_id=str(task_id_raw) if task_id_raw is not None else None,
        task_description=str(task_desc_raw) if task_desc_raw is not None else None,
        context_files=context_files_list,
    )


def _normalize_accesses(accesses_raw: JsonValue) -> list[AccessRecord]:
    """Normalize raw accesses data into AccessRecord list."""
    if not isinstance(accesses_raw, list):
        return []

    accesses_raw_list = cast(list[JsonValue], accesses_raw)
    accesses_list: list[ModelDict] = [
        cast(ModelDict, item) for item in accesses_raw_list if isinstance(item, dict)
    ]
    accesses: list[AccessRecord] = []
    for access_item in accesses_list:
        accesses.append(_create_access_record(access_item))
    return accesses


def _normalize_file_stats(file_stats_raw: JsonValue) -> dict[str, FileStatsEntry]:
    """Normalize raw file stats data into FileStatsEntry dict."""
    file_stats: dict[str, FileStatsEntry] = {}
    if not isinstance(file_stats_raw, dict):
        return file_stats

    file_stats_dict: ModelDict = cast(ModelDict, file_stats_raw)
    for file_path_raw, stats_dict_raw in file_stats_dict.items():
        file_path = str(file_path_raw)
        if isinstance(stats_dict_raw, dict):
            stats_dict: ModelDict = cast(ModelDict, stats_dict_raw)
            tasks_raw: JsonValue = stats_dict.get("tasks")
            tasks_list: list[str] = (
                [
                    str(task_item)
                    for task_item in cast(list[JsonValue], tasks_raw)
                    if isinstance(task_item, (str, int, float))
                ]
                if isinstance(tasks_raw, list)
                else []
            )
            total_raw = stats_dict.get("total_accesses", 0)
            file_stats[file_path] = FileStatsEntry(
                total_accesses=(
                    int(total_raw) if isinstance(total_raw, (int, float)) else 0
                ),
                first_access=str(stats_dict.get("first_access", "")),
                last_access=str(stats_dict.get("last_access", "")),
                tasks=tasks_list,
            )
    return file_stats


def _normalize_co_access_patterns(co_access_patterns_raw: JsonValue) -> dict[str, int]:
    """Normalize raw co-access patterns data into dict."""
    co_access_patterns: dict[str, int] = {}
    if not isinstance(co_access_patterns_raw, dict):
        return co_access_patterns

    co_access_dict: ModelDict = cast(ModelDict, co_access_patterns_raw)
    for key_item, value_item in co_access_dict.items():
        key_str = str(key_item)
        value = int(value_item) if isinstance(value_item, (int, float)) else 0
        co_access_patterns[key_str] = value
    return co_access_patterns


def _normalize_task_patterns(
    task_patterns_raw: JsonValue,
) -> dict[str, TaskPatternEntry]:
    """Normalize raw task patterns data into TaskPatternEntry dict."""
    task_patterns: dict[str, TaskPatternEntry] = {}
    if not isinstance(task_patterns_raw, dict):
        return task_patterns

    task_patterns_dict: ModelDict = cast(ModelDict, task_patterns_raw)
    for task_id_key, pattern_item in task_patterns_dict.items():
        task_id_str = str(task_id_key)
        if isinstance(pattern_item, dict):
            pattern_dict: ModelDict = cast(ModelDict, pattern_item)
            files_raw: JsonValue = pattern_dict.get("files")
            files_list: list[str] = (
                [
                    str(file_item)
                    for file_item in cast(list[JsonValue], files_raw)
                    if isinstance(file_item, (str, int, float))
                ]
                if isinstance(files_raw, list)
                else []
            )
            desc_raw = pattern_dict.get("description")
            task_patterns[task_id_str] = TaskPatternEntry(
                description=str(desc_raw) if desc_raw is not None else None,
                files=[str(f) for f in files_list],
                timestamp=str(pattern_dict.get("timestamp", "")),
            )
    return task_patterns


def normalize_access_log(data_raw: JsonValue) -> AccessLog:
    """Normalize raw JSON data into AccessLog format.

    Args:
        data_raw: Raw JSON data from file

    Returns:
        Normalized AccessLog structure
    """
    if not isinstance(data_raw, dict):
        return create_default_access_log()

    data: ModelDict = cast(ModelDict, data_raw)

    version_raw = data.get("version", "1.0")
    version = str(version_raw) if version_raw is not None else "1.0"

    return AccessLog(
        version=version,
        accesses=_normalize_accesses(data.get("accesses", [])),
        file_stats=_normalize_file_stats(data.get("file_stats", {})),
        co_access_patterns=_normalize_co_access_patterns(
            data.get("co_access_patterns", {})
        ),
        task_patterns=_normalize_task_patterns(data.get("task_patterns", {})),
    )
