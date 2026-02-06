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
from urllib.parse import unquote

from cortex.core.constants import MCP_TOOL_TIMEOUT_FAST, MCP_TOOL_TIMEOUT_MEDIUM
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_annotations import read_only_annotations, safe_write_annotations
from cortex.core.mcp_stability import (
    ensure_usage_context,
    mcp_resource_wrapper,
    mcp_tool_wrapper,
)
from cortex.core.project_root_resolver import resolve_project_root_async
from cortex.discovery.recommendation_engine import recommend_tools_and_scripts
from cortex.discovery.tool_registry import get_known_script_names, get_known_tool_names
from cortex.script_analysis.script_analyzer import analyze_script
from cortex.script_detection.models import ScriptCaptureRecord
from cortex.script_detection.script_capture import capture_script
from cortex.script_detection.storage import get_capture_by_id, list_captures
from cortex.script_promotion.models import ValidationResult
from cortex.script_promotion.script_integrator import script_integration_template
from cortex.script_promotion.script_validator import validate_for_promotion
from cortex.script_promotion.tool_converter import tool_conversion_template
from cortex.server import mcp


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


@mcp.tool(annotations=safe_write_annotations("Capture Session Script"))
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
        "status": "success",
        "script_id": record.script_id,
        "timestamp": record.timestamp,
        "message": f"Captured script {record.script_id}",
    }
    await log_client(ctx, "info", "capture_session_script: completed")
    return json.dumps(payload, indent=2)


@mcp.tool(annotations=read_only_annotations("List Session Scripts"))
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
    """
    root = await resolve_project_root_async(None, ctx)
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


def _build_promote_payload(
    record: ScriptCaptureRecord,
    script_id: str,
    validation: ValidationResult,
    output_type: str,
) -> dict[str, object]:
    """Build JSON payload for promote_session_script success response."""
    payload: dict[str, object] = {
        "status": "success",
        "script_id": script_id,
        "validation_passed": validation.passed,
        "quality_score": validation.quality_score,
        "issues": validation.issues,
    }
    if output_type == "script":
        rel_path, content = script_integration_template(record)
        payload["template_path"] = rel_path
        payload["template_content"] = content
    else:
        payload["template_content"] = tool_conversion_template(record)
    return payload


def _analysis_to_summary(obj: object) -> dict[str, object]:
    """Build JSON-serializable summary from ScriptAnalysisResult."""
    return {
        "script_id": getattr(obj, "script_id", ""),
        "use_case_label": getattr(getattr(obj, "use_case", None), "use_case_label", ""),
        "keywords": getattr(getattr(obj, "use_case", None), "keywords", []),
        "gap_reason": getattr(getattr(obj, "gap", None), "gap_reason", ""),
        "is_gap": getattr(getattr(obj, "gap", None), "is_gap", True),
        "reusability_score": getattr(obj, "reusability_score", 0.0),
        "promotion_potential": getattr(obj, "promotion_potential", 0.0),
    }


@mcp.tool(annotations=read_only_annotations("Analyze Session Scripts"))
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def analyze_session_scripts(
    ctx: MCPContext | None = None,
) -> str:
    """Analyze captured session scripts for use case, gap, and promotion potential.

    USE WHEN: User or agent wants to analyze captured scripts; identify
    use cases, gaps vs existing tools/scripts, and promotion potential.

    EXAMPLES: 'analyze captured scripts', 'run script analysis'.

    RETURNS: JSON with status, count, and list of analysis summaries.
    """
    root = await resolve_project_root_async(None, ctx)
    await log_client(ctx, "info", "analyze_session_scripts: starting")
    records = await list_captures(root)
    tool_names = get_known_tool_names()
    script_names = get_known_script_names(root)
    analyses: list[dict[str, object]] = []
    for record in records:
        result = analyze_script(record, tool_names, script_names)
        analyses.append(_analysis_to_summary(result))
    payload = {
        "status": "success",
        "count": len(analyses),
        "analyses": analyses,
    }
    await log_client(ctx, "info", "analyze_session_scripts: completed")
    return json.dumps(payload, indent=2)


@mcp.tool(annotations=read_only_annotations("Suggest Tool Improvements"))
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
        "status": "success",
        "task_description": task_description,
        "recommendations": recommendations,
    }
    await log_client(ctx, "info", "suggest_tool_improvements: completed")
    return json.dumps(payload, indent=2)


# Phase 43: Script capture resources (read-only, default params)


@mcp.resource(uri="cortex://scripts/list")
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def list_session_scripts_resource() -> str:
    """Resource: List captured session scripts (default project). Read via cortex://scripts/list."""
    return await list_session_scripts()


@mcp.resource(uri="cortex://scripts/analyze")
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def analyze_session_scripts_resource() -> str:
    """Resource: Analyze captured scripts (default project). Read via cortex://scripts/analyze."""
    return await analyze_session_scripts()


@mcp.resource(uri="cortex://scripts/suggest-improvements/{task_description}")
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def suggest_tool_improvements_resource(task_description: str) -> str:
    """Resource: Suggest tools/scripts for task (default params). Read via cortex://scripts/suggest-improvements/{task_description}. Task description may be URL-encoded."""
    decoded = unquote(task_description)
    return await suggest_tool_improvements(task_description=decoded, max_results=15)


@mcp.tool(annotations=safe_write_annotations("Promote Session Script"))
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
    """
    root = await resolve_project_root_async(None, ctx)
    await log_client(ctx, "info", "promote_session_script: starting")
    record = await get_capture_by_id(root, script_id)
    if record is None:
        payload = {
            "status": "error",
            "error": f"Script {script_id} not found",
        }
        await log_client(ctx, "info", "promote_session_script: completed")
        return json.dumps(payload, indent=2)
    tool_names = get_known_tool_names()
    script_names = get_known_script_names(root)
    analysis = analyze_script(record, tool_names, script_names)
    validation = validate_for_promotion(record, analysis)
    payload = _build_promote_payload(record, script_id, validation, output_type)
    await log_client(ctx, "info", "promote_session_script: completed")
    return json.dumps(payload, indent=2)
