"""Composite tools: thin wrappers that chain multiple tool calls (plan: agent-skills-and-composability).

Reduces round-trips by combining common sequences:
- quick_start: session_start + load_context
- quality_check: execute_pre_commit_checks(quality) + optional fix_quality_issues
- safe_manage_file: validate + manage_file + validate (write with guard)
"""

from __future__ import annotations

import json

from cortex.core.constants import MCP_TOOL_TIMEOUT_COMPLEX
from cortex.core.mcp_annotations import read_only_annotations, safe_write_annotations
from cortex.core.mcp_stability import ensure_usage_context, mcp_tool_wrapper
from cortex.server import mcp


@mcp.tool(  # pyright: ignore[reportUntypedFunctionDecorator]
    annotations=read_only_annotations(
        "Quick Start (Session + Context)",
        idempotent=False,
    ),  # pyright: ignore[reportCallIssue]
)
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_COMPLEX)
async def quick_start(
    task_description: str | None = None,
    token_budget: int | None = None,
) -> str:
    """Run session_start then load_context in one call for fast orientation.

    USE WHEN: Starting a session and loading task context in one step.

    EXAMPLES: 'quick start', 'quick_start()', 'quick_start(task_description=
    "implement feature", token_budget=10000)', 'orient and load context'.

    RETURNS: JSON with status, session_brief (SessionStartResult), and
    context (load_context result). Combined orientation and context in one call.

    Args:
        task_description: Optional task description for load_context.
            If omitted or empty, context uses "general task". Used to select
            relevant memory bank files.
        token_budget: Maximum tokens for load_context. Default: 10000 when
            omitted. Use for implement/add (e.g. 10000) or fix/debug (e.g. 15000).
    """
    from cortex.tools.phase4_optimization_handlers import load_context
    from cortex.tools.session_start_tools import session_start

    brief_json = await session_start(task_description=None)
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
        {
            "status": "success",
            "session_brief": json.loads(brief_json),
            "context": json.loads(context_json),
        },
        indent=2,
    )


@mcp.tool(  # pyright: ignore[reportUntypedFunctionDecorator]
    annotations=safe_write_annotations("Quality Check (Pre-commit + Fix)"),
)
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_COMPLEX)
async def quality_check() -> str:
    """Run execute_pre_commit_checks(quality) then fix_quality_issues if needed.

    USE WHEN: Single-step quality gate and auto-fix before commit, or when
    user wants to run quality check and auto-fix in one call.

    EXAMPLES: 'quality check', 'run quality gate', 'check quality and fix',
    'pre-commit quality before commit'.

    RETURNS: JSON with status, pre_commit_result (execute_pre_commit_checks
    output), fix_applied (bool), and fix_result (if fix_quality_issues ran).

    Args:
        None. No parameters; runs quality check and optional fix in one call.

    Example (Success):
        ```json
        {
          "status": "success",
          "pre_commit_result": { "status": "success", "results": { ... } },
          "fix_applied": true,
          "fix_result": { "status": "success", "files_modified": 2 }
        }
        ```
    """
    from cortex.tools.pre_commit_tools import (
        execute_pre_commit_checks,
        fix_quality_issues,
    )

    pre_result = await execute_pre_commit_checks(checks=["quality"])
    success = (
        pre_result.get("status") == "success" and pre_result.get("total_errors", 0) == 0
    )
    fix_result: str | None = None
    if not success:
        fix_result = await fix_quality_issues()
    out = {
        "status": "success",
        "pre_commit_result": pre_result,
        "fix_applied": fix_result is not None,
    }
    if fix_result is not None:
        out["fix_result"] = json.loads(fix_result)
    return json.dumps(out, indent=2)


async def _safe_manage_file_impl(
    file_name: str,
    operation: str,
    content: str | None,
    sections: list[str] | None,
    change_description: str | None,
    check_type: str,
) -> str:
    from cortex.tools.file_crud_operations import manage_file
    from cortex.tools.file_operation_helpers import FileOperation
    from cortex.tools.validation_helpers import ValidationCheckType
    from cortex.tools.validation_operations import validate

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
        {
            "status": "success",
            "pre_validation": json.loads(pre),
            "manage_file_result": json.loads(file_result),
            "post_validation": json.loads(post),
        },
        indent=2,
    )


@mcp.tool(  # pyright: ignore[reportUntypedFunctionDecorator]
    annotations=safe_write_annotations(
        "Safe Manage File (Validate + Write + Validate)"
    ),
)
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_COMPLEX)
async def safe_manage_file(
    file_name: str,
    operation: str,
    content: str | None = None,
    sections: list[str] | None = None,
    change_description: str | None = None,
    check_type: str = "roadmap_sync",
) -> str:
    """Run validate, then manage_file, then validate (write with guard).

    USE WHEN: Writing memory bank files with pre/post validation to ensure
    schema/consistency before and after the write.

    EXAMPLES: 'safe_manage_file(file_name="roadmap.md", operation="read")',
    'safe write activeContext with validation', 'manage file with guard'.

    RETURNS: JSON with status, pre_validation (validate result),
    manage_file_result (manage_file result), and post_validation (validate
    result). Use when atomic write-with-validation is required.

    Args:
        file_name: Memory bank file name (e.g. "activeContext.md",
            "roadmap.md"). Resolved via project structure.
        operation: manage_file operation: "read", "write", "metadata".
        content: Full file content for operation="write". Optional for read.
        sections: Section names for section-level read/write. Optional.
        change_description: Description of change for write operations.
            Optional.
        check_type: Validation check type run before and after (e.g.
            "roadmap_sync", "schema", "timestamps"). Default: "roadmap_sync".
    """
    return await _safe_manage_file_impl(
        file_name, operation, content, sections, change_description, check_type
    )
