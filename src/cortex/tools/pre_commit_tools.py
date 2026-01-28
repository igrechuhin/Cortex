"""Pre-Commit Tools

MCP tools for executing pre-commit checks with language auto-detection.

Total: 2 tools
- execute_pre_commit_checks: Execute pre-commit checks (fix errors,
  format, type check, quality, tests)
- fix_quality_issues: Automatically fix quality issues on-the-go
  (fix errors, format, type check, markdown lint)
"""

import ast
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.constants import MCP_TOOL_TIMEOUT_VERY_COMPLEX
from cortex.core.mcp_stability import mcp_tool_wrapper
from cortex.core.models import JsonValue, ModelDict
from cortex.managers.initialization import get_project_root
from cortex.server import mcp
from cortex.services.framework_adapters.base import CheckResult, TestResult
from cortex.services.framework_adapters.python_adapter import PythonAdapter
from cortex.services.language_detector import LanguageDetector, LanguageInfo

# Import markdown operations for markdown lint fixing
# No circular import: markdown_operations doesn't import pre_commit_tools
from cortex.tools.markdown_operations import fix_markdown_lint  # noqa: F401
from cortex.tools.pre_commit_helpers import (
    collect_remaining_issues,
    extract_check_results,
    extract_dict_from_object,
    extract_int_from_object,
    extract_list_from_object,
)

# Constants for quality checks
MAX_FILE_LINES = 400
MAX_FUNCTION_LINES = 30


class FileSizeViolation(BaseModel):
    """File size violation details."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    file: str = Field(description="File path")
    lines: int = Field(ge=0, description="Number of lines")
    max_lines: int = Field(ge=0, description="Maximum allowed lines")
    excess: int = Field(ge=0, description="Excess lines over limit")


class FunctionLengthViolation(BaseModel):
    """Function length violation details."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    file: str = Field(description="File path")
    function: str = Field(description="Function name")
    line: int = Field(ge=1, description="Line number")
    lines: int = Field(ge=0, description="Number of lines")
    max_lines: int = Field(ge=0, description="Maximum allowed lines")
    excess: int = Field(ge=0, description="Excess lines over limit")


class QualityCheckResult(BaseModel):
    """Result of quality check including file size and function length."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    check_type: str = Field(description="Type of check")
    success: bool = Field(description="Whether check succeeded")
    output: str = Field(description="Check output")
    errors: list[str] = Field(default_factory=list, description="List of errors")
    warnings: list[str] = Field(default_factory=list, description="List of warnings")
    files_modified: list[str] = Field(
        default_factory=list, description="List of modified files"
    )
    file_size_violations: list[FileSizeViolation] = Field(
        default_factory=lambda: list[FileSizeViolation](),
        description="File size violations",
    )
    function_length_violations: list[FunctionLengthViolation] = Field(
        default_factory=lambda: list[FunctionLengthViolation](),
        description="Function length violations",
    )


class PreCommitResult(BaseModel):
    """Result of pre-commit checks execution."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    status: Literal["success", "error"] = Field(description="Operation status")
    language: str | None = Field(default=None, description="Detected language")
    checks_performed: list[str] = Field(
        default_factory=list, description="List of checks performed"
    )
    results: dict[str, CheckResult | TestResult | QualityCheckResult] = Field(
        default_factory=dict, description="Check results by check name"
    )
    total_errors: int = Field(ge=0, description="Total number of errors")
    total_warnings: int = Field(ge=0, description="Total number of warnings")
    files_modified: list[str] = Field(
        default_factory=list, description="List of modified files"
    )
    success: bool = Field(description="Whether all checks passed")


