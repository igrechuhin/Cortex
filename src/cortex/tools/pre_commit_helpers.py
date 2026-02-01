"""Helper functions for pre-commit tools.

Extracted to keep pre_commit_tools.py under 400 lines.
"""

import json
from collections.abc import Sequence
from enum import Enum
from pathlib import Path
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.constants import MAX_FILE_LINES
from cortex.core.models import JsonValue, ModelDict
from cortex.managers.initialization import get_project_root
from cortex.services.framework_adapters.base import (
    CheckResult,
    TestResult,
)
from cortex.services.language_detector import LanguageDetector, LanguageInfo


class PreCommitCheck(str, Enum):
    """Fixed set of pre-commit check names. Use instead of raw strings."""

    FIX_ERRORS = "fix_errors"
    FORMAT = "format"
    FORMAT_CI_PARITY = "format_ci_parity"
    TYPE_CHECK = "type_check"
    QUALITY = "quality"
    TEST_NAMING = "test_naming"
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
) -> tuple[dict[str, JsonValue], dict[str, JsonValue], dict[str, JsonValue]]:
    """Extract check result dicts from results."""
    fix_errors_check_obj = results.get("fix_errors", {})
    format_check_obj = results.get("format", {})
    type_check_result_obj = results.get("type_check", {})

    fix_errors_check = (
        cast(dict[str, JsonValue], fix_errors_check_obj)
        if isinstance(fix_errors_check_obj, dict)
        else {}
    )
    format_check = (
        cast(dict[str, JsonValue], format_check_obj)
        if isinstance(format_check_obj, dict)
        else {}
    )
    type_check_result = (
        cast(dict[str, JsonValue], type_check_result_obj)
        if isinstance(type_check_result_obj, dict)
        else {}
    )

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


def detect_or_use_language(language: str | None, root_str: str) -> LanguageInfo | str:
    """Detect language or use provided language."""
    if language is None:
        detector = LanguageDetector(root_str)
        language_info = detector.detect_language()
        if language_info is None:
            return create_error_result(
                "Could not detect project language. Please specify language parameter."
            )
        return language_info
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
    excluded_files = {"models.py"}

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
