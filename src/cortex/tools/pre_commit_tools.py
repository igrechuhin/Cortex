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
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.constants import (
    MAX_FILE_LINES,
    MAX_FUNCTION_LINES,
    MCP_TOOL_TIMEOUT_VERY_COMPLEX,
)
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_stability import ensure_usage_context, mcp_tool_wrapper
from cortex.core.models import JsonValue, ModelDict
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
    FileSizeViolation,
    FunctionLengthViolation,
    PreCommitCheck,
    PreCommitResult,
    QualityCheckResult,
    check_file_sizes,
    check_function_lengths_in_file,
    collect_remaining_issues,
    create_error_result_dict,
    detect_or_use_language,
    determine_checks_to_perform,
    ensure_json_serializable_for_mcp,
    extract_check_results,
    extract_dict_from_object,
    extract_int_from_object,
    extract_list_from_object,
    get_project_root_str,
    truncate_large_logs_in_data,
    unsupported_language_result_dict,
)
from cortex.tools.pre_commit_synapse import run_synapse_script

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
    language_info = detect_or_use_language(language, root_str)
    if isinstance(language_info, str):
        await log_client(
            ctx,
            "warning",
            "execute_pre_commit_checks: language detection failed",
            logger_name=__name__,
        )
        return cast(ModelDict, json.loads(language_info))
    adapter = _get_adapter(language_info, root_str)
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


async def _execute_pre_commit_checks_impl(
    project_root: str | None,
    language: str | None,
    checks: Sequence[str] | None,
    strict_mode: bool,
    timeout: int | None,
    coverage_threshold: float,
    ctx: MCPContext | None,
) -> ModelDict:
    """Run pre-commit checks and return result dict (FastMCP serializes to JSON)."""
    root_str = get_project_root_str(project_root)
    resolved = await _resolve_language_and_adapter(ctx, root_str, language)
    if isinstance(resolved, dict):
        return resolved
    adapter, language_info = resolved
    checks_to_perform = determine_checks_to_perform(checks)
    results, stats = await asyncio.to_thread(
        _execute_all_checks,
        adapter,
        language_info.language,
        checks_to_perform,
        strict_mode,
        timeout,
        coverage_threshold,
    )
    out = _build_response(results, stats, language_info.language)
    await log_client(
        ctx, "info", "execute_pre_commit_checks: completed", logger_name=__name__
    )
    return out


@mcp.tool()
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_VERY_COMPLEX)
async def execute_pre_commit_checks(
    checks: Sequence[str] | None = None,
    language: str | None = None,
    project_root: str | None = None,
    timeout: int | None = None,
    coverage_threshold: float = 0.90,
    strict_mode: bool = False,
    ctx: MCPContext | None = None,
) -> ModelDict:
    """Execute pre-commit checks with language auto-detection.

    USE WHEN: User wants pre-commit checks, user needs quality
    validation, user requests pre-commit validation, user wants to
    check before commit.

    EXAMPLES: 'execute pre-commit checks', 'run quality checks',
    'check formatting and linting', 'run pre-commit validation'.

    RETURNS: JSON with check results, errors found, and pass/fail status.

    Args:
        checks: List of checks (fix_errors, format, type_check, quality, tests).
        language: Project language or None to auto-detect.
        project_root: Project root path or None.
        timeout: Test timeout in seconds or None.
        coverage_threshold: Minimum coverage 0.0-1.0 (default 0.90).
        strict_mode: Treat warnings as errors (default False).
    Returns:
        Dict with status, language, checks, stats, error (if any); FastMCP serializes.
    Examples:
        See MCP tool descriptor for full JSON examples.
    """
    await log_client(
        ctx, "info", "execute_pre_commit_checks: starting", logger_name=__name__
    )
    try:
        return await _execute_pre_commit_checks_impl(
            project_root,
            language,
            checks,
            strict_mode,
            timeout,
            coverage_threshold,
            ctx,
        )
    except Exception as e:
        await log_client(
            ctx,
            "error",
            f"execute_pre_commit_checks: {e!s}",
            logger_name=__name__,
        )
        return create_error_result_dict(str(e), type(e).__name__)


