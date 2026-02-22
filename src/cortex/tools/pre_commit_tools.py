"""Pre-Commit Tools

MCP tools for executing pre-commit checks with language auto-detection.

Total: 2 tools
- execute_pre_commit_checks: Execute pre-commit checks (fix errors,
  format, type check, quality, tests)
- fix_quality_issues: Automatically fix quality issues on-the-go
  (fix errors, format, type check, markdown lint)
"""

import asyncio
import json
import logging
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import cast

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.constants import MCP_TOOL_TIMEOUT_VERY_COMPLEX
from cortex.core.context_logging import MCPContext, log_client, report_progress_safe
from cortex.core.mcp_annotations import external_annotations, safe_write_annotations
from cortex.core.mcp_stability import (
    check_connection_health,
    ensure_usage_context,
    mcp_tool_wrapper,
)
from cortex.core.models import ConnectionHealth, JsonValue, ModelDict, OperationStatus
from cortex.core.usage_context import get_or_resolve_project_root
from cortex.server import mcp
from cortex.services.framework_adapters.base import (
    CheckResult,
    FrameworkAdapter,
    TestResult,
)
from cortex.services.framework_adapters.go_adapter import GoAdapter
from cortex.services.framework_adapters.java_adapter import JavaAdapter
from cortex.services.framework_adapters.javascript_adapter import JavaScriptAdapter
from cortex.services.framework_adapters.kotlin_adapter import KotlinAdapter
from cortex.services.framework_adapters.python_adapter import PythonAdapter
from cortex.services.framework_adapters.rust_adapter import RustAdapter
from cortex.services.framework_adapters.swift_adapter import SwiftAdapter
from cortex.services.framework_adapters.typescript_adapter import TypeScriptAdapter
from cortex.services.language_detector import LanguageInfo

# No circular import: markdown_operations doesn't import pre_commit_tools
from cortex.tools.markdown_operations import fix_markdown_lint  # noqa: F401
from cortex.tools.pre_commit_helpers import (
    CheckStats,
    PreCommitCheck,
    PreCommitResult,
    QualityCheckResult,
    collect_remaining_issues,
    create_error_result_dict,
    detect_or_use_language,
    determine_checks_to_perform,
    ensure_json_serializable_for_mcp,
    extract_check_results,
    extract_dict_from_object,
    extract_int_from_object,
    extract_list_from_object,
    truncate_large_logs_in_data,
    unsupported_language_result_dict,
)
from cortex.tools.pre_commit_pipeline import run_checks_pipeline

logger = logging.getLogger(__name__)

# Adapter registry: language -> factory(project_root) -> FrameworkAdapter.
# Python, TypeScript, JavaScript, Rust, Go, Java, Swift, and Kotlin have full implementations.
_ADAPTER_REGISTRY: dict[str, Callable[[str | None], FrameworkAdapter]] = {
    "python": lambda root: PythonAdapter(root),
    "typescript": lambda root: TypeScriptAdapter(root),
    "javascript": lambda root: JavaScriptAdapter(root),
    "rust": lambda root: RustAdapter(root),
    "go": lambda root: GoAdapter(root),
    "java": lambda root: JavaAdapter(root),
    "swift": lambda root: SwiftAdapter(root),
    "kotlin": lambda root: KotlinAdapter(root),
}
SUPPORTED_LANGUAGES: tuple[str, ...] = tuple(_ADAPTER_REGISTRY.keys())

# Type alias for check names (must match PreCommitCheck enum).
PreCommitCheckName = PreCommitCheck


def _get_adapter(
    language_info: LanguageInfo, project_root: str | None
) -> FrameworkAdapter | None:
    """Get framework adapter for detected language.

    Args:
        language_info: Detected language information.
        project_root: Project root directory.

    Returns:
        Framework adapter instance or None if language not in registry.
    """
    factory = _ADAPTER_REGISTRY.get(language_info.language)
    if factory is None:
        return None
    return factory(project_root)


