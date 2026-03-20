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
from cortex.core.mcp_stability import (
    ensure_usage_context,
    mcp_tool_wrapper,
)
from cortex.core.models import JsonValue, ModelDict
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
    fix_result: ModelDict | None = None
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


async def _fix_docs_impl() -> str:
    """Run Phase B docs/memory-bank sync and return full result. Zero args required."""
    from cortex.tools.execution.pre_commit_docs_memory_helpers import (
        run_docs_and_memory_bank_sync_impl,
    )
    from cortex.tools.validation.helpers import ValidationCheckType
    from cortex.tools.validation.operations import validate

    docs = await run_docs_and_memory_bank_sync_impl()
    ts = await validate(check_type=ValidationCheckType("timestamps"))
    rs = await validate(check_type=ValidationCheckType("roadmap_sync"))
    payload: dict[str, JsonValue] = {
        "docs_phase_b": docs,
        "timestamps": json.loads(ts),
        "roadmap_sync": json.loads(rs),
        "docs_phase_passed": docs.get("docs_phase_passed", False),
    }
    return json.dumps(success_response(**payload), indent=2)


def _fix_all_payload(
    quality: ModelDict,
    verify: ModelDict,
    tests: ModelDict,
    docs: ModelDict,
    ts: str,
    rs: str,
) -> dict[str, JsonValue]:
    """Build fix_all result payload dict."""
    return {
        "quality_fix": cast(JsonValue, quality),
        "quality_verify": cast(JsonValue, verify),
        "tests": cast(JsonValue, tests),
        "docs_phase_b": cast(JsonValue, docs),
        "timestamps": cast(JsonValue, json.loads(ts)),
        "roadmap_sync": cast(JsonValue, json.loads(rs)),
    }


async def _resolve_detached(result: ModelDict, root: object) -> ModelDict:
    """If result is a detached job stub {job_id, status}, poll to completion.

    In detached mode execute_pre_commit_checks returns {job_id, status} immediately.
    This helper waits for the worker to finish and returns the full inner result dict
    so callers get output/errors fields for targeted fix application.
    """
    from pathlib import Path

    from cortex.tools.execution.pre_commit_detached import poll_job_to_completion

    job_id = result.get("job_id")
    status = result.get("status")
    if not isinstance(job_id, str) or status not in ("started", "already_running"):
        return result  # Already a full result or a cache hit — return as-is.
    if not isinstance(root, Path):
        return result  # Cannot poll without a valid root.
    polled = await poll_job_to_completion(root, job_id)
    return cast(ModelDict, polled)


async def _run_fix_quality_job() -> ModelDict:
    from cortex.tools.execution.pre_commit_tools import execute_pre_commit_checks

    return await execute_pre_commit_checks(
        checks=["fix_quality"], include_untracked_markdown=True
    )


async def _run_verify_job() -> ModelDict:
    from cortex.tools.execution.pre_commit_tools import execute_pre_commit_checks

    return await execute_pre_commit_checks(
        checks=["type_check", "quality", "format", "markdown"],
        test_timeout=300,
        coverage_threshold=0.90,
        strict_mode=False,
    )


async def _run_tests_job() -> ModelDict:
    from cortex.tools.execution.pre_commit_tools import execute_pre_commit_checks

    return await execute_pre_commit_checks(
        checks=["tests"],
        test_timeout=600,
        coverage_threshold=0.90,
        strict_mode=False,
    )


async def _run_docs_job() -> ModelDict:
    from cortex.tools.execution.pre_commit_tools import execute_pre_commit_checks

    return await execute_pre_commit_checks(
        phase="B",
        test_timeout=600,
        coverage_threshold=0.90,
        strict_mode=False,
    )


async def _fix_all_impl() -> str:
    """Run full fix sequence: quality → tests → docs. Zero args required."""
    from cortex.core.usage_context import get_current_project_root
    from cortex.tools.execution.pre_commit_detached import clear_all_cached_results
    from cortex.tools.validation.helpers import ValidationCheckType
    from cortex.tools.validation.operations import validate

    root = get_current_project_root()
    quality = await _run_fix_quality_job()
    if root is not None:
        _ = clear_all_cached_results(root)
    verify_raw = await _run_verify_job()
    tests_raw = await _run_tests_job()
    docs_raw = await _run_docs_job()
    verify = await _resolve_detached(verify_raw, root)
    tests = await _resolve_detached(tests_raw, root)
    docs = await _resolve_detached(docs_raw, root)
    ts = await validate(check_type=ValidationCheckType("timestamps"))
    rs = await validate(check_type=ValidationCheckType("roadmap_sync"))
    return json.dumps(
        success_response(**_fix_all_payload(quality, verify, tests, docs, ts, rs)),
        indent=2,
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
    if op == "fix_docs":
        return await _fix_docs_impl()
    if op in ("fix_all", ""):
        return await _fix_all_impl()
    msg = f"Unknown operation: {operation}. Use quick_start, quality_check, fix_all, fix_docs, safe_manage_file, or suggest_workflow."
    return json.dumps(error_response(error=msg), indent=2)


# ---------------------------------------------------------------------------
# Consolidated MCP tool: run_composite_workflow
# ---------------------------------------------------------------------------


# MCP registration removed — use individual zero-arg tools instead
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_COMPLEX)
async def run_composite_workflow(
    operation: str = "fix_all",
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
    """Run composite workflow: quick_start, quality_check, fix_all, safe_manage_file, suggest_workflow.

    USE WHEN: Combining session+context, quality gate, safe file write, or workflow suggestions
    in one call. Reduces tool count; use operation= to select behavior.

    operation="quick_start": session(operation=start) + load_context. Params: task_description, token_budget.
    operation="quality_check": pre_commit quality + fix. No extra params.
    operation="fix_all": Full fix sequence (quality→tests→docs) with zero args. USE THIS when
        the MCP bridge cannot pass arguments to individual tools (e.g. Cursor tool bridge sends
        empty {} — causes "Missing required parameters" errors on rules, load_context,
        execute_pre_commit_checks). fix_all runs fix_quality, type_check/quality/format/markdown
        verification, tests (600s, 90% coverage), phase B docs validation, and
        timestamps+roadmap_sync validation — all with sensible hardcoded defaults.
    operation="fix_docs": Run Phase B docs/memory-bank sync validation (timestamps +
        roadmap_sync). Zero args. Use this instead of execute_pre_commit_checks(phase="B")
        when the bridge cannot pass arguments — that call zero-args to Phase A (runs tests).
    operation="safe_manage_file": validate + manage_file + validate. Params: file_name,
        file_operation, content, sections, change_description, check_type.
    operation="suggest_workflow": recommend templates. Params: task_description, limit.

    RETURNS: JSON result specific to the operation.

    Args:
        operation: quick_start, quality_check, fix_all, fix_docs, safe_manage_file, or suggest_workflow.
            Defaults to "fix_all" — so a zero-arg call (when the MCP bridge cannot pass
            arguments) automatically runs the full quality→tests→docs fix sequence.
        task_description, token_budget: For quick_start and suggest_workflow.
        file_name, file_operation, content: For safe_manage_file.
        check_type: For safe_manage_file (default roadmap_sync).

    EXAMPLES:
        run_composite_workflow(operation="quick_start", task_description="Implement feature X")
        run_composite_workflow(operation="quality_check")
        run_composite_workflow(operation="fix_all")
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
