"""
Memory Bank Statistics Tool

This module provides the get_memory_bank_stats tool for retrieving
comprehensive Memory Bank statistics and analytics.
"""

import json
from pathlib import Path
from typing import Literal, cast

from cortex.core.metadata_index import MetadataIndex
from cortex.core.models import JsonValue, ModelDict
from cortex.core.version_manager import VersionManager
from cortex.managers import initialization
from cortex.managers.lazy_manager import LazyManager
from cortex.managers.manager_utils import get_manager
from cortex.managers.types import ManagersDict
from cortex.server import mcp


@mcp.tool()
async def get_memory_bank_stats(
    project_root: str | None = None,
    include_token_budget: bool = True,
    include_refactoring_history: bool = False,
    refactoring_days: int = 90,
) -> str:
    """Get overall Memory Bank statistics and analytics.

    Returns comprehensive statistics about token usage, file sizes,
    version history, usage patterns, token budget status, and optionally
    refactoring history. This is the primary tool for monitoring Memory
    Bank health and usage.

    Args:
        project_root: Optional path to project root directory
        include_token_budget: Include token budget analysis (default: True)
            Shows usage percentage, remaining tokens, and status
        include_refactoring_history: Include refactoring history (default: False)
            Shows recent refactorings, rollbacks, and success rates
        refactoring_days: Days of refactoring history to include (default: 90)
            Only used when include_refactoring_history=True

    Returns:
        JSON string with detailed statistics including:
        - summary: Total files, tokens, size, reads, history size
        - token_budget: Usage percentage, remaining tokens, status
        - refactoring_history: Recent refactorings and rollbacks (optional)
        - index_stats: Metadata index statistics

    Example (Basic stats):
        ```json
        {
          "status": "success",
          "project_root": "/path/to/project",
          "summary": {
            "total_files": 7,
            "total_tokens": 45120,
            "total_size_bytes": 180480,
            "total_size_kb": 176.25,
            "total_reads": 142,
            "history_size_bytes": 2048000,
            "history_size_kb": 2000.0
          },
          "token_budget": {
            "status": "healthy",
            "total_tokens": 45120,
            "max_tokens": 100000,
            "remaining_tokens": 54880,
            "usage_percentage": 45.12,
            "warn_threshold": 80.0
          },
          "last_updated": "2026-01-04T10:30:00",
          "index_stats": { ... }
        }
        ```

    Example (With refactoring history):
        When include_refactoring_history=True, adds:
        ```json
        {
          ...
          "refactoring_history": {
            "total_refactorings": 12,
            "successful": 10,
            "rolled_back": 2,
            "recent": [
              {
                "type": "consolidation",
                "timestamp": "2026-01-03T14:00:00",
                "files_affected": ["file1.md", "file2.md"],
                "status": "success"
              }
            ]
          }
        }
        ```

    Note:
        This tool replaces the deprecated check_token_budget and
        get_refactoring_history tools. Use include_token_budget=True and
        include_refactoring_history=True to get all information in one call.

        Token budget status values:
        - "healthy": Usage < warning threshold (default 80%)
        - "warning": Usage >= warning threshold but < max
        - "over_budget": Usage >= max tokens
    """
    try:
        base_result, total_tokens = await _collect_base_stats(project_root)
        result_dict: ModelDict = base_result
        updated = await _add_optional_stats(
            result_dict,
            include_token_budget,
            include_refactoring_history,
            project_root,
            total_tokens,
            refactoring_days,
        )
        return json.dumps(updated if updated is not None else result_dict, indent=2)
    except Exception as e:
        return json.dumps(
            {"status": "error", "error": str(e), "error_type": type(e).__name__},
            indent=2,
        )


async def _collect_base_stats(
    project_root: str | None,
) -> tuple[ModelDict, int]:
    """Collect base statistics for Memory Bank.

    Args:
        project_root: Optional path to project root directory

    Returns:
        Tuple of (result dict, total_tokens)
    """
    root = initialization.get_project_root(project_root)
    mgrs = await initialization.get_managers(root)
    metadata_index = await get_manager(mgrs, "index", MetadataIndex)
    version_manager = await get_manager(mgrs, "versions", VersionManager)

    index_stats = await metadata_index.get_stats()
    files_metadata_raw = await metadata_index.get_all_files_metadata()
    files_metadata = {k: cast(ModelDict, v) for k, v in files_metadata_raw.items()}
    history_size = await _get_history_size(root, version_manager)

    totals = calculate_totals(files_metadata)
    result_dict = _build_base_stats_result(
        root, files_metadata, totals, history_size, cast(ModelDict, index_stats)
    )
    return result_dict, totals[0]


async def _get_history_size(root: Path, version_manager: VersionManager) -> int:
    """Get total disk usage of version history directory."""
    history_dir = root / ".cortex" / "history"
    if not history_dir.exists():
        return 0
    disk_usage = await version_manager.get_disk_usage()
    return disk_usage.total_bytes


def sum_file_field(files_metadata: dict[str, ModelDict], field_name: str) -> int:
    """Sum a numeric field across all files metadata."""
    total = 0
    for file_data in files_metadata.values():
        value = file_data.get(field_name, 0)
        if isinstance(value, int):
            total += value
        elif isinstance(value, float):
            total += int(value)
    return total


def extract_last_updated(index_stats: ModelDict) -> str | None:
    """Extract last_full_scan timestamp from index stats."""
    totals_raw = index_stats.get("totals")
    if not isinstance(totals_raw, dict):
        return None
    last_full_scan = totals_raw.get("last_full_scan")
    return last_full_scan if isinstance(last_full_scan, str) else None


