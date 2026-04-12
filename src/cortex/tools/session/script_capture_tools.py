"""
Script Capture Tools (Phase 27)

MCP tools for capturing and listing session-generated scripts.

Total: 5 tools
- capture_session_script: Record a session-generated script with metadata
- list_session_scripts: List captured session scripts for analysis
- analyze_session_scripts: Analyze captured scripts (use case, gap, promotion)
- suggest_tool_improvements: Recommend tools/scripts for a task description
- promote_session_script: Validate and get promotion template for a script
"""

import json
from enum import Enum
from urllib.parse import unquote

from cortex.core.constants import MCP_TOOL_TIMEOUT_FAST, MCP_TOOL_TIMEOUT_MEDIUM
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_stability import (
    ensure_usage_context,
    mcp_resource_wrapper,
    mcp_tool_wrapper,
)
from cortex.core.models import OperationStatus
from cortex.core.project_root_resolver import resolve_project_root_async
from cortex.discovery.recommendation_engine import recommend_tools_and_scripts
from cortex.discovery.tool_registry import get_known_script_names, get_known_tool_names
from cortex.script_analysis.script_analyzer import analyze_script
from cortex.script_detection.script_capture import capture_script
from cortex.script_detection.storage import get_capture_by_id, list_captures
from cortex.script_promotion.script_validator import validate_for_promotion
from cortex.tools.session.script_capture_handlers import dispatch_session_scripts
from cortex.tools.session.script_capture_helpers import (
    analysis_to_summary,
    build_promote_payload,
    record_to_summary,
)


class SessionScriptAnalysisField(str, Enum):
    """JSON object keys for ``analyze_session_scripts`` tool responses."""

    STATUS = "status"
    COUNT = "count"
    ANALYSES = "analyses"


@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def capture_session_script(
    script_path: str,
    script_content: str,
    task_description: str,
    script_type: str = "python",
    purpose: str = "utility",
    usage_context: str | None = None,
    ctx: MCPContext | None = None,
) -> str:
    """Record a session-generated script with metadata for later analysis.

    USE WHEN: An agent creates a temporary script during a session that
    might be worth promoting to a permanent Synapse script or MCP tool.

    EXAMPLES: 'capture this script for analysis', 'record session script
    for promotion review'.

    RETURNS: JSON with status, script_id, timestamp, and message.

    Args:
        script_path: Path or name of the script (e.g. "scripts/check_foo.py").
        script_content: Full source code of the script.
        task_description: What task the script was created for.
        script_type: Language or type (e.g. "python", "shell"). Default: "python".
        purpose: Category (e.g. "utility", "test"). Default: "utility".
        usage_context: Optional context (e.g. "pre-commit fallback").

    Example:
        >>> capture_session_script(
        ...     script_path="scripts/format_check.py",
        ...     script_content="import black; black.check(...)",
        ...     task_description="Format check fallback"
        ... )
        {"status": OperationStatus.SUCCESS.value, "script_id": "cap-20260224-123456", "timestamp": "...", "message": "Captured script ..."}
    """
    root = await resolve_project_root_async(None, ctx)
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
        "status": OperationStatus.SUCCESS.value,
        "script_id": record.script_id,
        "timestamp": record.timestamp,
        "message": f"Captured script {record.script_id}",
    }
    await log_client(ctx, "info", "capture_session_script: completed")
    return json.dumps(payload, indent=2)