def _execute_all_checks(
    adapter: FrameworkAdapter,
    language: str,
    checks_to_perform: list[PreCommitCheck],
    strict_mode: bool,
    timeout: int | None,
    coverage_threshold: float,
) -> tuple[dict[str, CheckResult | TestResult | QualityCheckResult], CheckStats]:
    """Execute all requested checks."""
    results: dict[str, CheckResult | TestResult | QualityCheckResult] = {}
    stats = CheckStats(
        total_errors=0,
        total_warnings=0,
        files_modified=[],
        checks_performed=[],
    )

    _process_fix_errors_check(adapter, checks_to_perform, strict_mode, results, stats)
    _process_quality_check(adapter, language, checks_to_perform, results, stats)
    _process_format_check(adapter, checks_to_perform, results, stats)
    _process_format_ci_parity_check(
        adapter, language, checks_to_perform, results, stats
    )
    _process_type_check(adapter, checks_to_perform, results, stats)
    _process_test_naming_check(adapter, language, checks_to_perform, results, stats)
    _process_tests_check(
        adapter, checks_to_perform, timeout, coverage_threshold, results, stats
    )

    return results, stats


def _process_fix_errors_check(
    adapter: FrameworkAdapter,
    checks_to_perform: list[PreCommitCheck],
    strict_mode: bool,
    results: dict[str, CheckResult | TestResult | QualityCheckResult],
    stats: CheckStats,
) -> None:
    """Process fix_errors check if requested."""
    if PreCommitCheck.FIX_ERRORS in checks_to_perform:
        fix_result = _execute_fix_errors(adapter, strict_mode)
        results[PreCommitCheck.FIX_ERRORS.value] = fix_result
        stats.checks_performed.append(PreCommitCheck.FIX_ERRORS.value)
        stats.total_errors += len(fix_result.errors)
        stats.total_warnings += len(fix_result.warnings)
        stats.files_modified.extend(fix_result.files_modified)


def _process_format_check(
    adapter: FrameworkAdapter,
    checks_to_perform: list[PreCommitCheck],
    results: dict[str, CheckResult | TestResult | QualityCheckResult],
    stats: CheckStats,
) -> None:
    """Process format check if requested."""
    if PreCommitCheck.FORMAT in checks_to_perform:
        format_result = adapter.format_code()
        results[PreCommitCheck.FORMAT.value] = format_result
        stats.checks_performed.append(PreCommitCheck.FORMAT.value)
        stats.total_errors += len(format_result.errors)
        stats.files_modified.extend(format_result.files_modified)


def _process_format_ci_parity_check(
    adapter: FrameworkAdapter,
    language: str,
    checks_to_perform: list[PreCommitCheck],
    results: dict[str, CheckResult | TestResult | QualityCheckResult],
    stats: CheckStats,
) -> None:
    """Process format_ci_parity check if requested (runs synapse script)."""
    if PreCommitCheck.FORMAT_CI_PARITY not in checks_to_perform:
        return
    project_root = Path(adapter.project_root)
    result = run_synapse_script(
        project_root,
        language,
        "check_formatting_ci_parity.py",
        PreCommitCheck.FORMAT_CI_PARITY.value,
    )
    results[PreCommitCheck.FORMAT_CI_PARITY.value] = result
    stats.checks_performed.append(PreCommitCheck.FORMAT_CI_PARITY.value)
    stats.total_errors += len(result.errors)


def _process_test_naming_check(
    adapter: FrameworkAdapter,
    language: str,
    checks_to_perform: list[PreCommitCheck],
    results: dict[str, CheckResult | TestResult | QualityCheckResult],
    stats: CheckStats,
) -> None:
    """Process test_naming check if requested (runs synapse script)."""
    if PreCommitCheck.TEST_NAMING not in checks_to_perform:
        return
    project_root = Path(adapter.project_root)
    result = run_synapse_script(
        project_root,
        language,
        "check_test_naming.py",
        PreCommitCheck.TEST_NAMING.value,
    )
    results[PreCommitCheck.TEST_NAMING.value] = result
    stats.checks_performed.append(PreCommitCheck.TEST_NAMING.value)
    stats.total_errors += len(result.errors)


def _process_type_check(
    adapter: FrameworkAdapter,
    checks_to_perform: list[PreCommitCheck],
    results: dict[str, CheckResult | TestResult | QualityCheckResult],
    stats: CheckStats,
) -> None:
    """Process type_check check if requested."""
    if PreCommitCheck.TYPE_CHECK in checks_to_perform:
        type_result = adapter.type_check()
        results[PreCommitCheck.TYPE_CHECK.value] = type_result
        stats.checks_performed.append(PreCommitCheck.TYPE_CHECK.value)
        stats.total_errors += len(type_result.errors)


