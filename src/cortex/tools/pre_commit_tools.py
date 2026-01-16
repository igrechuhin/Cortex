"""Pre-Commit Tools

MCP tools for executing pre-commit checks with language auto-detection.

Total: 2 tools
- execute_pre_commit_checks: Execute pre-commit checks (fix errors, format, type check, quality, tests)
- fix_quality_issues: Automatically fix quality issues on-the-go (fix errors, format, type check, markdown lint)
"""

import json
from collections.abc import Sequence
from typing import Literal, TypedDict, cast

from cortex.managers.initialization import get_project_root
from cortex.server import mcp
from cortex.services.framework_adapters.base import CheckResult, TestResult
from cortex.services.framework_adapters.python_adapter import PythonAdapter
from cortex.services.language_detector import LanguageDetector, LanguageInfo

# Import markdown operations for markdown lint fixing
# No circular import: markdown_operations doesn't import pre_commit_tools
from cortex.tools.markdown_operations import fix_markdown_lint  # noqa: F401


class PreCommitResult(TypedDict):
    """Result of pre-commit checks execution."""

    status: Literal["success", "error"]
    language: str | None
    checks_performed: list[str]
    results: dict[str, CheckResult | TestResult]
    total_errors: int
    total_warnings: int
    files_modified: list[str]
    success: bool


class CheckStats(TypedDict):
    """Statistics for pre-commit checks."""

    total_errors: int
    total_warnings: int
    files_modified: list[str]
    checks_performed: list[str]


def _get_adapter(
    language_info: LanguageInfo, project_root: str | None
) -> PythonAdapter | None:
    """Get framework adapter for detected language.

    Args:
        language_info: Detected language information.
        project_root: Project root directory.

    Returns:
        Framework adapter instance or None if not supported.
    """
    if language_info["language"] == "python":
        return PythonAdapter(project_root)
    # TODO: Add other language adapters as needed
    return None


def _create_error_result(error: str, error_type: str = "ValueError") -> str:
    """Create error response JSON."""
    return json.dumps(
        {"status": "error", "error": error, "error_type": error_type},
        indent=2,
    )


@mcp.tool()
async def execute_pre_commit_checks(
    checks: Sequence[str] | None = None,
    language: str | None = None,
    project_root: str | None = None,
    timeout: int | None = None,
    coverage_threshold: float = 0.90,
    strict_mode: bool = False,
) -> str:
    """Execute pre-commit checks with language auto-detection.

    Args:
        checks: List of checks to perform. Options: "fix_errors", "format", "type_check",
            "quality", "tests". If None, performs all checks.
        language: Project language (python, typescript, javascript, rust, go).
            If None, auto-detects from project structure.
        project_root: Path to project root directory. If None, uses current directory.
        timeout: Maximum time in seconds for test execution. If None, no timeout.
        coverage_threshold: Minimum test coverage percentage required (0.0-1.0).
            Default: 0.90 (90%).
        strict_mode: Whether to treat warnings as errors. Default: False.

    Returns:
        JSON string with pre-commit check results containing:
        - status: "success" or "error"
        - language: Detected or specified language
        - checks: Dictionary of check results (fix_errors, format, type_check, quality, tests)
        - stats: Summary statistics (total_errors, total_warnings, files_modified)
        - error: Error message (only if status is "error")

    Examples:
        Example 1: Run all checks with auto-detection
        >>> await execute_pre_commit_checks()
        {
          "status": "success",
          "language": "python",
          "checks": {
            "fix_errors": {
              "status": "passed",
              "errors": 0,
              "warnings": 2,
              "message": "All errors fixed"
            },
            "format": {
              "status": "passed",
              "files_formatted": 3,
              "message": "Code formatted successfully"
            },
            "type_check": {
              "status": "passed",
              "errors": 0,
              "message": "Type checking passed"
            },
            "quality": {
              "status": "passed",
              "score": 9.5,
              "message": "Code quality excellent"
            },
            "tests": {
              "status": "passed",
              "tests_run": 1520,
              "tests_passed": 1520,
              "coverage": 0.92,
              "message": "All tests passed"
            }
          },
          "stats": {
            "total_errors": 0,
            "total_warnings": 2,
            "files_modified": ["src/file1.py"],
            "checks_performed": ["fix_errors", "format", "type_check", "quality", "tests"]
          }
        }

        Example 2: Run specific checks with strict mode
        >>> await execute_pre_commit_checks(
        ...     checks=["format", "type_check"],
        ...     strict_mode=True
        ... )
        {
          "status": "success",
          "language": "python",
          "checks": {
            "format": {
              "status": "passed",
              "files_formatted": 0,
              "message": "Code already formatted"
            },
            "type_check": {
              "status": "passed",
              "errors": 0,
              "message": "Type checking passed"
            }
          },
          "stats": {
            "total_errors": 0,
            "total_warnings": 0,
            "files_modified": [],
            "checks_performed": ["format", "type_check"]
          }
        }

        Example 3: Run with custom coverage threshold
        >>> await execute_pre_commit_checks(
        ...     checks=["tests"],
        ...     coverage_threshold=0.95,
        ...     timeout=60
        ... )
        {
          "status": "success",
          "language": "python",
          "checks": {
            "tests": {
              "status": "passed",
              "tests_run": 1520,
              "tests_passed": 1520,
              "coverage": 0.96,
              "message": "All tests passed, coverage above threshold"
            }
          },
          "stats": {
            "total_errors": 0,
            "total_warnings": 0,
            "files_modified": [],
            "checks_performed": ["tests"]
          }
        }
    """
    try:
        root_str = _get_project_root_str(project_root)
        language_info = _detect_or_use_language(language, root_str)
        if isinstance(language_info, str):
            return language_info

        adapter = _get_adapter(language_info, root_str)
        if adapter is None:
            return _create_error_result(
                f"Language '{language_info['language']}' is not yet supported. "
                + "Supported languages: python"
            )

        checks_to_perform = _determine_checks_to_perform(checks)
        results, stats = _execute_all_checks(
            adapter, checks_to_perform, strict_mode, timeout, coverage_threshold
        )

        return _build_response(results, stats, language_info["language"])

    except Exception as e:
        return _create_error_result(str(e), type(e).__name__)


