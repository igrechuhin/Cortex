"""
Script Capture Tools (Phase 27)

MCP tools for capturing and listing session-generated scripts.

Total: 2 tools
- capture_session_script: Record a session-generated script with metadata
- list_session_scripts: List captured session scripts for analysis
"""

import json
from pathlib import Path

from cortex.core.constants import MCP_TOOL_TIMEOUT_FAST
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_stability import mcp_tool_wrapper
from cortex.script_detection.script_capture import capture_script
from cortex.script_detection.storage import list_captures
from cortex.server import mcp


def _project_root(project_root: str | None) -> Path:
    """Resolve project root path."""
    if project_root:
        return Path(project_root).resolve()
    return Path.cwd()


def _record_to_summary(record: object) -> dict[str, object]:
    """Build a JSON-serializable summary from a ScriptCaptureRecord."""
    r = record
    return {
        "script_id": getattr(r, "script_id", ""),
        "timestamp": getattr(r, "timestamp", ""),
        "task_description": getattr(r, "task_description", ""),
        "script_path": getattr(r, "script_path", ""),
        "script_type": getattr(r, "script_type", ""),
        "purpose": getattr(r, "purpose", ""),
        "promotion_status": getattr(r, "promotion_status", ""),
    }


@mcp.tool()
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def capture_session_script(
    script_path: str,
    script_content: str,
    task_description: str,
    script_type: str = "python",
    purpose: str = "utility",
    usage_context: str | None = None,
    project_root: str | None = None,
    ctx: MCPContext | None = None,
) -> str:
    """Record a session-generated script with metadata for later analysis.

    USE WHEN: An agent creates a temporary script during a session that
    might be worth promoting to a permanent Synapse script or MCP tool.

    EXAMPLES: 'capture this script for analysis', 'record session script
    for promotion review'.

    RETURNS: JSON with status, script_id, timestamp, and message.
    """
    root = _project_root(project_root)
    await log_client(ctx, "info", "capture_session_script: starting")
    record = await capture_script(
        project_root=root,
        script_path=script_path,
        script_content=script_content,
        task_description=task_description,
        script_type=script_type,
        purpose=purpose,
        usage_context=usage_context,
    )
    payload = {
        "status": "success",
        "script_id": record.script_id,
        "timestamp": record.timestamp,
        "message": f"Captured script {record.script_id}",
    }
    await log_client(ctx, "info", "capture_session_script: completed")
    return json.dumps(payload, indent=2)


@mcp.tool()
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def list_session_scripts(
    project_root: str | None = None,
    ctx: MCPContext | None = None,
) -> str:
    """List captured session scripts for analysis and promotion review.

    USE WHEN: User or agent wants to see what session scripts have been
    captured; preparing for script analysis or promotion.

    EXAMPLES: 'list captured scripts', 'show session scripts for analysis'.

    RETURNS: JSON with status, count, and list of script summaries.
    """
    root = _project_root(project_root)
    await log_client(ctx, "info", "list_session_scripts: starting")
    records = await list_captures(root)
    summaries = [_record_to_summary(r) for r in records]
    payload = {
        "status": "success",
        "count": len(summaries),
        "scripts": summaries,
    }
    await log_client(ctx, "info", "list_session_scripts: completed")
    return json.dumps(payload, indent=2)