async def _resolve_language_and_adapter(
    ctx: MCPContext | None,
    root_str: str,
    language: str | None,
) -> ModelDict | tuple[FrameworkAdapter, LanguageInfo]:
    """Resolve language and adapter; return error dict or (adapter, lang_info)."""
    result = detect_or_use_language(language, root_str)
    if isinstance(result, str):
        await log_client(
            ctx,
            "warning",
            "execute_pre_commit_checks: language detection failed",
            logger_name=__name__,
        )
        return cast(ModelDict, json.loads(result))
    language_info, root_to_use = result
    adapter = _get_adapter(language_info, root_to_use)
    if adapter is None:
        await log_client(
            ctx,
            "warning",
            "execute_pre_commit_checks: unsupported language",
            logger_name=__name__,
        )
        return unsupported_language_result_dict(
            language_info.language, SUPPORTED_LANGUAGES
        )
    return (adapter, language_info)


def _make_test_progress_callback(
    ctx: MCPContext | None, loop: asyncio.AbstractEventLoop
) -> Callable[[int, int], None] | None:
    """Build (completed, total) callback that reports test counts to MCP.

    Reports progress as (tests executed, total tests) so the client sees
    actual test counts. This complements (does not replace) the generic
    time-based progress loop that keeps the connection alive during setup.
    """
    if ctx is None:
        return None

    def report(completed: int, total: int) -> None:
        _ = asyncio.run_coroutine_threadsafe(
            report_progress_safe(ctx, float(completed), float(total)), loop
        )

    return report


async def _run_all_checks_off_loop(
    adapter: FrameworkAdapter,
    language_info: LanguageInfo,
    checks_to_perform: list[PreCommitCheck],
    strict_mode: bool,
    timeout: int | None,
    coverage_threshold: float,
    ctx: MCPContext | None,
) -> tuple[dict[str, CheckResult | TestResult | QualityCheckResult], CheckStats]:
    """Run checks off event loop with optional test progress callback."""
    progress_callback: Callable[[int, int], None] | None = None
    if (
        ctx is not None
        and PreCommitCheck.TESTS in checks_to_perform
        and language_info.language == "python"
    ):
        loop = asyncio.get_running_loop()
        progress_callback = _make_test_progress_callback(ctx, loop)
    return await asyncio.to_thread(
        _execute_all_checks,
        adapter,
        language_info.language,
        checks_to_perform,
        strict_mode,
        timeout,
        coverage_threshold,
        progress_callback,
    )


async def _log_connection_health_before_tests() -> ConnectionHealth | None:
    """Log connection health before test execution (Step 12.7 monitoring)."""
    try:
        health = await check_connection_health()
        logger.info(
            "execute_pre_commit_checks: connection health before tests: %s",
            health.model_dump(),
        )
        return health
    except Exception as e:
        logger.warning(
            "execute_pre_commit_checks: failed to check connection health before tests: %s",
            e,
        )
        return None


async def _log_connection_health_after_tests(
    health_before: ConnectionHealth | None,
) -> None:
    """Log connection health after successful test execution (Step 12.7 monitoring)."""
    try:
        health_after = await check_connection_health()
        logger.info(
            "execute_pre_commit_checks: connection health after tests: %s (health_before=%s)",
            health_after.model_dump(),
            health_before.model_dump() if health_before else None,
        )
    except Exception as e:
        logger.warning(
            "execute_pre_commit_checks: failed to check connection health after tests: %s",
            e,
        )


def _log_test_execution_error(
    error: Exception, health_before: ConnectionHealth | None
) -> None:
    """Log test execution error with connection health context."""
    logger.error(
        "execute_pre_commit_checks: test execution failed: %s (health_before=%s)",
        error,
        health_before,
    )


