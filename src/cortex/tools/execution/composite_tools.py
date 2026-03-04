"""Composite tools: agent workflow dispatcher (plan: agent-skills-and-composability, tool consolidation).

Consolidates agent-skills operations into a single dispatcher:
- quick_start: session_start + load_context
- quality_check: execute_pre_commit_checks(quality) + optional fix_quality
- safe_manage_file: validate + manage_file + validate (write with guard)
- suggest_workflow: recommend workflow templates for task description
"""

from __future__ import annotations

import json
from typing import cast

from cortex.core.constants import MCP_TOOL_TIMEOUT_COMPLEX
from cortex.core.mcp_annotations import safe_write_annotations
from cortex.core.mcp_stability import ensure_usage_context, mcp_tool_wrapper
from cortex.core.models import JsonValue
from cortex.server import mcp
from cortex.tools.response_builder import error_response, success_response

# ---------------------------------------------------------------------------
# Internal implementations (no @mcp.tool; called by run_composite_workflow)
# ---------------------------------------------------------------------------


async def _quick_start_impl(
    task_description: str | None = None,
    token_budget: int | None = None,
) -> str:
    """Run session(operation=start) then load_context."""
    from cortex.tools.optimization import load_context
    from cortex.tools.session.dispatcher import session

    brief_json = await session(operation="start", task_description=None, ctx=None)
    budget = token_budget if token_budget is not None else 10000
    task = (
        task_description.strip()
        if task_description and task_description.strip()
        else "general task"
    )
    context_json = await load_context(
        task_description=task,
        token_budget=budget,
    )
    return json.dumps(
        success_response(
            session_brief=json.loads(brief_json),
            context=json.loads(context_json),
        ),
        indent=2,
    )


async def _quality_check_impl() -> str:
    """Run execute_pre_commit_checks(quality) then fix_quality if needed."""
    from cortex.tools.execution.pre_commit_tools import execute_pre_commit_checks

    pre_result = await execute_pre_commit_checks(checks=["quality"])
    success = (
        pre_result.get("status") == "success" and pre_result.get("total_errors", 0) == 0
    )
    fix_result: dict[str, object] | None = None
    if not success:
        fix_result = await execute_pre_commit_checks(
            checks=["fix_quality"], include_untracked_markdown=True
        )
    payload: dict[str, JsonValue] = {
        "pre_commit_result": cast(JsonValue, pre_result),
        "fix_applied": fix_result is not None,
    }
    if fix_result is not None:
        payload["fix_result"] = cast(JsonValue, fix_result)
    return json.dumps(success_response(**payload), indent=2)


async def _safe_manage_file_impl(
    file_name: str,
    operation: str,
    content: str | None,
    sections: list[str] | None,
    change_description: str | None,
    check_type: str,
) -> str:
    """Run validate, manage_file, validate (write with guard)."""
    from cortex.tools.files.crud_operations import manage_file
    from cortex.tools.files.operation_helpers import FileOperation
    from cortex.tools.validation.helpers import ValidationCheckType
    from cortex.tools.validation.operations import validate

    vct = ValidationCheckType(check_type)
    pre = await validate(check_type=vct)
    file_result = await manage_file(
        file_name=file_name,
        operation=FileOperation(operation),
        content=content,
        sections=sections,
        change_description=change_description,
    )
    post = await validate(check_type=vct)
    return json.dumps(
        success_response(
            pre_validation=json.loads(pre),
            manage_file_result=json.loads(file_result),
            post_validation=json.loads(post),
        ),
        indent=2,
    )


# ---------------------------------------------------------------------------
# Dispatch helpers (keep functions under 30 lines)
# ---------------------------------------------------------------------------


async def _run_safe_manage_file(
    file_name: str | None,
    file_operation: str | None,
    content: str | None,
    sections: list[str] | None,
    change_description: str | None,
    check_type: str,
) -> str:
    """Run safe_manage_file with validation of required params."""
    if not file_name or not file_operation:
        return json.dumps(
            error_response(
                error="safe_manage_file requires file_name and file_operation",
            ),
            indent=2,
        )
    return await _safe_manage_file_impl(
        file_name=file_name,
        operation=file_operation,
        content=content,
        sections=sections,
        change_description=change_description,
        check_type=check_type,
    )


async def _run_suggest_workflow(task_description: str | None, limit: int) -> str:
    """Run suggest_workflow with clamped limit."""
    from cortex.tools.execution.workflow_operations import suggest_workflow_impl

    task = (task_description or "").strip()
    lim = max(1, min(10, limit))
    return await suggest_workflow_impl(task_description=task, limit=lim)


async def _dispatch_agent_workflow(
    operation: str,
    task_description: str | None,
    token_budget: int | None,
    file_name: str | None,
    file_operation: str | None,
    content: str | None,
    sections: list[str] | None,
    change_description: str | None,
    check_type: str,
    limit: int,
) -> str:
    """Route to operation-specific implementation."""
    op = operation.strip().lower() if operation else ""
    if op == "quick_start":
        return await _quick_start_impl(
            task_description=task_description, token_budget=token_budget
        )
    if op == "quality_check":
        return await _quality_check_impl()
    if op == "safe_manage_file":
        return await _run_safe_manage_file(
            file_name, file_operation, content, sections, change_description, check_type
        )
    if op == "suggest_workflow":
        return await _run_suggest_workflow(task_description, limit)
    msg = f"Unknown operation: {operation}. Use quick_start, quality_check, safe_manage_file, or suggest_workflow."
    return json.dumps(error_response(error=msg), indent=2)


# ---------------------------------------------------------------------------
# Consolidated MCP tool: run_composite_workflow
# ---------------------------------------------------------------------------


@mcp.tool(  # pyright: ignore[reportUntypedFunctionDecorator]
    annotations=safe_write_annotations(
        "Run Composite Workflow (Session+Context, Quality, Safe File, Suggest)"
    ),  # pyright: ignore[reportCallIssue]
)
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_COMPLEX)
async def run_composite_workflow(
    operation: str,
    task_description: str | None = None,
    token_budget: int | None = None,
    file_name: str | None = None,
    file_operation: str | None = None,
    content: str | None = None,
    sections: list[str] | None = None,
    change_description: str | None = None,
    check_type: str = "roadmap_sync",
    limit: int = 3,
) -> str:
    """Run composite workflow: quick_start, quality_check, safe_manage_file, suggest_workflow.

    USE WHEN: Combining session+context, quality gate, safe file write, or workflow suggestions
    in one call. Reduces tool count; use operation= to select behavior.

    operation="quick_start": session(operation=start) + load_context. Params: task_description, token_budget.
    operation="quality_check": pre_commit quality + fix. No extra params.
    operation="safe_manage_file": validate + manage_file + validate. Params: file_name,
        file_operation, content, sections, change_description, check_type.
    operation="suggest_workflow": recommend templates. Params: task_description, limit.

    RETURNS: JSON result specific to the operation.

    Args:
        operation: quick_start, quality_check, safe_manage_file, or suggest_workflow.
        task_description, token_budget: For quick_start and suggest_workflow.
        file_name, file_operation, content: For safe_manage_file.
        check_type: For safe_manage_file (default roadmap_sync).

    Example:
        run_composite_workflow(operation="quick_start", task_description="Implement feature X")
    """
    return await _dispatch_agent_workflow(
        operation,
        task_description,
        token_budget,
        file_name,
        file_operation,
        content,
        sections,
        change_description,
        check_type,
        limit,
    )