def build_summary_dict(
    files_metadata: dict[str, ModelDict],
    total_tokens: int,
    total_size: int,
    total_reads: int,
    history_size: int,
) -> ModelDict:
    """Build summary model with calculated totals."""
    return {
        "total_files": len(files_metadata),
        "total_tokens": total_tokens,
        "total_size_bytes": total_size,
        "total_size_kb": round(total_size / 1024, 2),
        "total_reads": total_reads,
        "history_size_bytes": history_size,
        "history_size_kb": round(history_size / 1024, 2),
    }


def calculate_token_status(
    total_tokens: int, max_tokens: int, warn_threshold: float
) -> Literal["healthy", "warning", "over_budget"]:
    """Calculate token budget status based on usage."""
    warn_threshold_tokens = int(max_tokens * (warn_threshold / 100))
    if total_tokens >= max_tokens:
        return "over_budget"
    if total_tokens >= warn_threshold_tokens:
        return "warning"
    return "healthy"


async def _build_token_budget_dict(root: Path, total_tokens: int) -> ModelDict:
    """Build token budget analysis dict."""
    from cortex.validation.validation_config import ValidationConfig

    validation_config = ValidationConfig(root)
    max_tokens = validation_config.get_token_budget_max()
    warn_threshold = validation_config.get_token_budget_warn_threshold()

    usage_percentage = (total_tokens / max_tokens * 100) if max_tokens > 0 else 0
    remaining_tokens = max_tokens - total_tokens
    status = calculate_token_status(total_tokens, max_tokens, warn_threshold)

    return {
        "status": status,
        "total_tokens": total_tokens,
        "max_tokens": max_tokens,
        "remaining_tokens": remaining_tokens,
        "usage_percentage": round(usage_percentage, 2),
        "warn_threshold": warn_threshold,
    }


async def _build_refactoring_history_dict(
    mgrs: ManagersDict, refactoring_days: int
) -> ModelDict | None:
    """Build refactoring history dict (best-effort)."""
    executor = mgrs.refactoring_executor
    if executor is None:
        return None

    if isinstance(executor, LazyManager):
        refactoring_executor = await executor.get()
    else:
        refactoring_executor = executor
    history = await refactoring_executor.get_execution_history(
        time_range_days=refactoring_days, include_rollbacks=True
    )
    recent: list[JsonValue] = [
        {
            "type": "execution",
            "timestamp": cast(JsonValue, exec.created_at),
            "files_affected": cast(JsonValue, list[JsonValue]()),
            "status": "success",
        }
        for exec in history.executions
    ]
    return cast(
        ModelDict,
        {
            "total_refactorings": history.total_executions,
            "successful": history.successful,
            "rolled_back": history.rolled_back,
            "recent": recent,
        },
    )


def calculate_totals(
    files_metadata: dict[str, ModelDict],
) -> tuple[int, int, int]:
    """Calculate totals for tokens, size, and reads.

    Args:
        files_metadata: Dictionary of file metadata

    Returns:
        Tuple of (total_tokens, total_size, total_reads)
    """
    total_tokens = sum_file_field(files_metadata, "token_count")
    total_size = sum_file_field(files_metadata, "size_bytes")
    total_reads = sum_file_field(files_metadata, "read_count")
    return total_tokens, total_size, total_reads


def _build_base_stats_result(
    root: Path,
    files_metadata: dict[str, ModelDict],
    totals: tuple[int, int, int],
    history_size: int,
    index_stats: ModelDict,
) -> ModelDict:
    """Build base statistics result model.

    Args:
        root: Project root path
        files_metadata: Dictionary of file metadata
        totals: Tuple of (total_tokens, total_size, total_reads)
        history_size: Size of version history in bytes
        index_stats: Index statistics model

    Returns:
        GetMemoryBankStatsResult with base statistics
    """
    total_tokens, total_size, total_reads = totals
    summary = build_summary_dict(
        files_metadata, total_tokens, total_size, total_reads, history_size
    )
    last_updated = extract_last_updated(index_stats)

    files_payload: dict[str, JsonValue] = {
        file_name: cast(JsonValue, meta) for file_name, meta in files_metadata.items()
    }
    return {
        "status": "success",
        "project_root": str(root),
        "summary": summary,
        "last_updated": last_updated,
        "index_stats": index_stats,
        "files": files_payload,
    }


async def _add_optional_stats(
    result: ModelDict,
    include_token_budget: bool,
    include_refactoring_history: bool,
    project_root: str | None,
    total_tokens: int,
    refactoring_days: int,
) -> ModelDict | None:
    """Add optional statistics to result model.

    Args:
        result: Result model to update
        include_token_budget: Whether to include token budget
        include_refactoring_history: Whether to include refactoring history
        project_root: Optional project root path
        total_tokens: Total token count
        refactoring_days: Days of refactoring history to include

    Returns:
        Updated GetMemoryBankStatsResult with optional stats
    """
    root = initialization.get_project_root(project_root)
    if include_token_budget:
        token_budget = await _build_token_budget_dict(root, total_tokens)
        result["token_budget"] = token_budget

    if include_refactoring_history:
        mgrs = await initialization.get_managers(root)
        refactoring_history = await _build_refactoring_history_dict(
            mgrs, refactoring_days
        )
        if refactoring_history is not None:
            result["refactoring_history"] = refactoring_history

    return result