def _get_project_root_str(project_root: str | None) -> str:
    """Get project root as string."""
    root = get_project_root(project_root)
    return str(root)


def _detect_or_use_language(language: str | None, root_str: str) -> LanguageInfo | str:
    """Detect language or use provided language."""
    if language is None:
        detector = LanguageDetector(root_str)
        language_info = detector.detect_language()
        if language_info is None:
            return _create_error_result(
                "Could not detect project language. Please specify language parameter."
            )
        return language_info
    else:
        detected_language = language.lower()
        return LanguageInfo(
            language=detected_language,
            test_framework=None,
            formatter=None,
            linter=None,
            type_checker=None,
            build_tool=None,
            confidence=0.5,
        )


def _determine_checks_to_perform(checks: Sequence[str] | None) -> list[str]:
    """Determine which checks to perform."""
    default_checks = ["fix_errors", "format", "type_check", "quality", "tests"]
    return list(checks) if checks else default_checks


def _execute_all_checks(
    adapter: PythonAdapter,
    checks_to_perform: list[str],
    strict_mode: bool,
    timeout: int | None,
    coverage_threshold: float,
) -> tuple[dict[str, CheckResult | TestResult], CheckStats]:
    """Execute all requested checks."""
    results: dict[str, CheckResult | TestResult] = {}
    stats: CheckStats = {
        "total_errors": 0,
        "total_warnings": 0,
        "files_modified": [],
        "checks_performed": [],
    }

    _process_fix_errors_check(adapter, checks_to_perform, strict_mode, results, stats)
    _process_format_check(adapter, checks_to_perform, results, stats)
    _process_type_check(adapter, checks_to_perform, results, stats)
    _process_quality_check(adapter, checks_to_perform, results, stats)
    _process_tests_check(
        adapter, checks_to_perform, timeout, coverage_threshold, results, stats
    )

    return results, stats


