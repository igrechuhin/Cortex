#!/usr/bin/env python3
"""
Phase 8: Comprehensive Project Structure Management Tools

MCP tools for managing project structure, including:
- Structure health monitoring (with optional cleanup)
- Structure information retrieval

Total: 2 tools
- check_structure_health (with optional perform_cleanup parameter)
- get_structure_info

Note: setup_project_structure and migrate_project_structure
have been replaced by prompt templates in docs/prompts/

Note: cleanup_project_structure has been consolidated into check_structure_health with
perform_cleanup=True parameter.
"""

import json
from pathlib import Path
from typing import cast

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
    perform_remove_empty,
    perform_remove_legacy_cursor_artifacts,
    perform_update_index,
    record_archive_action,
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
    "get_project_root_resource",
    "move_stale_plans",
    "perform_archive_stale",
    "perform_cleanup_actions",
    "perform_remove_empty",
    "perform_remove_legacy_cursor_artifacts",
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
    """Analyze project structure health and optionally perform cleanup operations.

    USE WHEN: User wants structure health check, user needs to fix
    structure issues, user requests structure validation, user wants
    cleanup actions.

    EXAMPLES: 'check structure health', 'fix structure issues',
    'validate project structure', 'perform structure cleanup'.

    DO NOT:
    - Pass project_root or filesystem paths; the tool resolves the project
      root and structure configuration internally.
    - Use this tool as a generic filesystem cleaner outside the Cortex
      project structure; it assumes the standard .cortex layout.

    RETURNS: JSON with health score, issues found, and cleanup results.

    Performs comprehensive health checks on the MCP Memory Bank project structure,
    verifying that all required directories exist, symlinks are valid, configuration
    files are present, and files are properly organized. Optionally performs cleanup
    actions to maintain structure integrity and archive stale content.

    Health checks validate:
    - Required directories (.cortex/, .cortex/memory-bank/, .cortex/plans/, etc.)
    - Configuration files existence and validity (.cortex/config/structure.json)
    - No leftover .cursor/ artifacts from a pre-removal Cortex version
    - File organization (plans in correct subdirectories, no orphaned files)
    - Memory bank file presence (projectBrief.md, activeContext.md, etc.)

    Cleanup actions (when perform_cleanup=True):
    - archive_stale: Move inactive plans older than stale_days to archived/
    - organize_plans: Categorize plans by status (active/completed/archived)
    - remove_legacy_cursor_artifacts: Remove leftover .cursor/ artifacts (symlinks, synced agents, generated mcp.json) from a pre-removal Cortex version
    - update_index: Refresh metadata index (.cortex/index.json)
    - remove_empty: Remove empty plan directories (active/, completed/, archived/)

    Args:
        perform_cleanup: Whether to perform cleanup actions in addition to health
            checks. Default: False (check-only mode)
        cleanup_actions: List of specific cleanup actions to perform. Valid values:
            ["archive_stale", "organize_plans", "fix_symlinks", "update_index",
            "remove_empty"]. If None, performs all cleanup actions. Example:
            ["archive_stale", "fix_symlinks"]
        stale_days: Number of days of inactivity before considering a plan file
            stale for archival. Based on file modification time. Default: 90.
            Example: 30 (archive plans inactive for 30+ days)
        dry_run: If True, previews cleanup actions without making changes. If False,
            executes cleanup actions. Default: True (safe preview mode).
            Example: False (execute cleanup)

    Returns:
        JSON string containing health report. See tool descriptor for full schema.

    Note:
        - Project root is resolved internally (MCP roots or current working directory).
        - This tool replaces the deprecated cleanup_project_structure tool
        - Use perform_cleanup=True to perform cleanup actions alongside health checks
        - Always run with dry_run=True first to preview changes before executing
        - The stale_days parameter uses file modification time (st_mtime),
          not access time
        - Cleanup actions are idempotent and safe to run multiple times
        - Health score formula: 100 - (10 × number_of_issues), minimum 0
        - Grade mapping: A=90-100, B=80-89, C=70-79, D=60-69, F=0-59
        - Status mapping: healthy=90-100, good=75-89, fair=60-74,
          warning=40-59, critical=0-39
        - If structure is not initialized, returns score=0, grade=F,
          status=not_initialized
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


async def _get_structure_info_inner(ctx: MCPContext | None) -> str:
    """Resolve root, build structure JSON, and log result."""
    await log_client(ctx, "info", "get_structure_info: starting", logger_name=__name__)
    try:
        root = await resolve_project_root_async(None, ctx)
        structure_mgr = StructureManager(root)
        info_payload: ModelDict = structure_mgr.get_structure_info()
        out = json.dumps(
            {
                "success": True,
                "structure_info": info_payload,
                "message": "Structure information retrieved successfully",
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


@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_structure_info_impl(
    ctx: MCPContext | None = None,
) -> str:
    """Get current project structure configuration, paths, and status information.

    USE WHEN: User needs structure paths, user wants structure
    configuration, user requests structure info, user needs path
    information.

    EXAMPLES: 'get structure info', 'show structure paths', 'get structure
    configuration', 'get memory bank path'.

    DO NOT:
    - Pass project_root or other filesystem parameters; the tool resolves the
      project root and structure configuration internally.
    - Use this as a generic file discovery mechanism; it is focused on the
      Cortex project structure, not arbitrary directories.

    RETURNS: JSON with structure version, paths, configuration, and
    health status.

    Retrieves comprehensive information about the MCP Memory Bank project structure,
    including the structure version, all configured component paths (memory bank,
    plans, rules directories), configuration settings, existence status of each
    component, and a high-level health summary. Project root is resolved internally
    (MCP roots or current working directory); no parameters required.

    Args:
        None. Project root is resolved by the server (MCP roots or cwd).

    Returns:
        JSON string containing structure_info (paths, version, config) with a canonical
        status field.

    Example (success):
        {"status": OperationStatus.SUCCESS.value, "structure_info": {"paths": {"memory_bank": "..."}, ...},
         "message": "✅ Structure information retrieved successfully"}

    Example (error):
        {"status": OperationStatus.ERROR.value, "error": "Project root not found", "error_type": "ValueError"}

    Note:
        - This is a read-only tool that does not modify any files or directories
        - Use check_structure_health() for detailed analysis
        - All paths returned are absolute paths
    """
    return await _get_structure_info_inner(ctx)


@mcp.resource(uri="cortex://structure")
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_structure_info() -> str:
    """Resource: Project structure info. Zero-arg with caching."""
    cached = _structure_resource_cache.get("structure/info")
    if cached is not None:
        return cached
    result = await get_structure_info_impl()
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
    root = await resolve_project_root_async(None, None)
    resolved = str(root.resolve())
    cached = _structure_resource_cache.get("project/root")
    if cached is not None:
        try:
            parsed_obj: object = json.loads(cached)
            if isinstance(parsed_obj, dict):
                parsed_dict = cast(ModelDict, parsed_obj)
                if "project_root" in parsed_dict:
                    cached_root_obj = parsed_dict["project_root"]
                    if isinstance(cached_root_obj, str) and cached_root_obj == resolved:
                        return cached
        except json.JSONDecodeError:
            # Corrupt cache entry — recompute below.
            pass
    result = json.dumps({"project_root": resolved}, indent=2)
    _structure_resource_cache.set("project/root", result)
    return result
