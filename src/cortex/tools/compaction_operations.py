"""Session compaction tool and handoff read/write (Phase 56)."""

import json
from pathlib import Path
from typing import cast

from cortex.core.constants import MCP_TOOL_TIMEOUT_MEDIUM
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.file_system import FileSystemManager
from cortex.core.mcp_stability import ensure_usage_context, mcp_tool_wrapper
from cortex.core.metadata_index import MetadataIndex
from cortex.core.token_counter import TokenCounter
from cortex.core.usage_context import (
    get_current_managers,
    get_or_resolve_project_root,
)
from cortex.core.version_manager import VersionManager
from cortex.managers.manager_utils import get_manager
from cortex.managers.types import ManagersDict
from cortex.tools.compaction_handoff import (
    HandoffParams,
    read_handoff,
    to_handoff_params,
    write_handoff,
)
from cortex.tools.compaction_write_helpers import compact_session_run

__all__ = ["compact_session", "write_handoff", "read_handoff"]


async def _compact_session_impl(
    summary: str | None,
    project_root: Path,
    managers: dict[str, object],
    handoff_params: HandoffParams | None,
    create_checkpoint: bool,
) -> str:
    """Implementation of compact_session: resolve managers and run compaction."""
    managers_dict = cast(ManagersDict, managers)
    fs_manager = await get_manager(managers_dict, "fs", FileSystemManager)
    token_counter = await get_manager(managers_dict, "tokens", TokenCounter)
    metadata_index = await get_manager(managers_dict, "index", MetadataIndex)
    version_manager = await get_manager(managers_dict, "versions", VersionManager)
    return await compact_session_run(
        project_root,
        summary,
        fs_manager,
        token_counter,
        metadata_index,
        version_manager,
        handoff_params,
        create_checkpoint,
    )


@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def compact_session(
    summary: str | None = None,
    completed_tasks: list[str] | None = None,
    in_progress_task: str | None = None,
    in_progress_notes: str | None = None,
    blockers: list[str] | None = None,
    decisions_made: list[str] | None = None,
    create_checkpoint: bool = False,
    ctx: MCPContext | None = None,
) -> str:
    """Compact activeContext and progress, write session handoff for next session.

    USE WHEN: End of session, reducing memory bank size, preparing handoff.

    EXAMPLES: 'compact_session(summary="Implemented Step 1; next: audit remaining tools")',
    'compact session', 'run session compaction'.

    RETURNS: JSON with status, token_savings, tokens_after, rollback_snapshots.

    Reads activeContext.md and progress.md, keeps current date in Completed Work
    and recent entries in progress, summarizes older content, writes handoff JSON
    to .cortex/.cache/session/last_handoff.json and progress.txt (structured
    format), and updates the files. Pre-compaction snapshots saved for rollback.

    Args:
        summary: Optional free-form summary (stored in handoff next_actions).
        completed_tasks: Optional list of completed tasks this session.
        in_progress_task: Optional task in progress.
        in_progress_notes: Optional notes for in-progress task.
        blockers: Optional list of current blockers.
        decisions_made: Optional list of key decisions.
        create_checkpoint: If True, create git tag cortex/session-YYYY-MM-DD-HH-MM.

    Returns:
        JSON with status, token_savings, tokens_after, rollback_snapshots.
    """
    await log_client(ctx, "info", "compact_session: starting", logger_name=__name__)
    project_root = await get_or_resolve_project_root(ctx)
    managers_raw = get_current_managers()
    if managers_raw is None:
        return json.dumps(
            {"status": "error", "error": "Managers not initialized"}, indent=2
        )
    hp = to_handoff_params(
        completed_tasks,
        in_progress_task,
        in_progress_notes,
        blockers,
        decisions_made,
    )
    return await _compact_session_impl(
        summary, project_root, managers_raw, hp, create_checkpoint
    )