def _process_fix_errors_check(
    adapter: PythonAdapter,
    checks_to_perform: list[str],
    strict_mode: bool,
    results: dict[str, CheckResult | TestResult],
    stats: CheckStats,
) -> None:
    """Process fix_errors check if requested."""
    if "fix_errors" in checks_to_perform:
        fix_result = _execute_fix_errors(adapter, strict_mode)
        results["fix_errors"] = fix_result
        stats["checks_performed"].append("fix_errors")
        stats["total_errors"] += len(fix_result["errors"])
        stats["total_warnings"] += len(fix_result["warnings"])
        stats["files_modified"].extend(fix_result["files_modified"])


def _process_format_check(
    adapter: PythonAdapter,
    checks_to_perform: list[str],
    results: dict[str, CheckResult | TestResult],
    stats: CheckStats,
) -> None:
    """Process format check if requested."""
    if "format" in checks_to_perform:
        format_result = _execute_format(adapter)
        results["format"] = format_result
        stats["checks_performed"].append("format")
        stats["total_errors"] += len(format_result["errors"])
        stats["files_modified"].extend(format_result["files_modified"])


def _process_type_check(
    adapter: PythonAdapter,
    checks_to_perform: list[str],
    results: dict[str, CheckResult | TestResult],
    stats: CheckStats,
) -> None:
    """Process type_check check if requested."""
    if "type_check" in checks_to_perform:
        type_result = _execute_type_check(adapter)
        results["type_check"] = type_result
        stats["checks_performed"].append("type_check")
        stats["total_errors"] += len(type_result["errors"])


def _process_quality_check(
    adapter: PythonAdapter,
    checks_to_perform: list[str],
    results: dict[str, CheckResult | TestResult],
    stats: CheckStats,
) -> None:
    """Process quality check if requested."""
    if "quality" in checks_to_perform:
        lint_result = _execute_quality(adapter)
        results["quality"] = lint_result
        stats["checks_performed"].append("quality")
        stats["total_errors"] += len(lint_result["errors"])


def _process_tests_check(
    adapter: PythonAdapter,
    checks_to_perform: list[str],
    timeout: int | None,
    coverage_threshold: float,
    results: dict[str, CheckResult | TestResult],
    stats: CheckStats,
) -> None:
    """Process tests check if requested."""
    if "tests" in checks_to_perform:
        test_result = _execute_tests(adapter, timeout, coverage_threshold)
        results["tests"] = test_result
        stats["checks_performed"].append("tests")
        if not test_result["success"]:
            stats["total_errors"] += len(test_result["errors"])


def _execute_fix_errors(
    adapter: PythonAdapter,
    strict_mode: bool,
) -> CheckResult:
    """Execute fix_errors check."""
    return adapter.fix_errors(
        error_types=None,
        auto_fix=True,
        strict_mode=strict_mode,
    )


def _execute_format(adapter: PythonAdapter) -> CheckResult:
    """Execute format check."""
    return adapter.format_code()


def _execute_type_check(adapter: PythonAdapter) -> CheckResult:
    """Execute type_check check."""
    return adapter.type_check()


def _execute_quality(adapter: PythonAdapter) -> CheckResult:
    """Execute quality check."""
    return adapter.lint_code()


def _execute_tests(
    adapter: PythonAdapter,
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
    results: dict[str, CheckResult | TestResult],
    stats: CheckStats,
    detected_language: str,
) -> str:
    """Build JSON response."""
    total_errors = stats["total_errors"]
    success = total_errors == 0
    response: PreCommitResult = {
        "status": "success" if success else "error",
        "language": detected_language,
        "checks_performed": stats["checks_performed"],
        "results": results,
        "total_errors": total_errors,
        "total_warnings": stats["total_warnings"],
        "files_modified": list(set(stats["files_modified"])),
        "success": success,
    }
    return json.dumps(response, indent=2)


class FixQualityResult(TypedDict):
    """Result of fix_quality_issues operation."""

    status: Literal["success", "error"]
    errors_fixed: int
    warnings_fixed: int
    formatting_issues_fixed: int
    markdown_issues_fixed: int
    type_errors_fixed: int
    files_modified: list[str]
    remaining_issues: list[str]
    error_message: str | None


def _create_quality_error_response(error_message: str) -> str:
    """Create error response for quality fixes."""
    return json.dumps(
        {
            "status": "error",
            "errors_fixed": 0,
            "warnings_fixed": 0,
            "formatting_issues_fixed": 0,
            "markdown_issues_fixed": 0,
            "type_errors_fixed": 0,
            "files_modified": [],
            "remaining_issues": [],
            "error_message": error_message,
        },
        indent=2,
    )


