"""
Memory Bank Statistics Tool

This module provides the get_memory_bank_stats tool for retrieving
comprehensive Memory Bank statistics and analytics.
"""

import json
from pathlib import Path
from typing import cast

from cortex.core.metadata_index import MetadataIndex
from cortex.core.version_manager import VersionManager
from cortex.managers.initialization import get_managers, get_project_root
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
        result, total_tokens = await _collect_base_stats(project_root)
        await _add_optional_stats(
            result,
            include_token_budget,
            include_refactoring_history,
            project_root,
            total_tokens,
            refactoring_days,
        )
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps(
            {"status": "error", "error": str(e), "error_type": type(e).__name__},
            indent=2,
        )


async def _collect_base_stats(
    project_root: str | None,
) -> tuple[dict[str, object], int]:
    """Collect base statistics for Memory Bank.

    Args:
        project_root: Optional path to project root directory

    Returns:
        Tuple of (base statistics result dictionary, total_tokens)
    """
    root = get_project_root(project_root)
    mgrs = await get_managers(root)
    metadata_index = cast(MetadataIndex, mgrs["index"])
    version_manager = cast(VersionManager, mgrs["versions"])

    index_stats = await metadata_index.get_stats()
    files_metadata = await metadata_index.get_all_files_metadata()
    history_size = await _get_history_size(root, version_manager)

    totals = calculate_totals(files_metadata)
    result = _build_base_stats_result(
        root, files_metadata, totals, history_size, index_stats
    )
    return result, totals[0]


async def _get_history_size(root: Path, version_manager: VersionManager) -> int:
    """Get total disk usage of version history directory."""
    history_dir = root / ".memory-bank-history"
    if not history_dir.exists():
        return 0
    disk_usage = await version_manager.get_disk_usage()
    return disk_usage.get("total_bytes", 0)


def sum_file_field(
    files_metadata: dict[str, dict[str, object]], field_name: str
) -> int:
    """Sum a numeric field across all files metadata."""
    total = 0
    for file_data in files_metadata.values():
        value = file_data.get(field_name, 0)
        if isinstance(value, (int, float)):
            total += int(value)
    return total


def extract_last_updated(index_stats: dict[str, object]) -> str | None:
    """Extract last_full_scan timestamp from index stats."""
    from typing import cast

    totals = index_stats.get("totals")
    if isinstance(totals, dict):
        totals_dict = cast(dict[str, object], totals)
        last_scan = totals_dict.get("last_full_scan")
        if isinstance(last_scan, str):
            return last_scan
    return None


def build_summary_dict(
    files_metadata: dict[str, dict[str, object]],
    total_tokens: int,
    total_size: int,
    total_reads: int,
    history_size: int,
) -> dict[str, object]:
    """Build summary dictionary with calculated totals."""
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
) -> str:
    """Calculate token budget status based on usage."""
    warn_threshold_tokens = int(max_tokens * (warn_threshold / 100))
    if total_tokens >= max_tokens:
        return "over_budget"
    elif total_tokens >= warn_threshold_tokens:
        return "warning"
    else:
        return "healthy"


async def _build_token_budget_dict(root: Path, total_tokens: int) -> dict[str, object]:
    """Build token budget analysis dictionary."""
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
    mgrs: dict[str, object], refactoring_days: int
) -> dict[str, object]:
    """Build refactoring history dictionary."""
    from cortex.refactoring.refactoring_executor import RefactoringExecutor

    refactoring_executor = cast(RefactoringExecutor, mgrs.get("refactoring_executor"))
    if refactoring_executor:
        history = await refactoring_executor.get_execution_history(
            time_range_days=refactoring_days, include_rollbacks=True
        )
        return history
    else:
        return {
            "status": "unavailable",
            "message": "Refactoring executor not initialized",
        }


def calculate_totals(
    files_metadata: dict[str, dict[str, object]],
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
    files_metadata: dict[str, dict[str, object]],
    totals: tuple[int, int, int],
    history_size: int,
    index_stats: dict[str, object],
) -> dict[str, object]:
    """Build base statistics result dictionary.

    Args:
        root: Project root path
        files_metadata: Dictionary of file metadata
        totals: Tuple of (total_tokens, total_size, total_reads)
        history_size: Size of version history in bytes
        index_stats: Index statistics dictionary

    Returns:
        Base statistics result dictionary
    """
    total_tokens, total_size, total_reads = totals
    summary = build_summary_dict(
        files_metadata, total_tokens, total_size, total_reads, history_size
    )
    last_updated = extract_last_updated(index_stats)

    return {
        "status": "success",
        "project_root": str(root),
        "summary": summary,
        "last_updated": last_updated,
        "index_stats": index_stats,
    }


async def _add_optional_stats(
    result: dict[str, object],
    include_token_budget: bool,
    include_refactoring_history: bool,
    project_root: str | None,
    total_tokens: int,
    refactoring_days: int,
) -> None:
    """Add optional statistics to result dictionary.

    Args:
        result: Result dictionary to update
        include_token_budget: Whether to include token budget
        include_refactoring_history: Whether to include refactoring history
        project_root: Optional project root path
        total_tokens: Total token count
        refactoring_days: Days of refactoring history to include
    """
    root = get_project_root(project_root)
    if include_token_budget:
        result["token_budget"] = await _build_token_budget_dict(root, total_tokens)

    if include_refactoring_history:
        mgrs = await get_managers(root)
        result["refactoring_history"] = await _build_refactoring_history_dict(
            mgrs, refactoring_days
        )