class CheckStats(BaseModel):
    """Statistics for pre-commit checks."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    total_errors: int = Field(ge=0, description="Total number of errors")
    total_warnings: int = Field(ge=0, description="Total number of warnings")
    files_modified: list[str] = Field(
        default_factory=list, description="List of modified files"
    )
    checks_performed: list[str] = Field(
        default_factory=list, description="List of checks performed"
    )


_MAX_LOG_OUTPUT_LENGTH = 4000


def _truncate_log_value(value: str, max_length: int = _MAX_LOG_OUTPUT_LENGTH) -> str:
    """Truncate very large log strings to keep JSON responses compact."""
    if len(value) <= max_length:
        return value
    truncated_chars = len(value) - max_length
    suffix = f"\n...[truncated {truncated_chars} characters]..."
    return value[:max_length] + suffix


def _truncate_large_logs_in_data(obj: JsonValue) -> JsonValue:
    """Recursively truncate large log fields in JSON-like data."""
    if isinstance(obj, dict):
        truncated: dict[str, JsonValue] = {}
        for key, value in obj.items():
            if isinstance(value, str) and key == "output":
                truncated[key] = _truncate_log_value(value)
            else:
                truncated[key] = _truncate_large_logs_in_data(value)
        return truncated
    if isinstance(obj, list):
        return [_truncate_large_logs_in_data(item) for item in obj]
    return obj


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
    if language_info.language == "python":
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
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_VERY_COMPLEX)
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
        checks: List of checks to perform. Options: "fix_errors",
            "format", "type_check", "quality", "tests". If None, performs
            all checks.
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
        - checks: Dictionary of check results (fix_errors, format,
          type_check, quality, tests)
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
              "success": true,
              "file_size_violations": [],
              "function_length_violations": [],
              "errors": [],
              "message": "All quality checks passed"
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
            "checks_performed": [
                "fix_errors",
                "format",
                "type_check",
                "quality",
                "tests",
            ]
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
                f"Language '{language_info.language}' is not yet supported. "
                + "Supported languages: python"
            )

        checks_to_perform = _determine_checks_to_perform(checks)
        results, stats = _execute_all_checks(
            adapter, checks_to_perform, strict_mode, timeout, coverage_threshold
        )

        return _build_response(results, stats, language_info.language)

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
    # Default ordering is optimized for fast feedback:
    # - fix_errors first (can resolve obvious failures cheaply)
    # - quality early (file sizes / function lengths fail-fast before expensive steps)
    # - formatting and type checking next
    # - tests last (most expensive)
    default_checks = ["fix_errors", "quality", "format", "type_check", "tests"]
    return list(checks) if checks else default_checks


def _execute_all_checks(
    adapter: PythonAdapter,
    checks_to_perform: list[str],
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
    _process_quality_check(adapter, checks_to_perform, results, stats)
    _process_format_check(adapter, checks_to_perform, results, stats)
    _process_type_check(adapter, checks_to_perform, results, stats)
    _process_tests_check(
        adapter, checks_to_perform, timeout, coverage_threshold, results, stats
    )

    return results, stats


def _process_fix_errors_check(
    adapter: PythonAdapter,
    checks_to_perform: list[str],
    strict_mode: bool,
    results: dict[str, CheckResult | TestResult | QualityCheckResult],
    stats: CheckStats,
) -> None:
    """Process fix_errors check if requested."""
    if "fix_errors" in checks_to_perform:
        fix_result = _execute_fix_errors(adapter, strict_mode)
        results["fix_errors"] = fix_result
        stats.checks_performed.append("fix_errors")
        stats.total_errors += len(fix_result.errors)
        stats.total_warnings += len(fix_result.warnings)
        stats.files_modified.extend(fix_result.files_modified)


def _process_format_check(
    adapter: PythonAdapter,
    checks_to_perform: list[str],
    results: dict[str, CheckResult | TestResult | QualityCheckResult],
    stats: CheckStats,
) -> None:
    """Process format check if requested."""
    if "format" in checks_to_perform:
        format_result = _execute_format(adapter)
        results["format"] = format_result
        stats.checks_performed.append("format")
        stats.total_errors += len(format_result.errors)
        stats.files_modified.extend(format_result.files_modified)


def _process_type_check(
    adapter: PythonAdapter,
    checks_to_perform: list[str],
    results: dict[str, CheckResult | TestResult | QualityCheckResult],
    stats: CheckStats,
) -> None:
    """Process type_check check if requested."""
    if "type_check" in checks_to_perform:
        type_result = _execute_type_check(adapter)
        results["type_check"] = type_result
        stats.checks_performed.append("type_check")
        stats.total_errors += len(type_result.errors)


def _process_quality_check(
    adapter: PythonAdapter,
    checks_to_perform: list[str],
    results: dict[str, CheckResult | TestResult | QualityCheckResult],
    stats: CheckStats,
) -> None:
    """Process quality check if requested."""
    if "quality" in checks_to_perform:
        quality_result = _execute_quality(adapter)
        results["quality"] = quality_result
        stats.checks_performed.append("quality")
        stats.total_errors += len(quality_result.errors)


def _process_tests_check(
    adapter: PythonAdapter,
    checks_to_perform: list[str],
    timeout: int | None,
    coverage_threshold: float,
    results: dict[str, CheckResult | TestResult | QualityCheckResult],
    stats: CheckStats,
) -> None:
    """Process tests check if requested."""
    if "tests" in checks_to_perform:
        test_result = _execute_tests(adapter, timeout, coverage_threshold)
        results["tests"] = test_result
        stats.checks_performed.append("tests")
        if not test_result.success:
            stats.total_errors += len(test_result.errors)


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


def _count_file_lines(path: Path) -> int:
    """Count non-blank, non-comment, non-docstring lines in a file."""
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        return 0

    count = 0
    in_docstring = False

    for line in lines:
        stripped = line.strip()
        if '"""' in stripped or "'''" in stripped:
            in_docstring = not in_docstring
            continue
        if in_docstring:
            continue
        if not stripped or stripped.startswith("#"):
            continue
        count += 1

    return count