@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def list_session_scripts(
    ctx: MCPContext | None = None,
) -> str:
    """List captured session scripts for analysis and promotion review.

    USE WHEN: User or agent wants to see what session scripts have been
    captured; preparing for script analysis or promotion.

    EXAMPLES: 'list captured scripts', 'show session scripts for analysis'.

    RETURNS: JSON with status, count, and list of script summaries.

    Args:
        None (ctx is internal).

    Example (Success):
        ```json
        {
          "status": OperationStatus.SUCCESS.value,
          "count": 2,
          "scripts": [
            {
              "script_id": "abc-123",
              "captured_at": "2026-02-24T10:00:00",
              "task_description": "Parse markdown links"
            }
          ]
        }
        ```
    """
    root = await resolve_project_root_async(None, ctx)
    await log_client(ctx, "info", "list_session_scripts: starting")
    records = await list_captures(root)
    summaries = [record_to_summary(r) for r in records]
    payload = {
        "status": OperationStatus.SUCCESS.value,
        "count": len(summaries),
        "scripts": summaries,
    }
    await log_client(ctx, "info", "list_session_scripts: completed")
    return json.dumps(payload, indent=2)


@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def analyze_session_scripts(
    ctx: MCPContext | None = None,
) -> str:
    """Analyze captured session scripts for use case, gap, and promotion potential.

    USE WHEN: User or agent wants to analyze captured scripts; identify
    use cases, gaps vs existing tools/scripts, and promotion potential.

    EXAMPLES: 'analyze captured scripts', 'run script analysis'.

    RETURNS: JSON with status, count, and list of analysis summaries
    (use_case_label, gap_reason, is_gap, reusability_score, promotion_potential).

    Args:
        ctx: MCP context (automatically provided).
    """
    root = await resolve_project_root_async(None, ctx)
    await log_client(ctx, "info", "analyze_session_scripts: starting")
    records = await list_captures(root)
    tool_names = get_known_tool_names()
    script_names = get_known_script_names(root)
    analyses: list[dict[str, object]] = []
    for record in records:
        result = analyze_script(record, tool_names, script_names)
        analyses.append(analysis_to_summary(result))
    payload = {
        SessionScriptAnalysisField.STATUS.value: OperationStatus.SUCCESS.value,
        SessionScriptAnalysisField.COUNT.value: len(analyses),
        SessionScriptAnalysisField.ANALYSES.value: analyses,
    }
    await log_client(ctx, "info", "analyze_session_scripts: completed")
    return json.dumps(payload, indent=2)


@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def suggest_tool_improvements(
    task_description: str,
    max_results: int = 15,
    ctx: MCPContext | None = None,
) -> str:
    """Recommend existing tools/scripts for a task description.

    USE WHEN: User or agent wants tool/script recommendations for a task;
    discover existing tools before generating a new script.

    EXAMPLES: 'suggest tools for formatting Python', 'recommend scripts for lint'.

    RETURNS: JSON with status, recommendations (name, type, score).

    Args:
        task_description: Natural language description of the task to match
            against known tools and scripts.
        max_results: Maximum number of recommendations to return (default 15).
        ctx: MCP context (automatically provided).
    """
    root = await resolve_project_root_async(None, ctx)
    await log_client(ctx, "info", "suggest_tool_improvements: starting")
    tool_names = get_known_tool_names()
    script_names = get_known_script_names(root)
    recs = recommend_tools_and_scripts(
        task_description=task_description,
        tool_names=tool_names,
        script_names=script_names,
        max_results=max_results,
    )
    recommendations = [
        {"name": name, "type": typ, "score": score} for name, typ, score in recs
    ]
    payload = {
        "status": OperationStatus.SUCCESS.value,
        "task_description": task_description,
        "recommendations": recommendations,
    }
    await log_client(ctx, "info", "suggest_tool_improvements: completed")
    return json.dumps(payload, indent=2)


# Phase 43: Script capture resources (read-only, default params)


# MCP resource registration removed
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def list_session_scripts_resource() -> str:
    """Resource: List captured session scripts (default project). Read via cortex://scripts/list."""
    return await list_session_scripts()


# MCP resource registration removed
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def analyze_session_scripts_resource() -> str:
    """Resource: Analyze captured scripts (default project). Read via cortex://scripts/analyze."""
    return await analyze_session_scripts()


# MCP resource registration removed
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def suggest_tool_improvements_resource(task_description: str) -> str:
    """Resource: Suggest tools/scripts for task (default params). Read via cortex://scripts/suggest-improvements/{task_description}. Task description may be URL-encoded."""
    decoded = unquote(task_description)
    return await suggest_tool_improvements(task_description=decoded, max_results=15)


