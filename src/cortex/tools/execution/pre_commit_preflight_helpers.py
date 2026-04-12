"""Helpers for Phase A preflight checks used by commit pipeline MCP tools.

This module contains the pure business logic for `run_preflight_checks`.
Keeping helpers in a separate module allows the MCP tool registration
module to stay small and within line-count limits while preserving
testability and type safety.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import cast

from cortex.core.context_logging import MCPContext, log_client
from cortex.core.models import JsonDict, JsonValue, ModelDict, OperationStatus
from cortex.tools.execution.pre_commit_tools import (
    PreCommitCheckName,
    execute_pre_commit_checks,
)
from cortex.tools.files.markdown_lint import run_markdown_lint_all_files_check
from cortex.tools.models import (
    PreflightCheckSummary,
    RunPreflightChecksErrorResult,
    RunPreflightChecksResult,
)

_PRE_FLIGHT_DEFAULT_CHECKS: tuple[PreCommitCheckName, ...] = (
    PreCommitCheckName.FIX_ERRORS,
    PreCommitCheckName.FORMAT,
    PreCommitCheckName.SYNAPSE_FORMAT,
    PreCommitCheckName.SYNAPSE_LINT,
    PreCommitCheckName.TYPE_CHECK,
    PreCommitCheckName.QUALITY,
    PreCommitCheckName.SPELLING,
    PreCommitCheckName.TESTS,
    PreCommitCheckName.EVAL_FAST,
)


def _ensure_result_dict(value: ModelDict | str) -> ModelDict:
    """Ensure value is a dict; parse JSON string if needed (e.g. cancellation response).

    MCP stability can return CANCELLED_RESPONSE_JSON as a string. Prevents
    AttributeError: 'str' object has no attribute 'get'.
    """
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value)
        return (
            cast(ModelDict, parsed) if isinstance(parsed, dict) else cast(ModelDict, {})
        )
    except (json.JSONDecodeError, TypeError):
        return cast(
            ModelDict, {"status": OperationStatus.ERROR.value, "error": str(value)}
        )


def has_pre_commit_tool_error(execute_result: ModelDict) -> bool:
    """Return True when execute_pre_commit_checks failed as a tool."""
    status = str(execute_result.get("status"))
    error_message = execute_result.get("error")
    error_type = execute_result.get("error_type")
    return status == "error" and (error_message is not None or error_type is not None)


def markdown_has_tool_error(markdown_result: JsonDict) -> bool:
    """Return True when fix_markdown_lint reported a tool-level error."""
    status_value: JsonValue | None = markdown_result.get("status")
    return str(status_value) == "error"


def compute_preflight_passed(
    execute_result: ModelDict,
    markdown_result: JsonDict | None,
) -> bool:
    """Determine whether preflight checks passed with zero errors."""
    status = str(execute_result.get("status"))
    exec_success = status == "success"
    if not exec_success:
        return False

    if markdown_result is None:
        # If markdown was not run, base decision solely on execute_pre_commit_checks.
        return exec_success

    files_with_errors_obj = markdown_result.get("files_with_errors", 0)
    files_with_errors = (
        int(files_with_errors_obj)
        if isinstance(files_with_errors_obj, (int, str))
        else 0
    )
    error_message = markdown_result.get("error_message")
    markdown_status = str(markdown_result.get("status", "success"))
    markdown_success = files_with_errors == 0 and error_message is None
    markdown_success = markdown_success and markdown_status != "error"
    return exec_success and markdown_success


def _one_check_summary(name: str, check_dict: ModelDict) -> PreflightCheckSummary:
    """Build a single PreflightCheckSummary from a check result dict."""
    success_flag = bool(check_dict.get("success"))
    errors_value = check_dict.get("errors", [])
    warnings_value = check_dict.get("warnings", [])
    errors_count = len(errors_value) if isinstance(errors_value, list) else None
    warnings_count = len(warnings_value) if isinstance(warnings_value, list) else None
    output_obj = check_dict.get("output")
    message = str(output_obj) if output_obj else None
    return PreflightCheckSummary(
        name=name,
        status=(OperationStatus.SUCCESS if success_flag else OperationStatus.ERROR),
        errors=errors_count,
        warnings=warnings_count,
        message=message,
    )


def build_execute_check_summaries(
    execute_result: ModelDict,
) -> list[PreflightCheckSummary]:
    """Build summaries for checks returned by execute_pre_commit_checks."""
    summaries: list[PreflightCheckSummary] = []
    results_obj = execute_result.get("results", {})
    if not isinstance(results_obj, dict):
        return summaries
    results_dict = cast(dict[str, JsonValue], results_obj)
    for name, raw in results_dict.items():
        if not isinstance(raw, dict):
            continue
        summaries.append(_one_check_summary(name, cast(ModelDict, raw)))
    return summaries


def append_markdown_summary(
    summaries: list[PreflightCheckSummary],
    markdown_result: JsonDict | None,
) -> None:
    """Append markdown_lint summary entry when available."""
    if markdown_result is None:
        return

    files_with_errors_obj = markdown_result.get("files_with_errors", 0)
    files_with_errors = (
        int(files_with_errors_obj)
        if isinstance(files_with_errors_obj, (int, str))
        else 0
    )
    md_error_message = markdown_result.get("error_message")
    md_status = (
        OperationStatus.SUCCESS if files_with_errors == 0 else OperationStatus.ERROR
    )
    summaries.append(
        PreflightCheckSummary(
            name="markdown_lint",
            status=md_status,
            errors=files_with_errors,
            warnings=None,
            message=str(md_error_message) if md_error_message else None,
        )
    )


def build_check_summaries(
    execute_result: ModelDict,
    markdown_result: JsonDict | None,
) -> list[PreflightCheckSummary]:
    """Build per-check summaries from execute_pre_commit_checks and markdown lint."""
    summaries = build_execute_check_summaries(execute_result)
    append_markdown_summary(summaries, markdown_result)
    return summaries


async def _run_markdown_phase(
    include_untracked_markdown: bool,
    ctx: MCPContext | None,
) -> JsonDict | None:
    """Run markdown lint on all repo files (CI parity) and parse JSON into a dict."""
    _ = include_untracked_markdown  # Preflight always lints all files to match CI
    markdown_json = await run_markdown_lint_all_files_check(ctx=ctx)
    try:
        decoded = json.loads(markdown_json)
    except json.JSONDecodeError as exc:
        await log_client(
            ctx,
            "error",
            f"run_preflight_checks: failed to decode markdown result: {exc!s}",
            logger_name=__name__,
        )
        return None
    if not isinstance(decoded, dict):
        await log_client(
            ctx,
            "error",
            "run_preflight_checks: markdown result was not a JSON object",
            logger_name=__name__,
        )
        return None
    return cast(JsonDict, decoded)


async def _run_preflight_checks_phase_tools(
    test_timeout: int,
    coverage_threshold: float,
    strict_mode: bool,
    include_untracked_markdown: bool,
    ctx: MCPContext | None,
) -> tuple[ModelDict, str | None, JsonDict | None]:
    """Run execute_pre_commit_checks and markdown lint once for preflight."""
    checks: Sequence[PreCommitCheckName] = _PRE_FLIGHT_DEFAULT_CHECKS
    raw_result = await execute_pre_commit_checks(
        checks=checks,
        test_timeout=test_timeout,
        coverage_threshold=coverage_threshold,
        strict_mode=strict_mode,
        ctx=ctx,
    )
    execute_result = _ensure_result_dict(raw_result)
    language_value = execute_result.get("language")
    language = str(language_value) if isinstance(language_value, str) else None
    markdown_result = await _run_markdown_phase(include_untracked_markdown, ctx)
    return execute_result, language, markdown_result


def build_preflight_model(
    execute_result: ModelDict,
    language: str | None,
    markdown_result: JsonDict | None,
    ctx: MCPContext | None,
) -> ModelDict:
    """Build success or error model for run_preflight_checks."""
    if has_pre_commit_tool_error(execute_result) or (
        markdown_result is not None and markdown_has_tool_error(markdown_result)
    ):
        error_model = RunPreflightChecksErrorResult(
            error="run_preflight_checks: underlying tool error during preflight",
            error_type="PreflightToolError",
            language=language,
            execute_result=cast(JsonDict, execute_result),
            markdown_result=markdown_result,
        )
        # Logging handled by caller; keep this helper pure except for type.
        return cast(ModelDict, error_model.model_dump(mode="json"))

    preflight_passed = compute_preflight_passed(execute_result, markdown_result)
    summaries = build_check_summaries(execute_result, markdown_result)
    result_model = RunPreflightChecksResult(
        preflight_passed=preflight_passed,
        language=language,
        checks=summaries,
        execute_result=cast(JsonDict, execute_result),
        markdown_result=markdown_result,
    )
    return cast(ModelDict, result_model.model_dump(mode="json"))


async def run_preflight_checks_impl(
    test_timeout: int,
    coverage_threshold: float,
    strict_mode: bool,
    include_untracked_markdown: bool = True,
    ctx: MCPContext | None = None,
) -> ModelDict:
    """Core implementation for run_preflight_checks (no logging wrapper)."""
    execute_result, language, markdown_result = await _run_preflight_checks_phase_tools(
        test_timeout,
        coverage_threshold,
        strict_mode,
        include_untracked_markdown,
        ctx,
    )
    return build_preflight_model(execute_result, language, markdown_result, ctx)


__all__ = ["run_preflight_checks_impl"]