def _check_file_sizes(project_root: Path) -> list[FileSizeViolation]:
    """Check all Python files for size violations."""
    violations: list[FileSizeViolation] = []
    src_dir = project_root / "src"
    # Files excluded from size checks (data definition files that are inherently large)
    excluded_files = {"models.py"}  # Pydantic model definitions

    if not src_dir.exists():
        return violations

    for py_file in src_dir.glob("**/*.py"):
        if "__pycache__" in str(py_file) or py_file.name.startswith("test_"):
            continue
        if py_file.name in excluded_files:
            continue
        lines = _count_file_lines(py_file)
        if lines > MAX_FILE_LINES:
            try:
                relative_path = str(py_file.relative_to(project_root))
            except ValueError:
                relative_path = str(py_file)
            violations.append(
                FileSizeViolation(
                    file=relative_path,
                    lines=lines,
                    max_lines=MAX_FILE_LINES,
                    excess=lines - MAX_FILE_LINES,
                )
            )

    return violations


def _get_docstring_range(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> tuple[int, int] | None:
    """Get docstring line range if function has a docstring."""
    if (
        node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
        and isinstance(node.body[0].value.value, str)
    ):
        start = node.body[0].lineno
        end = node.body[0].end_lineno
        if end is not None:
            return (start, end)
    return None


class _FunctionVisitor(ast.NodeVisitor):
    """AST visitor to find and check function lengths."""

    def __init__(self, source_lines: list[str]) -> None:
        self.source_lines = source_lines
        self.violations: list[tuple[str, int, int]] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._check_function(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._check_function(node)
        self.generic_visit(node)

    def _check_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        start_line = node.lineno
        end_line = node.end_lineno
        if end_line is None:
            return

        docstring_range = _get_docstring_range(node)
        logical_lines = self._count_logical_lines(start_line, end_line, docstring_range)

        if logical_lines > MAX_FUNCTION_LINES:
            self.violations.append((node.name, logical_lines, start_line))

    def _count_logical_lines(
        self,
        start_line: int,
        end_line: int,
        docstring_range: tuple[int, int] | None,
    ) -> int:
        """Count logical lines in function body."""
        logical_lines = 0
        for line_num in range(start_line, end_line + 1):
            if self._should_skip_line(line_num, start_line, docstring_range):
                continue
            logical_lines += 1
        return logical_lines

    def _should_skip_line(
        self,
        line_num: int,
        start_line: int,
        docstring_range: tuple[int, int] | None,
    ) -> bool:
        """Check if line should be skipped when counting."""
        if line_num <= 0 or line_num > len(self.source_lines):
            return True
        line = self.source_lines[line_num - 1].strip()
        if line_num == start_line:
            return True
        if docstring_range and docstring_range[0] <= line_num <= docstring_range[1]:
            return True
        if not line or line.startswith("#"):
            return True
        return False


def _check_function_lengths_in_file(
    path: Path,
) -> list[tuple[str, int, int]]:
    """Check all functions in file for length violations."""
    try:
        with open(path, encoding="utf-8") as f:
            source = f.read()
            source_lines = source.split("\n")
    except Exception:
        return []

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []

    visitor = _FunctionVisitor(source_lines)
    visitor.visit(tree)
    return visitor.violations


def _check_function_lengths(project_root: Path) -> list[FunctionLengthViolation]:
    """Check all Python files for function length violations."""
    violations: list[FunctionLengthViolation] = []
    src_dir = project_root / "src"

    if not src_dir.exists():
        return violations

    for py_file in src_dir.glob("**/*.py"):
        if "__pycache__" in str(py_file) or py_file.name.startswith("test_"):
            continue
        file_violations = _check_function_lengths_in_file(py_file)
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


def _execute_quality(adapter: PythonAdapter) -> QualityCheckResult:
    """Execute quality check including linting, file sizes, and function lengths."""
    lint_result = adapter.lint_code()
    project_root = adapter.project_root
    file_violations = _check_file_sizes(project_root)
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
    results: dict[str, CheckResult | TestResult | QualityCheckResult],
    stats: CheckStats,
    detected_language: str,
) -> str:
    """Build JSON response."""
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
    compact = _truncate_large_logs_in_data(data)
    return json.dumps(compact, separators=(",", ":"))


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
    compact = _truncate_large_logs_in_data(data)
    return json.dumps(compact, separators=(",", ":"))


async def _run_quality_checks(root_str: str) -> ModelDict | str:
    """Run quality checks and return result or error response."""
    fix_errors_result_json = await execute_pre_commit_checks(
        checks=["fix_errors", "format", "type_check"],
        project_root=root_str,
        strict_mode=False,
    )
    fix_errors_result_raw: JsonValue = json.loads(fix_errors_result_json)
    if not isinstance(fix_errors_result_raw, dict):
        return _create_quality_error_response("Invalid quality check response")
    fix_errors_result = cast(ModelDict, fix_errors_result_raw)

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
    if not isinstance(markdown_result_raw, dict):
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
        markdown_issues_fixed = (
            int(files_fixed_obj) if isinstance(files_fixed_obj, (int, str)) else 0
        )
        results_obj = markdown_result.get("results", [])
        if isinstance(results_obj, list):
            for item in cast(list[JsonValue], results_obj):
                if isinstance(item, dict):
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
    compact = _truncate_large_logs_in_data(data)
    return json.dumps(compact, separators=(",", ":"))


@mcp.tool()
async def fix_quality_issues(
    project_root: str | None = None,
    include_untracked_markdown: bool = True,
) -> str:
    """Automatically fix code quality issues on-the-go.

    This tool provides lightweight, automatic quality fixes to prevent
    error accumulation. It fixes type errors, formatting issues, linting
    errors, and markdown lint errors, but does NOT run tests (tests are
    reserved for the commit pipeline).

    The agent should automatically call this tool:
    - After making code changes
    - When errors are detected in the IDE
    - Before starting new work to ensure clean state
    - As part of regular development workflow

    Args:
        project_root: Path to project root directory. If None, uses current directory.
        include_untracked_markdown: Include untracked markdown files in
            markdown lint fixing. Default: True.

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
        remaining_issues = collect_remaining_issues(fix_errors_result)
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
