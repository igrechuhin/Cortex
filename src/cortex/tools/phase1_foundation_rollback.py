"""
Rollback Tool

This module provides the rollback_file_version tool for rolling back
Memory Bank files to previous versions.
"""

import json
from pathlib import Path

from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_stability import execute_tool_with_stability
from cortex.core.project_root_resolver import resolve_project_root_async
from cortex.managers import initialization
from cortex.tools.models import (
    RollbackFileVersionErrorResult,
    RollbackFileVersionResult,
)
from cortex.tools.phase1_foundation_rollback_helpers import (
    build_rollback_error_response,
    build_rollback_success_response,
    process_and_finalize_rollback,
    validate_and_get_snapshot,
)
from cortex.tools.phase1_foundation_rollback_models import RollbackManagers

__all__ = [
    "rollback_file_version",
    "execute_rollback",
    "build_rollback_error_response",
    "build_rollback_success_response",
]


async def rollback_file_version(
    file_name: str,
    version: int,
    ctx: MCPContext | None = None,
) -> str:
    """Rollback a Memory Bank file to a previous version.

    USE WHEN: User wants to undo changes, user needs to restore previous
    version, user requests rollback to specific version, user wants to revert
    file.

    EXAMPLES: 'rollback projectBrief.md to version 3', 'restore
    activeContext.md version 5', 'revert roadmap.md to previous version'.

    RETURNS: JSON with success status, rolled back version number, and file
    content.

    Restores content from a snapshot and creates a new version entry.
    This is a safe operation that preserves history - the rollback itself
    becomes a new version, allowing you to undo the rollback if needed.

    Args:
        file_name: Name of the file (e.g., "projectBrief.md")
        version: Version number to rollback to (must exist in history)

    Returns:
        JSON string with rollback status including the new version number
        created by the rollback operation.

    Example (Success):
        ```json
        {
          "status": "success",
          "file_name": "projectBrief.md",
          "rolled_back_from_version": 3,
          "new_version": 6,
          "token_count": 490
        }
        ```

    Example (Error - version not found):
        ```json
        {
          "status": "error",
          "error": "Version 10 not found for 'projectBrief.md'",
          "error_type": "ValueError"
        }
        ```

    Note:
        - Rollback creates a new version (doesn't delete history)
        - Original content is restored from snapshot
        - Metadata (tokens, size, hash) is recalculated
        - Change type is marked as "rollback" in version history
        - To undo a rollback, use get_version_history to find the
          version before rollback, then rollback to that version
    """
    await log_client(
        ctx, "info", "rollback_file_version: starting", logger_name=__name__
    )
    try:
        root = await resolve_project_root_async(None, ctx)
        result = await execute_rollback(file_name, version, root)
        await log_client(
            ctx, "info", "rollback_file_version: completed", logger_name=__name__
        )
        payload = (
            result if isinstance(result, dict) else result.model_dump(exclude_none=True)
        )
        return json.dumps(payload, indent=2)
    except Exception as e:
        await log_client(
            ctx,
            "error",
            f"rollback_file_version: failed: {e}",
            logger_name=__name__,
        )
        error_result = build_rollback_error_response(str(e), type(e).__name__)
        return json.dumps(error_result.model_dump(exclude_none=True), indent=2)


async def execute_rollback(
    file_name: str, version: int, root: Path
) -> (
    RollbackFileVersionResult
    | RollbackFileVersionErrorResult
    | dict[str, str | int | None]
):
    """Execute rollback and return result or dict for JSON serialization."""
    return await execute_tool_with_stability(
        _execute_rollback, file_name, version, str(root)
    )


async def _execute_rollback(
    file_name: str, version: int, root: str
) -> RollbackFileVersionResult | RollbackFileVersionErrorResult:
    """Execute rollback workflow.

    Args:
        file_name: Name of file to rollback
        version: Version number to rollback to
        root: Project root path

    Returns:
        RollbackFileVersionResult or RollbackFileVersionErrorResult
    """
    root_path = Path(root)
    mgrs = await initialization.get_managers(root_path)
    # These managers are produced by our initialization pipeline.
    # Avoid re-validating concrete manager instance types here; it makes
    # tests unnecessarily brittle (MagicMock) without improving safety.
    managers = RollbackManagers.model_construct(
        fs_manager=mgrs.fs,
        token_counter=mgrs.tokens,
        metadata_index=mgrs.index,
        version_manager=mgrs.versions,
    )

    validation_result = await validate_and_get_snapshot(
        managers, root_path, file_name, version
    )
    if isinstance(validation_result, RollbackFileVersionErrorResult):
        return validation_result

    file_path, content = validation_result
    return await process_and_finalize_rollback(
        managers, file_name, file_path, content, version
    )
