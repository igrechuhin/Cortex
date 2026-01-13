"""Pre-Commit Tools

MCP tools for executing pre-commit checks with language auto-detection.

Total: 1 tool
- execute_pre_commit_checks: Execute pre-commit checks (fix errors, format, type check, quality, tests)
"""

import json
from collections.abc import Sequence
from typing import Literal, TypedDict

from cortex.managers.initialization import get_project_root
from cortex.server import mcp
from cortex.services.framework_adapters.base import CheckResult, TestResult
from cortex.services.framework_adapters.python_adapter import PythonAdapter
from cortex.services.language_detector import LanguageDetector, LanguageInfo


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
        JSON string with pre-commit check results.
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