def _process_quality_check(
    adapter: FrameworkAdapter,
    language: str,
    checks_to_perform: list[PreCommitCheck],
    results: dict[str, CheckResult | TestResult | QualityCheckResult],
    stats: CheckStats,
) -> None:
    """Process quality check if requested."""
    if PreCommitCheck.QUALITY in checks_to_perform:
        quality_result = _execute_quality(adapter, language)
        results[PreCommitCheck.QUALITY.value] = quality_result
        stats.checks_performed.append(PreCommitCheck.QUALITY.value)
        stats.total_errors += len(quality_result.errors)


def _process_tests_check(
    adapter: FrameworkAdapter,
    checks_to_perform: list[PreCommitCheck],
    timeout: int | None,
    coverage_threshold: float,
    results: dict[str, CheckResult | TestResult | QualityCheckResult],
    stats: CheckStats,
) -> None:
    """Process tests check if requested."""
    if PreCommitCheck.TESTS in checks_to_perform:
        test_result = _execute_tests(adapter, timeout, coverage_threshold)
        results[PreCommitCheck.TESTS.value] = test_result
        stats.checks_performed.append(PreCommitCheck.TESTS.value)
        if not test_result.success:
            stats.total_errors += len(test_result.errors)


def _execute_fix_errors(
    adapter: FrameworkAdapter,
    strict_mode: bool,
) -> CheckResult:
    """Execute fix_errors check."""
    return adapter.fix_errors(
        error_types=None,
        auto_fix=True,
        strict_mode=strict_mode,
    )


def _check_function_lengths(project_root: Path) -> list[FunctionLengthViolation]:
    """Check all Python files for function length violations."""
    violations: list[FunctionLengthViolation] = []
    src_dir = project_root / "src"

    if not src_dir.exists():
        return violations

    for py_file in src_dir.glob("**/*.py"):
        if "__pycache__" in str(py_file) or py_file.name.startswith("test_"):
            continue
        file_violations = check_function_lengths_in_file(py_file)
        for func_name, logical_lines, start_line in file_violations:
            try:
                relative_path = str(py_file.relative_to(project_root))
            except ValueError:
                relative_path = str(py_file)
            violations.append(
                FunctionLengthViolation(
                    file=relative_path,
                    function=func_name,
                    line=start_line,
                    lines=logical_lines,
                    max_lines=MAX_FUNCTION_LINES,
                    excess=logical_lines - MAX_FUNCTION_LINES,
                )
            )

    return violations


def _build_quality_errors(
    lint_errors: list[str],
    file_violations: list[FileSizeViolation],
    func_violations: list[FunctionLengthViolation],
) -> list[str]:
    """Build error messages for quality check."""
    errors = list(lint_errors)
    for v in file_violations:
        msg = f"File size violation: {v.file} has {v.lines} lines "
        msg += f"(max: {v.max_lines}, excess: {v.excess})"
        errors.append(msg)
    for v in func_violations:
        msg = f"Function length violation: {v.file}:{v.function}() at line "
        msg += f"{v.line} has {v.lines} lines "
        msg += f"(max: {v.max_lines}, excess: {v.excess})"
        errors.append(msg)
    return errors


def _build_quality_output(
    lint_output: str,
    file_violations: list[FileSizeViolation],
    func_violations: list[FunctionLengthViolation],
) -> str:
    """Build output message for quality check."""
    parts = [lint_output]
    if file_violations:
        parts.append(
            f"\nFile size violations: {len(file_violations)} file(s) "
            + f"exceed {MAX_FILE_LINES} lines"
        )
    if func_violations:
        parts.append(
            f"\nFunction length violations: {len(func_violations)} "
            + f"function(s) exceed {MAX_FUNCTION_LINES} lines"
        )
    return "\n".join(parts)


def _execute_quality(adapter: FrameworkAdapter, language: str) -> QualityCheckResult:
    """Execute quality check: linting; for Python only, file sizes and function lengths."""
    lint_result = adapter.lint_code()
    project_root = adapter.project_root
    file_violations: list[FileSizeViolation] = []
    func_violations: list[FunctionLengthViolation] = []
    if language == "python":
        file_violations = check_file_sizes(project_root)
        func_violations = _check_function_lengths(project_root)

    errors = _build_quality_errors(lint_result.errors, file_violations, func_violations)
    output = _build_quality_output(lint_result.output, file_violations, func_violations)
    success = (
        lint_result.success and len(file_violations) == 0 and len(func_violations) == 0
    )

    return QualityCheckResult(
        check_type="quality",
        success=success,
        output=output,
        errors=errors,
        warnings=list(lint_result.warnings),
        files_modified=list(lint_result.files_modified),
        file_size_violations=file_violations,
        function_length_violations=func_violations,
    )