async def _run_checks_with_connection_monitoring(
    adapter: FrameworkAdapter,
    language_info: LanguageInfo,
    checks_to_perform: list[PreCommitCheck],
    strict_mode: bool,
    timeout: int | None,
    coverage_threshold: float,
    ctx: MCPContext | None,
) -> tuple[dict[str, CheckResult | TestResult | QualityCheckResult], CheckStats]:
    """Run checks with connection stability monitoring for tests (Step 12.7)."""
    health_before: ConnectionHealth | None = (
        await _log_connection_health_before_tests()
        if PreCommitCheck.TESTS in checks_to_perform
        else None
    )
    try:
        return await _run_all_checks_off_loop(
            adapter,
            language_info,
            checks_to_perform,
            strict_mode,
            timeout,
            coverage_threshold,
            ctx,
        )
    except Exception as e:
        if PreCommitCheck.TESTS in checks_to_perform:
            _log_test_execution_error(e, health_before)
        raise
    finally:
        if PreCommitCheck.TESTS in checks_to_perform:
            await _log_connection_health_after_tests(health_before)


async def _execute_pre_commit_checks_impl(
    root: Path,
    language: str | None,
    checks: Sequence[str] | None,
    strict_mode: bool,
    timeout: int | None,
    coverage_threshold: float,
    ctx: MCPContext | None,
) -> ModelDict:
    """Run pre-commit checks and return result dict (FastMCP serializes to JSON)."""
    root_str = str(root)
    resolved = await _resolve_language_and_adapter(ctx, root_str, language)
    if isinstance(resolved, dict):
        return resolved
    adapter, language_info = resolved
    checks_to_perform = determine_checks_to_perform(checks)

    results, stats = await _run_checks_with_connection_monitoring(
        adapter,
        language_info,
        checks_to_perform,
        strict_mode,
        timeout,
        coverage_threshold,
        ctx,
    )

    out = _build_response(results, stats, language_info.language)
    await log_client(
        ctx, "info", "execute_pre_commit_checks: completed", logger_name=__name__
    )
    return out


async def _log_pre_commit_start(
    ctx: MCPContext | None,
    checks: Sequence[PreCommitCheckName],
    test_timeout: int,
    coverage_threshold: float,
    strict_mode: bool,
) -> None:
    """Log start and parameters for execute_pre_commit_checks."""
    await log_client(
        ctx, "info", "execute_pre_commit_checks: starting", logger_name=__name__
    )
    await log_client(
        ctx,
        "info",
        (
            f"execute_pre_commit_checks: checks={list(checks)}, "
            f"test_timeout={test_timeout}, coverage_threshold={coverage_threshold}, "
            f"strict_mode={strict_mode}"
        ),
        logger_name=__name__,
    )


async def _resolve_and_run_pre_commit_impl(
    ctx: MCPContext | None,
    checks: Sequence[PreCommitCheckName],
    strict_mode: bool,
    test_timeout: int,
    coverage_threshold: float,
) -> ModelDict:
    """Resolve project root and run pre-commit checks implementation."""
    root = await get_or_resolve_project_root(ctx)
    return await _execute_pre_commit_checks_impl(
        root, None, checks, strict_mode, test_timeout, coverage_threshold, ctx
    )


async def _run_execute_pre_commit_checks(
    checks: Sequence[PreCommitCheckName],
    test_timeout: int,
    coverage_threshold: float,
    strict_mode: bool,
    ctx: MCPContext | None,
) -> ModelDict:
    """Resolve root, run impl, log and handle errors."""
    await _log_pre_commit_start(
        ctx, checks, test_timeout, coverage_threshold, strict_mode
    )
    try:
        return await _resolve_and_run_pre_commit_impl(
            ctx, checks, strict_mode, test_timeout, coverage_threshold
        )
    except Exception as e:
        await log_client(
            ctx,
            "error",
            f"execute_pre_commit_checks: {e!s}",
            logger_name=__name__,
        )
        return create_error_result_dict(str(e), type(e).__name__)


