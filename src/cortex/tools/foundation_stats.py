"""
Memory Bank Statistics Tool

This module provides the get_memory_bank_stats tool for retrieving
comprehensive Memory Bank statistics and analytics.
"""

import json
from pathlib import Path
from typing import cast

from cortex.core.constants import MCP_TOOL_TIMEOUT_MEDIUM
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_stability import (
    ensure_usage_context,
    mcp_resource_wrapper,
    mcp_tool_wrapper,
)
from cortex.core.metadata_index import MetadataIndex
from cortex.core.models import JsonValue, ModelDict, ResponseFormat
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.project_root_resolver import resolve_project_root_async
from cortex.core.version_manager import VersionManager
from cortex.managers import initialization
from cortex.managers.lazy_manager import LazyManager
from cortex.managers.types import ManagersDict
from cortex.managers.utils import get_manager
from cortex.server import mcp
from cortex.tools.foundation_stats_helpers import (
    build_base_stats_result,
    build_summary_dict,
    calculate_token_status,
    calculate_totals,
    extract_last_updated,
    format_memory_bank_stats_response,
    sum_file_field,
)

# Re-exports for tests
__all__ = [
    "build_summary_dict",
    "calculate_token_status",
    "calculate_totals",
    "extract_last_updated",
    "format_memory_bank_stats_response",
    "get_memory_bank_stats",
    "sum_file_field",
]


# Tool consolidated into query_memory_bank (Phase 50); kept as callable for dispatch.
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def get_memory_bank_stats(
    include_token_budget: bool = True,
    include_refactoring_history: bool = False,
    refactoring_days: int = 90,
    response_format: ResponseFormat = ResponseFormat.CONCISE,
    ctx: MCPContext | None = None,
) -> str:
    """Get overall Memory Bank statistics and analytics.

    USE WHEN: User asks about project status, user needs memory bank
    statistics, user wants to check file counts or token usage, user requests
    system overview.

    EXAMPLES: 'get memory bank stats', 'show project statistics', 'how many
    files in memory bank', 'what is the token usage'.

    RETURNS: JSON with file counts, token usage, version history stats, and
    system health metrics.

    Returns comprehensive statistics about token usage, file sizes,
    version history, usage patterns, token budget status, and optionally
    refactoring history. This is the primary tool for monitoring Memory
    Bank health and usage.

    Args:
        include_token_budget: Include token budget analysis (default: True)
            Shows usage percentage, remaining tokens, and status
        include_refactoring_history: Include refactoring history (default: False)
            Shows recent refactorings, rollbacks, and success rates
        refactoring_days: Days of refactoring history to include (default: 90)
            Only used when include_refactoring_history=True
        response_format: "concise" or "full" (default: concise)
            Controls verbosity of the response

    Returns:
        JSON string with detailed statistics including:
        - summary: Total files, tokens, size, reads, history size
        - token_budget: Usage percentage, remaining tokens, status
        - refactoring_history: Recent refactorings and rollbacks (optional)
        - index_stats: Metadata index statistics
    """
    await log_client(
        ctx, "info", "get_memory_bank_stats: starting", logger_name=__name__
    )
    try:
        root = await resolve_project_root_async(None, ctx)
        result_dict = await _get_memory_bank_stats_impl(
            ctx,
            root,
            include_token_budget,
            include_refactoring_history,
            refactoring_days,
        )
        return format_memory_bank_stats_response(result_dict, response_format)
    except Exception as e:
        await log_client(
            ctx,
            "error",
            f"get_memory_bank_stats: failed: {e}",
            logger_name=__name__,
        )
        return json.dumps(
            {"status": "error", "error": str(e), "error_type": type(e).__name__},
            indent=2,
        )


@mcp.resource(uri="cortex://memory-bank/stats")
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def get_memory_bank_stats_resource() -> str:
    """Resource: Memory Bank statistics (default params)."""
    return await get_memory_bank_stats()


async def _get_memory_bank_stats_impl(
    ctx: MCPContext | None,
    root: Path,
    include_token_budget: bool,
    include_refactoring_history: bool,
    refactoring_days: int,
) -> ModelDict:
    """Run get_memory_bank_stats logic and return result dict."""
    base_result, total_tokens = await _collect_base_stats(root)
    result_dict: ModelDict = base_result
    updated = await _add_optional_stats(
        result_dict,
        include_token_budget,
        include_refactoring_history,
        root,
        total_tokens,
        refactoring_days,
    )
    await log_client(
        ctx, "info", "get_memory_bank_stats: completed", logger_name=__name__
    )
    return updated if updated is not None else result_dict


async def _collect_base_stats(root: Path) -> tuple[ModelDict, int]:
    """Collect base statistics for Memory Bank."""
    mgrs = await initialization.get_managers(root)
    metadata_index = await get_manager(mgrs, "index", MetadataIndex)
    version_manager = await get_manager(mgrs, "versions", VersionManager)

    index_stats = await metadata_index.get_stats()
    files_metadata_raw = await metadata_index.get_all_files_metadata()
    files_metadata = {k: cast(ModelDict, v) for k, v in files_metadata_raw.items()}
    history_size = await _get_history_size(root, version_manager)

    totals = calculate_totals(files_metadata)
    result_dict = build_base_stats_result(
        root, files_metadata, totals, history_size, cast(ModelDict, index_stats)
    )
    return result_dict, totals[0]


async def _get_history_size(root: Path, version_manager: VersionManager) -> int:
    """Get total disk usage of version history directory."""
    history_dir = get_cortex_path(root, CortexResourceType.HISTORY)
    if not history_dir.exists():
        return 0
    disk_usage = await version_manager.get_disk_usage()
    return disk_usage.total_bytes


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


async def _add_optional_stats(
    result: ModelDict,
    include_token_budget: bool,
    include_refactoring_history: bool,
    root: Path,
    total_tokens: int,
    refactoring_days: int,
) -> ModelDict | None:
    """Add optional statistics to result model."""
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
