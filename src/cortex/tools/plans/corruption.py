"""
Roadmap corruption fixing tools.

This module contains MCP tools for detecting and fixing text corruption
patterns in the Memory Bank roadmap.md file.
"""

from cortex.core.constants import MCP_TOOL_TIMEOUT_MEDIUM
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_stability import ensure_usage_context, mcp_tool_wrapper
from cortex.core.project_root_resolver import resolve_project_root_async
from cortex.tools.plans.corruption_detectors import detect_roadmap_corruption
from cortex.tools.plans.corruption_helpers import (
    create_roadmap_error_response,
    fix_memory_bank_content_if_needed,
    fix_roadmap_content_if_needed,
    fix_roadmap_corruption_run,
)

__all__ = [
    "detect_roadmap_corruption",
    "fix_memory_bank_content_if_needed",
    "fix_roadmap_content_if_needed",
    "fix_roadmap_corruption",
]


# Internalized for tool budget reduction (2026-02-26). Rare admin; kept as callable.
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def fix_roadmap_corruption(
    dry_run: bool = False,
    ctx: MCPContext | None = None,
) -> str:
    """Fix text corruption in roadmap.md file.

    USE WHEN: User reports roadmap corruption, user needs roadmap fix,
    user requests corruption repair, user wants to fix roadmap.

    EXAMPLES: 'fix roadmap corruption', 'repair roadmap.md',
    fix_roadmap_corruption(dry_run=True), 'restore roadmap formatting'.

    RETURNS: JSON with fix status, changes made (matches fixed), and roadmap
    health. On error, status \"error\" and error message.

    Detects and fixes corruption patterns: missing spaces/newlines, corrupted
    text like 'ented'->'Implemented', malformed dates, corrupted scores.

    Args:
        dry_run: If True, report what would be fixed without writing (default False).
    """
    await log_client(
        ctx, "info", "fix_roadmap_corruption: starting", logger_name=__name__
    )
    try:
        root = await resolve_project_root_async(None, ctx)
        result, ok = fix_roadmap_corruption_run(root, dry_run)
        if ok:
            await log_client(
                ctx, "info", "fix_roadmap_corruption: completed", logger_name=__name__
            )
        else:
            await log_client(
                ctx,
                "warning",
                "fix_roadmap_corruption: roadmap not found",
                logger_name=__name__,
            )
        return result
    except Exception as e:
        await log_client(
            ctx, "error", f"fix_roadmap_corruption: failed: {e}", logger_name=__name__
        )
        return create_roadmap_error_response(str(e))