@mcp.tool(  # pyright: ignore[reportUntypedFunctionDecorator]
    annotations=external_annotations(
        "Execute Pre-Commit Checks",
        read_only=False,
        destructive=False,
        idempotent=False,
    ),  # pyright: ignore[reportCallIssue]
)
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_VERY_COMPLEX)
async def execute_pre_commit_checks(
    checks: Sequence[PreCommitCheckName],
    test_timeout: int,
    coverage_threshold: float,
    strict_mode: bool,
    ctx: MCPContext | None = None,
) -> ModelDict:
    """Execute pre-commit checks with language auto-detection.

    Language is always auto-detected from the project; there is no language
    parameter. USE WHEN: User wants pre-commit checks, user needs quality
    validation, user requests pre-commit validation, user wants to
    check before commit.

    EXAMPLES: 'execute pre-commit checks', 'run quality checks',
    'check formatting and linting', 'run pre-commit validation'.

    RETURNS: JSON with check results, errors found, and pass/fail status.

    Valid values for checks (invalid names are skipped; at least one required):
    - fix_errors: Auto-fix lint/format errors
    - format: Run formatter and fix formatting
    - format_ci_parity: Verify formatter matches CI (script-based)
    - type_check: Run type checker (e.g. pyright)
    - quality: Lint, file size, function length; includes type_check
    - spelling: Check spelling in code files (script-based)
    - test_naming: Enforce test naming conventions (script-based)
    - check_async_tests: Detect unawaited coroutines in test files (script-based)
    - tests: Run test suite with coverage

    All parameters are required. Example: checks=["fix_errors","format"],
    test_timeout=300, coverage_threshold=0.9, strict_mode=False.

    Args:
        checks: List of check names (see valid values above).
        test_timeout: Test run timeout in seconds (e.g. 300). Named to avoid
            conflict with MCP wrapper's timeout parameter.
        coverage_threshold: Minimum coverage 0.0-1.0 (e.g. 0.90).
        strict_mode: Treat warnings as errors.
    Returns:
        Dict with status, language, checks, stats, error (if any); FastMCP serializes.
    Examples:
        See MCP tool descriptor for full JSON examples.
    """
    return await _run_execute_pre_commit_checks(
        checks, test_timeout, coverage_threshold, strict_mode, ctx
    )


def _execute_all_checks(
    adapter: FrameworkAdapter,
    language: str,
    checks_to_perform: list[PreCommitCheck],
    strict_mode: bool,
    timeout: int | None,
    coverage_threshold: float,
    progress_callback: Callable[[int, int], None] | None = None,
) -> tuple[dict[str, CheckResult | TestResult | QualityCheckResult], CheckStats]:
    """Execute all requested checks."""
    results: dict[str, CheckResult | TestResult | QualityCheckResult] = {}
    stats = CheckStats(
        total_errors=0,
        total_warnings=0,
        files_modified=[],
        checks_performed=[],
    )
    run_checks_pipeline(
        adapter,
        language,
        checks_to_perform,
        strict_mode,
        timeout,
        coverage_threshold,
        progress_callback,
        results,
        stats,
    )
    return results, stats


def _build_response(
    results: dict[str, CheckResult | TestResult | QualityCheckResult],
    stats: CheckStats,
    detected_language: str,
) -> ModelDict:
    """Build response dict (FastMCP serializes to JSON; avoids double-encoding)."""
    total_errors = stats.total_errors
    success = total_errors == 0
    response = PreCommitResult(
        status=OperationStatus.SUCCESS if success else OperationStatus.ERROR,
        language=detected_language,
        checks_performed=stats.checks_performed,
        results=results,
        total_errors=total_errors,
        total_warnings=stats.total_warnings,
        files_modified=list(set(stats.files_modified)),
        success=success,
    )
    data = response.model_dump(mode="json")
    compact = truncate_large_logs_in_data(data)
    return ensure_json_serializable_for_mcp(cast(ModelDict, compact))


