"""Helper functions for pre-commit tools.

Extracted to keep pre_commit_tools.py under 400 lines.
"""

import ast
import json
import math
from collections.abc import Sequence
from enum import Enum
from pathlib import Path
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.constants import (
    FILE_SIZE_EXCLUDED_FILENAMES,
    MAX_FILE_LINES,
    MAX_FUNCTION_LINES,
)
from cortex.core.models import JsonValue, ModelDict
from cortex.core.path_resolver import has_memory_bank
from cortex.managers.initialization import get_project_root
from cortex.services.framework_adapters.base import (
    CheckResult,
    TestResult,
)
from cortex.services.framework_adapters.detection import detect_language_at_path
from cortex.services.language_detector import LanguageInfo


class PreCommitCheck(str, Enum):
    """Fixed set of pre-commit check names. Use instead of raw strings."""

    FIX_ERRORS = "fix_errors"
    FORMAT = "format"
    FORMAT_CI_PARITY = "format_ci_parity"
    TYPE_CHECK = "type_check"
    QUALITY = "quality"
    SPELLING = "spelling"
    TEST_NAMING = "test_naming"
    CHECK_ASYNC_TESTS = "check_async_tests"
    TESTS = "tests"


DEFAULT_CHECKS: list[PreCommitCheck] = [
    PreCommitCheck.FIX_ERRORS,
    PreCommitCheck.QUALITY,
    PreCommitCheck.FORMAT,
    PreCommitCheck.TYPE_CHECK,
    PreCommitCheck.TESTS,
]


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
        default_factory=lambda: cast(list[FileSizeViolation], []),
        description="File size violations",
    )
    function_length_violations: list[FunctionLengthViolation] = Field(
        default_factory=lambda: cast(list[FunctionLengthViolation], []),
        description="Function length violations",
    )


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


def extract_dict_from_object(
    obj: JsonValue, default: dict[str, JsonValue]
) -> dict[str, JsonValue]:
    """Extract dict from object with type checking."""
    return cast(dict[str, JsonValue], obj) if isinstance(obj, dict) else default


def extract_list_from_object(obj: JsonValue, default: list[str]) -> list[str]:
    """Extract list from object with type checking.

    Returns list of strings, filtering out non-string items.
    """
    if isinstance(obj, list):
        obj_list = cast(list[JsonValue], obj)
        return [str(item) for item in obj_list if isinstance(item, (str, int, float))]
    return default


def extract_int_from_object(obj: JsonValue, default: int) -> int:
    """Extract int from object with type checking."""
    return int(obj) if isinstance(obj, (int, str)) else default


def extract_check_results(
    results: dict[str, JsonValue],
) -> tuple[ModelDict, ModelDict, ModelDict]:
    """Extract check result dicts from results."""
    fix_errors_check_raw = results.get("fix_errors")
    format_check_raw = results.get("format")
    type_check_result_raw = results.get("type_check")

    fix_errors_check: ModelDict
    if isinstance(fix_errors_check_raw, dict):
        fix_errors_check = cast(ModelDict, fix_errors_check_raw)
    else:
        fix_errors_check = cast(ModelDict, {})

    format_check: ModelDict
    if isinstance(format_check_raw, dict):
        format_check = cast(ModelDict, format_check_raw)
    else:
        format_check = cast(ModelDict, {})

    type_check_result: ModelDict
    if isinstance(type_check_result_raw, dict):
        type_check_result = cast(ModelDict, type_check_result_raw)
    else:
        type_check_result = cast(ModelDict, {})

    return fix_errors_check, format_check, type_check_result


def _check_fix_errors_remaining(fix_errors_check: ModelDict) -> str | None:
    """Check if fix_errors check has remaining issues."""
    fix_errors_list = extract_list_from_object(fix_errors_check.get("errors", []), [])
    fix_errors_success_obj = fix_errors_check.get("success")
    if isinstance(fix_errors_success_obj, bool):
        fix_errors_success = bool(fix_errors_success_obj)
    else:
        fix_errors_success = len(fix_errors_list) == 0

    if not fix_errors_success and fix_errors_list:
        return f"{len(fix_errors_list)} linting/formatting errors remain after auto-fix"
    return None