async def _run_quality_checks(root_str: str) -> dict[str, object] | str:
    """Run quality checks and return result or error response."""
    fix_errors_result_json = await execute_pre_commit_checks(
        checks=["fix_errors", "format", "type_check"],
        project_root=root_str,
        strict_mode=False,
    )
    fix_errors_result = json.loads(fix_errors_result_json)

    if fix_errors_result.get("status") == "error":
        return _create_quality_error_response(
            fix_errors_result.get("error", "Unknown error")
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
    markdown_result = json.loads(markdown_result_json)
    return _process_markdown_results(markdown_result, files_modified)


def _extract_dict_from_object(
    obj: object, default: dict[str, object]
) -> dict[str, object]:
    """Extract dict from object with type checking."""
    return cast(dict[str, object], obj) if isinstance(obj, dict) else default


def _extract_list_from_object(obj: object, default: list[object]) -> list[object]:
    """Extract list from object with type checking."""
    return cast(list[object], obj) if isinstance(obj, list) else default


def _extract_int_from_object(obj: object, default: int) -> int:
    """Extract int from object with type checking."""
    return int(obj) if isinstance(obj, (int, str)) else default


def _extract_check_results(
    results: dict[str, object],
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    """Extract check result dicts from results."""
    fix_errors_check_obj = results.get("fix_errors", {})
    fix_errors_check = _extract_dict_from_object(fix_errors_check_obj, {})
    format_check_obj = results.get("format", {})
    format_check = _extract_dict_from_object(format_check_obj, {})
    type_check_result_obj = results.get("type_check", {})
    type_check_result = _extract_dict_from_object(type_check_result_obj, {})
    return fix_errors_check, format_check, type_check_result


def _extract_fix_statistics(
    fix_errors_result: dict[str, object],
) -> tuple[int, int, int, int, list[str]]:
    """Extract statistics from fix_errors result."""
    results_obj = fix_errors_result.get("results", {})
    results = _extract_dict_from_object(results_obj, {})
    fix_errors_check, format_check, type_check_result = _extract_check_results(results)

    errors = _extract_list_from_object(fix_errors_check.get("errors", []), [])
    warnings = _extract_list_from_object(fix_errors_check.get("warnings", []), [])
    errors_fixed = len(errors)
    warnings_fixed = len(warnings)
    formatting_issues_fixed = _extract_int_from_object(
        format_check.get("files_formatted", 0), 0
    )
    type_errors = _extract_list_from_object(type_check_result.get("errors", []), [])
    type_errors_fixed = len(type_errors)
    files_modified_list = _extract_list_from_object(
        fix_errors_result.get("files_modified", []), []
    )
    files_modified = list(set(cast(list[str], files_modified_list)))

    return (
        errors_fixed,
        warnings_fixed,
        formatting_issues_fixed,
        type_errors_fixed,
        files_modified,
    )


def _process_markdown_results(
    markdown_result: dict[str, object], files_modified: list[str]
) -> int:
    """Process markdown fix results and update files_modified list."""
    markdown_issues_fixed = 0
    success_obj = markdown_result.get("success")
    if success_obj:
        files_fixed_obj = markdown_result.get("files_fixed", 0)
        markdown_issues_fixed = (
            int(files_fixed_obj) if isinstance(files_fixed_obj, (int, str)) else 0
        )
        results_obj = markdown_result.get("results", [])
        if isinstance(results_obj, list):
            results_list = cast(list[object], results_obj)
            for item in results_list:
                if isinstance(item, dict):
                    file_result = cast(dict[str, object], item)
                    fixed_obj = file_result.get("fixed")
                    if fixed_obj:
                        file_path_obj = file_result.get("file", "")
                        file_path = str(file_path_obj) if file_path_obj else ""
                        if file_path and file_path not in files_modified:
                            files_modified.append(file_path)
    return markdown_issues_fixed


def _collect_remaining_issues(fix_errors_result: dict[str, object]) -> list[str]:
    """Collect remaining issues that couldn't be auto-fixed."""
    remaining_issues: list[str] = []
    total_errors_obj = fix_errors_result.get("total_errors", 0)
    total_errors = (
        int(total_errors_obj) if isinstance(total_errors_obj, (int, str)) else 0
    )
    if total_errors > 0:
        remaining_issues.append(f"{total_errors} errors remain after auto-fix")
    total_warnings_obj = fix_errors_result.get("total_warnings", 0)
    total_warnings = (
        int(total_warnings_obj) if isinstance(total_warnings_obj, (int, str)) else 0
    )
    if total_warnings > 0:
        remaining_issues.append(f"{total_warnings} warnings remain after auto-fix")
    return remaining_issues


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
    return {
        "status": "success",
        "errors_fixed": errors_fixed,
        "warnings_fixed": warnings_fixed,
        "formatting_issues_fixed": formatting_issues_fixed,
        "markdown_issues_fixed": markdown_issues_fixed,
        "type_errors_fixed": type_errors_fixed,
        "files_modified": files_modified,
        "remaining_issues": remaining_issues,
        "error_message": None,
    }


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
    return json.dumps(response, indent=2)


@mcp.tool()
async def fix_quality_issues(
    project_root: str | None = None,
    include_untracked_markdown: bool = True,
) -> str:
    """Automatically fix code quality issues on-the-go.

    This tool provides lightweight, automatic quality fixes to prevent error accumulation.
    It fixes type errors, formatting issues, linting errors, and markdown lint errors,
    but does NOT run tests (tests are reserved for the commit pipeline).

    The agent should automatically call this tool:
    - After making code changes
    - When errors are detected in the IDE
    - Before starting new work to ensure clean state
    - As part of regular development workflow

    Args:
        project_root: Path to project root directory. If None, uses current directory.
        include_untracked_markdown: Include untracked markdown files in markdown lint fixing.
            Default: True.

    Returns:
        JSON string with quality fix results containing:
        - status: "success" or "error"
        - errors_fixed: Count of errors fixed
        - warnings_fixed: Count of warnings fixed
        - formatting_issues_fixed: Count of formatting issues fixed
        - markdown_issues_fixed: Count of markdown lint issues fixed
        - type_errors_fixed: Count of type errors fixed
        - files_modified: List of files modified during quality fixes
        - remaining_issues: List of issues that could not be auto-fixed (if any)
        - error_message: Error message if operation failed

    Examples:
        Example 1: Fix all quality issues automatically
        >>> await fix_quality_issues()
        {
          "status": "success",
          "errors_fixed": 5,
          "warnings_fixed": 2,
          "formatting_issues_fixed": 3,
          "markdown_issues_fixed": 2,
          "type_errors_fixed": 1,
          "files_modified": ["src/file1.py", "README.md"],
          "remaining_issues": [],
          "error_message": null
        }

        Example 2: Fix quality issues with specific project root
        >>> await fix_quality_issues(project_root="/path/to/project")
        {
          "status": "success",
          "errors_fixed": 0,
          "warnings_fixed": 0,
          "formatting_issues_fixed": 1,
          "markdown_issues_fixed": 0,
          "type_errors_fixed": 0,
          "files_modified": ["src/file2.py"],
          "remaining_issues": [],
          "error_message": null
        }
    """
    try:
        root_str = _get_project_root_str(project_root)

        # Fix errors and extract statistics
        fix_errors_result = await _run_quality_checks(root_str)
        if isinstance(fix_errors_result, str):
            return fix_errors_result

        (
            errors_fixed,
            warnings_fixed,
            formatting_issues_fixed,
            type_errors_fixed,
            files_modified,
        ) = _extract_fix_statistics(fix_errors_result)

        # Fix markdown and collect remaining issues
        markdown_issues_fixed = await _fix_markdown_and_update_files(
            root_str, include_untracked_markdown, files_modified
        )
        remaining_issues = _collect_remaining_issues(fix_errors_result)
        return _build_quality_response_json(
            errors_fixed,
            warnings_fixed,
            formatting_issues_fixed,
            markdown_issues_fixed,
            type_errors_fixed,
            files_modified,
            remaining_issues,
        )

    except Exception as e:
        return _create_quality_error_response(str(e))
