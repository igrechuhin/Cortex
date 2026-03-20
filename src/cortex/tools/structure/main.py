#!/usr/bin/env python3
"""
Phase 8: Comprehensive Project Structure Management Tools

MCP tools for managing project structure, including:
- Structure health monitoring (with optional cleanup)
- Structure information retrieval

Total: 2 tools
- check_structure_health (with optional perform_cleanup parameter)
- get_structure_info

Note: setup_project_structure, migrate_project_structure, and setup_cursor_integration
have been replaced by prompt templates in docs/prompts/

Note: cleanup_project_structure has been consolidated into check_structure_health with
perform_cleanup=True parameter.
"""

import json
from pathlib import Path

from cortex.core.cache import TTLCache
from cortex.core.constants import (
    MCP_RESOURCE_CACHE_TTL_SECONDS,
    MCP_TOOL_TIMEOUT_COMPLEX,
    MCP_TOOL_TIMEOUT_FAST,
)
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_stability import (
    ensure_usage_context,
    mcp_resource_wrapper,
    mcp_tool_wrapper,
)
from cortex.core.models import ModelDict
from cortex.core.project_root_resolver import resolve_project_root_async
from cortex.server import mcp
from cortex.structure.manager import StructureManager
from cortex.tools.structure.operations import (
    find_stale_plans,
    move_stale_plans,
    perform_archive_stale,
    perform_cleanup_actions,
    perform_fix_symlinks,
    perform_remove_empty,
    perform_update_index,
    record_archive_action,
)
from cortex.tools.structure.structure_docs import (
    CHECK_STRUCTURE_HEALTH_DOC,
    GET_STRUCTURE_INFO_DOC,
)
from cortex.tools.structure.validation import (
    build_health_result,
    check_structure_initialized,
)

# Short-TTL cache for structure resources so queued reads after a long tool drain quickly
_structure_resource_cache: TTLCache[str] = TTLCache(MCP_RESOURCE_CACHE_TTL_SECONDS)


def invalidate_structure_resource_cache(key: str | None = None) -> None:
    """Invalidate cache entry by key, or clear all if key is None. Used by tests."""
    if key is None:
        _structure_resource_cache.clear()
    else:
        _structure_resource_cache.invalidate(key)


# Re-export for tests and backward compatibility
__all__ = [
    "invalidate_structure_resource_cache",
    "build_health_result",
    "check_structure_health",
    "check_structure_health_resource",
    "check_structure_initialized",
    "find_stale_plans",
    "get_structure_info",
    "get_structure_info_resource",
    "get_project_root_resource",
    "move_stale_plans",
    "perform_archive_stale",
    "perform_cleanup_actions",
    "perform_fix_symlinks",
    "perform_remove_empty",
    "perform_update_index",
    "record_archive_action",
]


async def _check_structure_health_impl(
    root: Path,
    perform_cleanup: bool,
    cleanup_actions: list[str] | None,
    stale_days: int,
    dry_run: bool,
    ctx: MCPContext | None,
) -> str:
    """Run check_structure_health logic. Returns JSON string."""
    structure_mgr = StructureManager(root)
    not_initialized_response = check_structure_initialized(structure_mgr)
    if not_initialized_response:
        await log_client(
            ctx,
            "warning",
            "check_structure_health: structure not initialized",
            logger_name=__name__,
        )
        return not_initialized_response
    health = structure_mgr.check_structure_health()
    result = build_health_result(health)
    result_dict = result.model_dump()
    if perform_cleanup:
        cleanup_report = await perform_cleanup_actions(
            structure_mgr, cleanup_actions, stale_days, dry_run, root
        )
        result_dict["cleanup"] = cleanup_report.model_dump()
    return json.dumps(result_dict, indent=2)


async def _check_structure_health_with_logging(
    root: Path,
    perform_cleanup: bool,
    cleanup_actions: list[str] | None,
    stale_days: int,
    dry_run: bool,
    ctx: MCPContext | None,
) -> str:
    """Run check_structure_health with try/except and error logging."""
    try:
        out = await _check_structure_health_impl(
            root,
            perform_cleanup,
            cleanup_actions,
            stale_days,
            dry_run,
            ctx,
        )
        await log_client(
            ctx, "info", "check_structure_health: completed", logger_name=__name__
        )
        return out
    except Exception as e:
        await log_client(
            ctx, "error", f"check_structure_health: {e!s}", logger_name=__name__
        )
        return json.dumps(
            {"success": False, "error": str(e), "error_type": type(e).__name__},
            indent=2,
        )