def _check_format_remaining(format_check: ModelDict) -> str | None:
    """Check if format check has remaining issues."""
    format_errors_list = extract_list_from_object(format_check.get("errors", []), [])
    format_success_obj = format_check.get("success")
    if isinstance(format_success_obj, bool):
        format_success = bool(format_success_obj)
    else:
        format_success = len(format_errors_list) == 0

    if not format_success and format_errors_list:
        return f"{len(format_errors_list)} formatting errors remain after auto-fix"
    return None


def _check_type_check_remaining(type_check_result: ModelDict) -> str | None:
    """Check if type_check has remaining issues."""
    type_errors_list = extract_list_from_object(type_check_result.get("errors", []), [])
    type_check_success_obj = type_check_result.get("success")
    if isinstance(type_check_success_obj, bool):
        type_check_success = bool(type_check_success_obj)
    else:
        type_check_success = len(type_errors_list) == 0

    if not type_check_success and type_errors_list:
        return f"{len(type_errors_list)} type errors remain after auto-fix"
    return None


def _check_type_warnings_remaining(type_check_result: ModelDict) -> str | None:
    """Check if type_check has remaining warnings (e.g. unknown variable types)."""
    type_warnings_list = extract_list_from_object(
        type_check_result.get("warnings", []), []
    )
    if type_warnings_list:
        # Treat type-check warnings as remaining issues so fix_quality_issues
        # surfaces diagnostics like reportUnknownVariableType instead of
        # declaring the pipeline completely clean.
        return f"{len(type_warnings_list)} type-check warnings remain after auto-fix"
    return None


def _check_warnings_remaining(fix_errors_check: ModelDict) -> str | None:
    """Check if fix_errors check has remaining warnings."""
    fix_warnings_list = extract_list_from_object(
        fix_errors_check.get("warnings", []), []
    )
    if fix_warnings_list:
        return f"{len(fix_warnings_list)} warnings remain after auto-fix"
    return None


def collect_remaining_issues(fix_errors_result: ModelDict) -> list[str]:
    """Collect remaining issues that couldn't be auto-fixed.

    Checks actual check results to determine if there are remaining errors,
    rather than using aggregate total_errors/total_warnings which may include
    errors that were already fixed or errors from checks that succeeded.
    """
    remaining_issues: list[str] = []

    # Extract results dict
    results_obj = fix_errors_result.get("results", {})
    results = extract_dict_from_object(results_obj, {})

    # Check each check result for actual remaining errors
    fix_errors_check, format_check, type_check_result = extract_check_results(results)

    # Check each check type for remaining issues
    issue = _check_fix_errors_remaining(fix_errors_check)
    if issue:
        remaining_issues.append(issue)

    issue = _check_format_remaining(format_check)
    if issue:
        remaining_issues.append(issue)

    issue = _check_type_check_remaining(type_check_result)
    if issue:
        remaining_issues.append(issue)

    issue = _check_type_warnings_remaining(type_check_result)
    if issue:
        remaining_issues.append(issue)

    issue = _check_warnings_remaining(fix_errors_check)
    if issue:
        remaining_issues.append(issue)

    return remaining_issues


def create_error_result(error: str, error_type: str = "ValueError") -> str:
    """Create error response JSON."""
    return json.dumps(
        {"status": "error", "error": error, "error_type": error_type},
        indent=2,
    )


def create_error_result_dict(error: str, error_type: str = "ValueError") -> ModelDict:
    """Create error response as dict for MCP (avoids double JSON encoding)."""
    from cortex.tools.tool_error_formatters import format_tool_error

    # Create exception object for formatter
    exception: Exception
    if error_type == "ValueError":
        exception = ValueError(error)
    elif error_type == "FileNotFoundError":
        exception = FileNotFoundError(error)
    elif error_type == "Exception":
        exception = Exception(error)
    else:
        # For other types, use ValueError but preserve error_type in response
        exception = ValueError(error)

    # Format using standardized formatter and parse back to dict
    json_response = format_tool_error(
        exception,
        suggestion=(
            "Review the error details and ensure all parameters are valid. "
            "Check the tool documentation for correct usage."
        ),
        example={
            "checks": ["format", "type_check"],
            "test_timeout": 300,
            "coverage_threshold": 0.9,
            "strict_mode": False,
        },
    )
    result = json.loads(json_response)
    # Override error_type if it was changed (e.g., generic Exception -> ValueError)
    if error_type != "ValueError" and error_type != type(exception).__name__:
        result["error_type"] = error_type
    return result


def get_project_root_str(project_root: str | None) -> str:
    """Get project root as string."""
    root = get_project_root(project_root)
    return str(root)


