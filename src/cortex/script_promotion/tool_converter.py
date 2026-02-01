"""Convert validated session scripts to MCP tool templates."""

from cortex.script_detection.models import ScriptCaptureRecord


def _sanitize_tool_name(name: str) -> str:
    """Turn a name into a valid snake_case tool name."""
    normalized = "".join(c if c.isalnum() or c in " _-" else " " for c in name)
    parts = normalized.lower().split()
    return "_".join(parts) if parts else "session_script_tool"


def tool_conversion_template(
    record: ScriptCaptureRecord,
    tool_name: str | None = None,
) -> str:
    """Produce an MCP tool handler template from a captured script.

    Args:
        record: Captured script record.
        tool_name: Optional tool name; derived from task_description if missing.

    Returns:
        Python code skeleton for an MCP tool handler.
    """
    name = (tool_name or "").strip() or (record.task_description or "").strip()
    snake = _sanitize_tool_name(name or "session_script")
    doc = (record.task_description or "Session script").replace('"""', "'")
    return f'''"""
MCP tool template generated from session script: {record.script_id}
Original task: {doc[:200]}
"""

from cortex.core.constants import MCP_TOOL_TIMEOUT_FAST
from cortex.core.mcp_stability import mcp_tool_wrapper
from cortex.server import mcp


@mcp.tool()
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def {snake}(
    project_root: str | None = None,
) -> str:
    """{doc[:200]}."""
    # TODO: Port logic from captured script (see script_content).
    return '{{"status": "success", "message": "Not yet implemented"}}'
'''
