"""Pre-commit models and enums.

Extracted from pre_commit_helpers to keep modules under 400 lines.
"""

from enum import Enum
from typing import cast

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.models import OperationStatus
from cortex.core.pydantic_extra import EXTRA_FORBID
from cortex.services.framework_adapters.base import CheckResult, TestResult


class PreCommitCheck(str, Enum):
    """Fixed set of pre-commit check names. Use instead of raw strings."""

    FIX_ERRORS = "fix_errors"
    FIX_QUALITY = "fix_quality"
    FORMAT = "format"
    FORMAT_CI_PARITY = "format_ci_parity"
    SYNAPSE_FORMAT = "synapse_format"
    SYNAPSE_LINT = "synapse_lint"
    TYPE_CHECK = "type_check"
    QUALITY = "quality"
    SPELLING = "spelling"
    TEST_NAMING = "test_naming"
    CHECK_ASYNC_TESTS = "check_async_tests"
    TESTS = "tests"
    EVAL_FAST = "eval_fast"


DEFAULT_CHECKS: list[PreCommitCheck] = [
    PreCommitCheck.FIX_ERRORS,
    PreCommitCheck.QUALITY,
    PreCommitCheck.FORMAT,
    PreCommitCheck.SYNAPSE_FORMAT,
    PreCommitCheck.SYNAPSE_LINT,
    PreCommitCheck.TYPE_CHECK,
    PreCommitCheck.TESTS,
]


class FileSizeViolation(BaseModel):
    """File size violation details."""

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

    file: str = Field(description="File path")
    lines: int = Field(ge=0, description="Number of lines")
    max_lines: int = Field(ge=0, description="Maximum allowed lines")
    excess: int = Field(ge=0, description="Excess lines over limit")


class FunctionLengthViolation(BaseModel):
    """Function length violation details."""

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

    file: str = Field(description="File path")
    function: str = Field(description="Function name")
    line: int = Field(ge=1, description="Line number")
    lines: int = Field(ge=0, description="Number of lines")
    max_lines: int = Field(ge=0, description="Maximum allowed lines")
    excess: int = Field(ge=0, description="Excess lines over limit")


class QualityCheckResult(BaseModel):
    """Result of quality check including file size and function length."""

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

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

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

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

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

    status: OperationStatus = Field(description="Operation status")
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