class FixQualityResult(BaseModel):
    """Result of fix_quality_issues operation."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    status: OperationStatus = Field(description="Operation status")
    errors_fixed: int = Field(ge=0, description="Number of errors fixed")
    warnings_fixed: int = Field(ge=0, description="Number of warnings fixed")
    formatting_issues_fixed: int = Field(
        ge=0, description="Number of formatting issues fixed"
    )
    markdown_issues_fixed: int = Field(
        ge=0, description="Number of markdown issues fixed"
    )
    type_errors_fixed: int = Field(ge=0, description="Number of type errors fixed")
    files_modified: list[str] = Field(
        default_factory=list, description="List of modified files"
    )
    remaining_issues: list[str] = Field(
        default_factory=list, description="List of remaining issues"
    )
    error_message: str | None = Field(default=None, description="Error message if any")


def _create_quality_error_response(error_message: str) -> str:
    """Create error response for quality fixes."""
    from cortex.tools.tool_error_formatters import format_tool_error

    return format_tool_error(
        Exception(error_message),
        suggestion=(
            "Review the error details. Ensure the project root is valid and "
            "quality tools (ruff, black, etc.) are available. Check file permissions."
        ),
        example={
            "include_untracked_markdown": True,
        },
        context={"error_message": error_message},
    )


async def _run_quality_checks(root_str: str) -> ModelDict | str:
    """Run quality checks and return result or error response."""
    fix_errors_result = await execute_pre_commit_checks(
        checks=[
            PreCommitCheck.FIX_ERRORS.value,
            PreCommitCheck.FORMAT.value,
            PreCommitCheck.TYPE_CHECK.value,
        ],
        test_timeout=300,
        coverage_threshold=0.90,
        strict_mode=False,
    )

    # `execute_pre_commit_checks()` uses `"status": "error"` both for:
    # - genuine tool failures (exception paths), which include `error`/`error_type`
    # - "checks ran, but errors remain" (normal outcome for this fixer)
    #
    # Only treat it as a tool failure if it contains the explicit error payload.
    if fix_errors_result.get("status") == "error" and (
        "error" in fix_errors_result or "error_type" in fix_errors_result
    ):
        error_obj = fix_errors_result.get("error")
        return _create_quality_error_response(
            str(error_obj) if error_obj is not None else "Unknown error"
        )

    return fix_errors_result


async def _fix_markdown_and_update_files(
    root_str: str, include_untracked_markdown: bool, files_modified: list[str]
) -> int:
    """Fix markdown lint errors and update files_modified list."""
    markdown_result_json = await fix_markdown_lint(
        include_untracked_markdown=include_untracked_markdown,
        dry_run=False,
    )
    markdown_result_raw: JsonValue = json.loads(markdown_result_json)
    # Recursive JsonValue narrows incorrectly in pyright/basedpyright
    if not isinstance(
        markdown_result_raw, dict
    ):  # pyright: ignore[reportUnnecessaryIsInstance]
        return 0
    markdown_result = cast(ModelDict, markdown_result_raw)
    return _process_markdown_results(markdown_result, files_modified)


def _extract_fix_statistics(
    fix_errors_result: dict[str, JsonValue],
) -> tuple[int, int, int, int, list[str]]:
    """Extract statistics from fix_errors result."""
    results_obj = fix_errors_result.get("results", {})
    results = extract_dict_from_object(results_obj, {})
    fix_errors_check, format_check, type_check_result = extract_check_results(results)

    errors = extract_list_from_object(fix_errors_check.get("errors", []), [])
    warnings = extract_list_from_object(fix_errors_check.get("warnings", []), [])
    errors_fixed = len(errors)
    warnings_fixed = len(warnings)
    formatting_issues_fixed = extract_int_from_object(
        format_check.get("files_formatted", 0), 0
    )
    type_errors = extract_list_from_object(type_check_result.get("errors", []), [])
    type_errors_fixed = len(type_errors)
    files_modified_list = extract_list_from_object(
        fix_errors_result.get("files_modified", []), []
    )
    files_modified = list(set(files_modified_list))

    return (
        errors_fixed,
        warnings_fixed,
        formatting_issues_fixed,
        type_errors_fixed,
        files_modified,
    )


def _process_markdown_results(
    markdown_result: ModelDict, files_modified: list[str]
) -> int:
    """Process markdown fix results and update files_modified list."""
    markdown_issues_fixed = 0
    success_obj = markdown_result.get("success")
    if success_obj:
        files_fixed_obj = markdown_result.get("files_fixed", 0)
        # Recursive JsonValue narrows incorrectly in pyright/basedpyright
        markdown_issues_fixed = (
            int(files_fixed_obj)
            if isinstance(files_fixed_obj, (int, str))
            else 0  # pyright: ignore[reportUnnecessaryIsInstance]
        )
        results_obj = markdown_result.get("results", [])
        if isinstance(
            results_obj, list
        ):  # pyright: ignore[reportUnnecessaryIsInstance]
            for item in cast(list[JsonValue], results_obj):
                if isinstance(
                    item, dict
                ):  # pyright: ignore[reportUnnecessaryIsInstance]
                    file_result = cast(ModelDict, item)
                    fixed_obj = file_result.get("fixed")
                    if fixed_obj:
                        file_path_obj = file_result.get("file", "")
                        file_path = str(file_path_obj) if file_path_obj else ""
                        if file_path and file_path not in files_modified:
                            files_modified.append(file_path)
    return markdown_issues_fixed


def _build_quality_response(
    errors_fixed: int,
    warnings_fixed: int,
    formatting_issues_fixed: int,
    markdown_issues_fixed: int,
    type_errors_fixed: int,
    files_modified: list[str],
    remaining_issues: list[str],
) -> FixQualityResult:
    """Build quality fix response."""
    return FixQualityResult(
        status=OperationStatus.SUCCESS,
        errors_fixed=errors_fixed,
        warnings_fixed=warnings_fixed,
        formatting_issues_fixed=formatting_issues_fixed,
        markdown_issues_fixed=markdown_issues_fixed,
        type_errors_fixed=type_errors_fixed,
        files_modified=files_modified,
        remaining_issues=remaining_issues,
        error_message=None,
    )


def _build_quality_response_json(
    errors_fixed: int,
    warnings_fixed: int,
    formatting_issues_fixed: int,
    markdown_issues_fixed: int,
    type_errors_fixed: int,
    files_modified: list[str],
    remaining_issues: list[str],
) -> str:
    """Build quality fix response as JSON string."""
    response = _build_quality_response(
        errors_fixed,
        warnings_fixed,
        formatting_issues_fixed,
        markdown_issues_fixed,
        type_errors_fixed,
        files_modified,
        remaining_issues,
    )
    data = response.model_dump(mode="json")
    compact = truncate_large_logs_in_data(data)
    return json.dumps(compact, separators=(",", ":"))


def _build_markdown_fix_output(
    fix_errors_result: ModelDict,
    markdown_issues_fixed: int,
    files_modified: list[str],
) -> str:
    """Build final quality response JSON from fix result and markdown stats."""
    remaining_issues = collect_remaining_issues(fix_errors_result)
    (
        errors_fixed,
        warnings_fixed,
        formatting_issues_fixed,
        type_errors_fixed,
        _,
    ) = _extract_fix_statistics(fix_errors_result)
    return _build_quality_response_json(
        errors_fixed,
        warnings_fixed,
        formatting_issues_fixed,
        markdown_issues_fixed,
        type_errors_fixed,
        files_modified,
        remaining_issues,
    )


async def _run_markdown_fixes_and_build_json(
    fix_errors_result: ModelDict,
    root_str: str,
    include_untracked_markdown: bool,
    files_modified: list[str],
    ctx: MCPContext | None,
) -> str:
    """Run markdown fixes and build final quality response JSON."""
    markdown_issues_fixed = await _fix_markdown_and_update_files(
        root_str, include_untracked_markdown, files_modified
    )
    await report_progress_safe(ctx, 90.0, 100.0)
    await log_client(
        ctx, "info", "fix_quality_issues: Finalizing results...", logger_name=__name__
    )
    out = _build_markdown_fix_output(
        fix_errors_result, markdown_issues_fixed, files_modified
    )
    await report_progress_safe(ctx, 100.0, 100.0)
    return out


async def _run_quality_fixes_and_build_response(
    root_str: str,
    include_untracked_markdown: bool,
    ctx: MCPContext | None = None,
) -> tuple[bool, str]:
    """Run fix_errors + markdown fixes; return (success, json_string)."""
    await log_client(
        ctx,
        "info",
        "fix_quality_issues: Running fix_errors, format, and type_check...",
        logger_name=__name__,
    )
    await report_progress_safe(ctx, 10.0, 100.0)
    fix_errors_result = await _run_quality_checks(root_str)
    if isinstance(fix_errors_result, str):
        return (False, fix_errors_result)
    (_, _, _, _, files_modified) = _extract_fix_statistics(fix_errors_result)
    await log_client(
        ctx,
        "info",
        "fix_quality_issues: Code checks complete. Fixing markdown lint...",
        logger_name=__name__,
    )
    await report_progress_safe(ctx, 50.0, 100.0)
    out = await _run_markdown_fixes_and_build_json(
        fix_errors_result, root_str, include_untracked_markdown, files_modified, ctx
    )
    return (True, out)


async def _fix_quality_issues_impl(
    root: Path,
    include_untracked_markdown: bool,
    ctx: MCPContext | None,
) -> str:
    """Run quality fixes and return JSON result."""
    root_str = str(root)
    success, out = await _run_quality_fixes_and_build_response(
        root_str, include_untracked_markdown, ctx
    )
    if not success:
        await log_client(
            ctx,
            "warning",
            "fix_quality_issues: quality checks returned error",
            logger_name=__name__,
        )
    else:
        await log_client(
            ctx, "info", "fix_quality_issues: completed", logger_name=__name__
        )
    return out


@mcp.tool(  # pyright: ignore[reportUntypedFunctionDecorator]
    annotations=safe_write_annotations(
        "Fix Code Quality Issues",
        open_world=True,
    ),  # pyright: ignore[reportCallIssue]
)
@ensure_usage_context
@mcp_tool_wrapper(
    timeout=MCP_TOOL_TIMEOUT_VERY_COMPLEX,
    enable_progress=True,
)
async def fix_quality_issues(
    include_untracked_markdown: bool = True,
    ctx: MCPContext | None = None,
) -> str:
    """Automatically fix code quality issues on-the-go.

    USE WHEN: User wants auto-fix, user needs quality fixes, user
    requests automatic fixes, user wants to fix code quality.

    EXAMPLES: 'fix quality issues', 'auto-fix formatting', 'fix
    linting errors', 'fix markdown issues'.

    RETURNS: JSON with fixes applied, files modified, and remaining
    issues.

    This tool runs comprehensive quality fixes across the codebase:
    1. Auto-fixes linting errors (ruff, etc.)
    2. Formats all code files (black, isort, etc.)
    3. Runs type checking (pyright, etc.) and reports type errors
    4. Fixes markdown lint errors across all markdown files

    NOTE: This can take several minutes on large codebases (typically
    2-5 minutes) as it processes the entire codebase. Progress is reported
    during execution. It does NOT run tests (tests are reserved for the
    commit pipeline).

    Call after code changes, when IDE reports errors, or before new work.

    Args:
        include_untracked_markdown: Include untracked markdown (default True).
    Returns:
        JSON with status, *_fixed counts, files_modified, remaining_issues.
    Examples:
        See MCP tool descriptor for full JSON examples.
    """
    await log_client(ctx, "info", "fix_quality_issues: starting", logger_name=__name__)
    try:
        root = await get_or_resolve_project_root(ctx)
        return await _fix_quality_issues_impl(root, include_untracked_markdown, ctx)
    except Exception as e:
        await log_client(
            ctx, "error", f"fix_quality_issues: {e!s}", logger_name=__name__
        )
        return _create_quality_error_response(str(e))
