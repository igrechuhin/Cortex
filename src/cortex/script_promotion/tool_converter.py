"""Convert validated session scripts to MCP tool templates."""

from cortex.script_detection.models import ScriptCaptureRecord

# JSON return value for the generated tool template (kept out of f-strings to avoid
# format-specifier errors from braces/colons in the literal).
_TOOL_TEMPLATE_RETURN_JSON = '{"status": "success", "message": "Template for promoted session script; implement tool logic."}'

_TOOL_TEMPLATE_BODY = '''"""
MCP tool template generated from session script: {record_id}
Original task: {doc}
Original script path: {script_path}
"""

from cortex.core.constants import MCP_TOOL_TIMEOUT_FAST
from cortex.core.mcp_stability import ensure_usage_context, mcp_tool_wrapper
from cortex.server import mcp


@mcp.tool()
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def {snake}() -> str:
    """{doc}.

    Review the original script at {script_path} and adapt this handler to wrap
    or replace its behavior.
    """
    return '{return_json}'
'''


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
    script_path = (record.script_path or "").replace('"""', "'")
    return _TOOL_TEMPLATE_BODY.format(
        record_id=record.script_id,
        doc=doc[:200],
        script_path=script_path,
        snake=snake,
        return_json=_TOOL_TEMPLATE_RETURN_JSON,
    )