@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def promote_session_script(
    script_id: str,
    output_type: str = "tool",
    ctx: MCPContext | None = None,
) -> str:
    """Validate a captured script and get promotion template (tool or script).

    USE WHEN: User or agent wants to promote a captured script to a
    permanent MCP tool or Synapse script; get validation and template.

    EXAMPLES: 'promote script abc-123', 'get tool template for script xyz'.

    RETURNS: JSON with status, validation, and template or issues.

    Args:
        script_id: ID of the captured script (from list_session_scripts).
        output_type: "tool" or "script" (default: "tool") — template format.

    Example (Success):
        ```json
        {
          "status": OperationStatus.SUCCESS.value,
          "script_id": "abc-123",
          "validation_passed": true,
          "quality_score": 0.85,
          "issues": [],
          "template_content": "..."
        }
        ```

    Example (Error - script not found):
        ```json
        {
          "status": OperationStatus.ERROR.value,
          "error": "Script abc-123 not found"
        }
        ```
    """
    root = await resolve_project_root_async(None, ctx)
    await log_client(ctx, "info", "promote_session_script: starting")
    record = await get_capture_by_id(root, script_id)
    if record is None:
        payload = {
            "status": OperationStatus.ERROR.value,
            "error": f"Script {script_id} not found",
        }
        await log_client(ctx, "info", "promote_session_script: completed")
        return json.dumps(payload, indent=2)
    tool_names = get_known_tool_names()
    script_names = get_known_script_names(root)
    analysis = analyze_script(record, tool_names, script_names)
    validation = validate_for_promotion(record, analysis)
    payload = build_promote_payload(record, script_id, validation, output_type)
    await log_client(ctx, "info", "promote_session_script: completed")
    return json.dumps(payload, indent=2)


# MCP registration removed — minimal agent usage
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def manage_session_scripts(
    operation: str,
    script_path: str | None = None,
    script_content: str | None = None,
    task_description: str | None = None,
    script_type: str = "python",
    purpose: str = "utility",
    script_id: str | None = None,
    max_results: int = 15,
    output_type: str = "tool",
    ctx: MCPContext | None = None,
) -> str:
    """Manage session scripts: capture, list, analyze, suggest, promote (single MCP tool).

    USE WHEN: Capturing a session-generated script, listing captured scripts,
    analyzing scripts for promotion, discovering tools for a task, or
    validating a script for promotion to Synapse/MCP.

    EXAMPLES: 'capture this script for analysis', 'list session scripts',
    'suggest tools for refactoring task', 'analyze script for promotion',
    'promote session script to tool'.

    RETURNS: JSON with status and operation-specific payload (script_id,
    scripts list, analysis result, recommendations, or promotion template).

    Args:
        operation: One of "capture", "list", "analyze", "suggest", "promote".
            capture: Record a script (requires script_path, script_content,
                task_description). list: List captured scripts (no extra args).
            analyze: Analyze captured scripts (optional task_description).
            suggest: Get tool/script recommendations (requires task_description).
            promote: Get promotion template (requires script_id).
        script_path: Path to script file (capture only).
        script_content: Script source (capture only).
        task_description: Task context (capture, suggest, or analyze).
        script_type: Script language (e.g. "python"). Default "python".
        purpose: Purpose label (e.g. "utility"). Default "utility".
        script_id: Captured script ID (promote only).
        max_results: Max results for suggest. Default 15.
        output_type: "tool" or "resource" for suggest. Default "tool".
        ctx: MCP context (automatically provided).
    """
    return await dispatch_session_scripts(
        operation=operation,
        script_path=script_path,
        script_content=script_content,
        task_description=task_description,
        script_type=script_type,
        purpose=purpose,
        script_id=script_id,
        max_results=max_results,
        output_type=output_type,
        ctx=ctx,
    )