def unsupported_language_result(
    language: str, supported_languages: tuple[str, ...]
) -> str:
    """Return error JSON for unsupported language."""
    supported = ", ".join(supported_languages)
    msg = (
        f"Language '{language}' is not yet supported. "
        + f"Supported languages: {supported}"
    )
    return create_error_result(msg)


def unsupported_language_result_dict(
    language: str, supported_languages: tuple[str, ...]
) -> ModelDict:
    """Return error dict for unsupported language (for MCP tool return)."""
    supported = ", ".join(supported_languages)
    msg = (
        f"Language '{language}' is not yet supported. "
        + f"Supported languages: {supported}"
    )
    return create_error_result_dict(msg)


_MAX_ANCESTOR_WALK = 20


def _detect_language_in_cortex_subdirs(
    candidate: Path,
) -> tuple[LanguageInfo, Path] | None:
    """Try detecting language in subdirs of a Cortex root (1–2 levels)."""
    try:
        for sub in candidate.iterdir():
            if not sub.is_dir() or sub.name.startswith("."):
                continue
            if not has_memory_bank(sub):
                for sub2 in sub.iterdir():
                    if (
                        not sub2.is_dir()
                        or sub2.name.startswith(".")
                        or not has_memory_bank(sub2)
                    ):
                        continue
                    result = detect_language_at_path(sub2)
                    if result is not None:
                        return result
                continue
            result = detect_language_at_path(sub)
            if result is not None:
                return result
    except OSError:
        pass
    return None


def _detect_language_at_cortex_root(
    start_path: Path,
) -> tuple[LanguageInfo, Path] | None:
    """If start_path or an ancestor is a Cortex root, detect language there.

    Uses framework adapters for detection (language-agnostic). Returns
    (LanguageInfo, project_root_path) when found so the adapter runs in
    the actual project (e.g. ~/Repo/Cortex) not the wrong root (e.g. ~).
    """
    for candidate in [start_path, *list(start_path.parents)[:_MAX_ANCESTOR_WALK]]:
        if candidate == candidate.parent:
            continue
        if not has_memory_bank(candidate):
            continue
        result = detect_language_at_path(candidate)
        if result is not None:
            return result
        result = _detect_language_in_cortex_subdirs(candidate)
        if result is not None:
            return result
    return None


def _detect_language_from_ancestors(
    start_path: Path,
) -> tuple[LanguageInfo, Path] | None:
    """Walk up from start_path and run language detection until a language is found.

    Uses framework adapters for detection. Returns (LanguageInfo, project_root_path).
    """
    ancestors = [start_path, *list(start_path.parents)[:_MAX_ANCESTOR_WALK]]
    for candidate in ancestors:
        if candidate == candidate.parent:
            continue
        result = detect_language_at_path(candidate)
        if result is not None:
            return result
    return None


def _resolve_language_at_root(root_path: Path) -> tuple[LanguageInfo, str] | str:
    """Detect language at root or ancestors or Cortex root; return (info, root) or error str."""
    result = detect_language_at_path(root_path)
    if result is not None:
        info, path = result
        return (info, str(path))
    resolved = _detect_language_from_ancestors(root_path)
    if resolved is not None:
        info, path = resolved
        return (info, str(path))
    resolved = _detect_language_at_cortex_root(root_path)
    if resolved is not None:
        info, path = resolved
        return (info, str(path))
    msg = (
        "Could not detect project language. Pass language (e.g. 'python') "
        + "to execute_pre_commit_checks when invoking the tool."
    )
    return create_error_result(msg)


def detect_or_use_language(
    language: str | None, root_str: str
) -> tuple[LanguageInfo, str] | str:
    """Detect language or use provided language.

    Returns (LanguageInfo, root_to_use) so the adapter runs in the correct
    project (e.g. when project was found in a subdir). Returns error JSON str on failure.
    Empty string is treated as auto-detect (same as None).
    """
    if language is None or language == "":
        return _resolve_language_at_root(Path(root_str).resolve())
    detected_language = language.lower()
    info = LanguageInfo(
        language=detected_language,
        test_framework=None,
        formatter=None,
        linter=None,
        type_checker=None,
        build_tool=None,
        confidence=0.5,
    )
    return (info, root_str)