def _execute_tests(
    adapter: FrameworkAdapter,
    timeout: int | None,
    coverage_threshold: float,
) -> TestResult:
    """Execute tests check."""
    return adapter.run_tests(
        timeout=timeout,
        coverage_threshold=coverage_threshold,
        max_failures=None,
    )


def _build_response(
    results: dict[str, CheckResult | TestResult | QualityCheckResult],
    stats: CheckStats,
    detected_language: str,
) -> ModelDict:
    """Build response dict (FastMCP serializes to JSON; avoids double-encoding)."""
    total_errors = stats.total_errors
    success = total_errors == 0
    response = PreCommitResult(
        status="success" if success else "error",
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

    status: Literal["success", "error"] = Field(description="Operation status")
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
    result = FixQualityResult(
        status="error",
        errors_fixed=0,
        warnings_fixed=0,
        formatting_issues_fixed=0,
        markdown_issues_fixed=0,
        type_errors_fixed=0,
        files_modified=[],
        remaining_issues=[],
        error_message=error_message,
    )
    data = result.model_dump(mode="json")
    compact = truncate_large_logs_in_data(data)
    return json.dumps(compact, separators=(",", ":"))


async def _run_quality_checks(root_str: str) -> ModelDict | str:
    """Run quality checks and return result or error response."""
    fix_errors_result = await execute_pre_commit_checks(
        checks=[
            PreCommitCheck.FIX_ERRORS.value,
            PreCommitCheck.FORMAT.value,
            PreCommitCheck.TYPE_CHECK.value,
        ],
        project_root=root_str,
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
        project_root=root_str,
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
        status="success",
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


async def _run_quality_fixes_and_build_response(
    root_str: str,
    include_untracked_markdown: bool,
) -> tuple[bool, str]:
    """Run fix_errors + markdown fixes; return (success, json_string)."""
    fix_errors_result = await _run_quality_checks(root_str)
    if isinstance(fix_errors_result, str):
        return (False, fix_errors_result)
    (
        errors_fixed,
        warnings_fixed,
        formatting_issues_fixed,
        type_errors_fixed,
        files_modified,
    ) = _extract_fix_statistics(fix_errors_result)
    markdown_issues_fixed = await _fix_markdown_and_update_files(
        root_str, include_untracked_markdown, files_modified
    )
    remaining_issues = collect_remaining_issues(fix_errors_result)
    out = _build_quality_response_json(
        errors_fixed,
        warnings_fixed,
        formatting_issues_fixed,
        markdown_issues_fixed,
        type_errors_fixed,
        files_modified,
        remaining_issues,
    )
    return (True, out)


async def _fix_quality_issues_impl(
    project_root: str | None,
    include_untracked_markdown: bool,
    ctx: MCPContext | None,
) -> str:
    """Run quality fixes and return JSON result."""
    root_str = get_project_root_str(project_root)
    success, out = await _run_quality_fixes_and_build_response(
        root_str, include_untracked_markdown
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


@mcp.tool()
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_VERY_COMPLEX)
async def fix_quality_issues(
    project_root: str | None = None,
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

    This tool provides lightweight, automatic quality fixes to prevent
    error accumulation. It fixes type errors, formatting issues, linting
    errors, and markdown lint errors, but does NOT run tests (tests are
    reserved for the commit pipeline).

    Call after code changes, when IDE reports errors, or before new work.

    Args:
        project_root: Project root or None.
        include_untracked_markdown: Include untracked markdown (default True).
    Returns:
        JSON with status, *_fixed counts, files_modified, remaining_issues.
    Examples:
        See MCP tool descriptor for full JSON examples.
    """
    await log_client(ctx, "info", "fix_quality_issues: starting", logger_name=__name__)
    try:
        return await _fix_quality_issues_impl(
            project_root, include_untracked_markdown, ctx
        )
    except Exception as e:
        await log_client(
            ctx, "error", f"fix_quality_issues: {e!s}", logger_name=__name__
        )
        return _create_quality_error_response(str(e))