# MCP registration removed — get_structure_info covers structure needs
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_COMPLEX)
async def check_structure_health(
    perform_cleanup: bool = False,
    cleanup_actions: list[str] | None = None,
    stale_days: int = 90,
    dry_run: bool = True,
    ctx: MCPContext | None = None,
) -> str:
    """Analyze project structure health and optionally perform cleanup.

    USE WHEN: You want a high-level structure health report or to perform
    cleanup actions (archive stale plans, fix symlinks, update index).

    EXAMPLES: 'check_structure_health()', 'check_structure_health(perform_cleanup=True)'.

    DO NOT:
    - Pass project_root or filesystem paths; the tool resolves the project root
      and structure configuration internally.
    - Use this as a generic filesystem cleaner for non-Cortex directories.
    """
    await log_client(
        ctx, "info", "check_structure_health: starting", logger_name=__name__
    )
    root = await resolve_project_root_async(None, ctx)
    return await _check_structure_health_with_logging(
        root,
        perform_cleanup,
        cleanup_actions,
        stale_days,
        dry_run,
        ctx,
    )


check_structure_health.__doc__ = CHECK_STRUCTURE_HEALTH_DOC


@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_structure_info(
    ctx: MCPContext | None = None,
) -> str:
    """Get current project structure configuration, paths, and status.

    USE WHEN: You need the canonical paths for memory_bank, plans, rules, or
    want to inspect structure.json configuration.

    EXAMPLES: 'get_structure_info()' to retrieve structure paths and status.

    DO NOT:
    - Pass project_root or other filesystem parameters; the tool resolves the
      project root and structure configuration internally.
    - Use this as a generic file discovery helper outside the Cortex project
      structure.
    """
    await log_client(ctx, "info", "get_structure_info: starting", logger_name=__name__)
    try:
        root = await resolve_project_root_async(None, ctx)
        structure_mgr = StructureManager(root)

        info = structure_mgr.get_structure_info()

        info_payload: ModelDict = info
        out = json.dumps(
            {
                "success": True,
                "structure_info": info_payload,
                "message": "✅ Structure information retrieved successfully",
            },
            indent=2,
        )
        await log_client(
            ctx, "info", "get_structure_info: completed", logger_name=__name__
        )
        return out

    except Exception as e:
        await log_client(
            ctx, "error", f"get_structure_info: {e!s}", logger_name=__name__
        )
        return json.dumps(
            {"success": False, "error": str(e), "error_type": type(e).__name__},
            indent=2,
        )


get_structure_info.__doc__ = GET_STRUCTURE_INFO_DOC


@mcp.resource(uri="cortex://structure")
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_structure_info_resource() -> str:
    """Resource: Project structure info. Zero-arg with caching."""
    cached = _structure_resource_cache.get("structure/info")
    if cached is not None:
        return cached
    result = await get_structure_info()
    _structure_resource_cache.set("structure/info", result)
    return result


# MCP resource registration removed
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_COMPLEX)
async def check_structure_health_resource() -> str:
    """Resource: Structure health check (read-only, no cleanup). Read via cortex://structure/health."""
    cached = _structure_resource_cache.get("structure/health")
    if cached is not None:
        return cached
    result = await check_structure_health(
        perform_cleanup=False,
        cleanup_actions=None,
        stale_days=90,
        dry_run=True,
    )
    _structure_resource_cache.set("structure/health", result)
    return result


# MCP resource registration removed
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_project_root_resource() -> str:
    """Resource: Resolved project root path (idempotent). Read via cortex://project/root."""
    cached = _structure_resource_cache.get("project/root")
    if cached is not None:
        return cached
    root = await resolve_project_root_async(None, None)
    result = json.dumps(
        {"project_root": str(root.resolve())},
        indent=2,
    )
    _structure_resource_cache.set("project/root", result)
    return result


get_structure_info.__doc__ = GET_STRUCTURE_INFO_DOC