def determine_checks_to_perform(checks: Sequence[str] | None) -> list[PreCommitCheck]:
    """Determine which checks to perform. Invalid names are skipped.

    When \"quality\" is requested, type_check is included so the quality gate
    catches type diagnostics (e.g. reportRedeclaration) and matches IDE/CI.
    """
    if not checks:
        return list(DEFAULT_CHECKS)
    result: list[PreCommitCheck] = []
    for name in checks:
        try:
            result.append(PreCommitCheck(name))
        except ValueError:
            continue
    if not result:
        return list(DEFAULT_CHECKS)
    # Quality gate includes type_check so CI/IDE type diagnostics are caught
    if PreCommitCheck.QUALITY in result and PreCommitCheck.TYPE_CHECK not in result:
        quality_idx = result.index(PreCommitCheck.QUALITY)
        result.insert(quality_idx + 1, PreCommitCheck.TYPE_CHECK)
    return result


MAX_LOG_OUTPUT_LENGTH = 4000


def truncate_log_value(value: str, max_length: int = MAX_LOG_OUTPUT_LENGTH) -> str:
    """Truncate very large log strings to keep JSON responses compact."""
    if len(value) <= max_length:
        return value
    truncated_chars = len(value) - max_length
    suffix = f"\n...[truncated {truncated_chars} characters]..."
    return value[:max_length] + suffix


def truncate_large_logs_in_data(obj: JsonValue) -> JsonValue:
    """Recursively truncate large log fields in JSON-like data."""
    if isinstance(obj, dict):
        truncated: dict[str, JsonValue] = {}
        for key, value in obj.items():
            if isinstance(value, str) and key == "output":
                truncated[key] = truncate_log_value(value)
            else:
                truncated[key] = truncate_large_logs_in_data(value)
        return truncated
    if isinstance(obj, list):
        return [truncate_large_logs_in_data(item) for item in obj]
    return obj


def _replace_nan_inf(value: JsonValue) -> JsonValue:
    """Recursively replace float nan/inf with None for JSON compatibility."""
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if isinstance(value, dict):
        return {k: _replace_nan_inf(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_replace_nan_inf(item) for item in value]
    return value


def _json_friendly_default(obj: object) -> str | None:
    """Convert non-JSON-serializable values for MCP response."""
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    return str(obj)


def ensure_json_serializable_for_mcp(data: ModelDict) -> ModelDict:
    """Ensure dict round-trips through JSON for MCP (avoids serialization errors).

    Converts float nan/inf to None and other non-serializable types to strings,
    then round-trips through json.dumps/json.loads so the result is exactly
    what the MCP client will receive after parsing.
    """
    sanitized = _replace_nan_inf(data)
    serialized = json.dumps(
        sanitized, separators=(",", ":"), default=_json_friendly_default
    )
    return cast(ModelDict, json.loads(serialized))


def get_docstring_range(
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
        docstring_range = get_docstring_range(node)
        logical_lines = self._count_logical_lines(start_line, end_line, docstring_range)
        if logical_lines > MAX_FUNCTION_LINES:
            self.violations.append((node.name, logical_lines, start_line))

    def _count_logical_lines(
        self,
        start_line: int,
        end_line: int,
        docstring_range: tuple[int, int] | None,
    ) -> int:
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


def check_function_lengths_in_file(path: Path) -> list[tuple[str, int, int]]:
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


def count_file_lines(path: Path) -> int:
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


def check_file_sizes(
    project_root: Path,
    max_lines: int | None = None,
) -> list[FileSizeViolation]:
    """Check all Python files under src for size violations."""
    if max_lines is None:
        max_lines = MAX_FILE_LINES
    violations: list[FileSizeViolation] = []
    src_dir = project_root / "src"
    # Must match CI (.cortex/synapse/scripts/python/check_file_sizes.py) and constants.FILE_SIZE_EXCLUDED_FILENAMES
    excluded_files = frozenset(FILE_SIZE_EXCLUDED_FILENAMES)

    if not src_dir.exists():
        return violations

    for py_file in src_dir.glob("**/*.py"):
        if "__pycache__" in str(py_file) or py_file.name.startswith("test_"):
            continue
        if py_file.name in excluded_files:
            continue
        lines = count_file_lines(py_file)
        if lines > max_lines:
            try:
                relative_path = str(py_file.relative_to(project_root))
            except ValueError:
                relative_path = str(py_file)
            violations.append(
                FileSizeViolation(
                    file=relative_path,
                    lines=lines,
                    max_lines=max_lines,
                    excess=lines - max_lines,
                )
            )

    return violations
