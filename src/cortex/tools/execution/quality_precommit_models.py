"""
Models for execute_pre_commit_checks, fix_quality_issues, run_preflight_checks,
run_docs_and_memory_bank_sync, cleanup_metadata_index, and pre-commit result types.
"""

from __future__ import annotations

from enum import Enum

from pydantic import ConfigDict, Field

from cortex.core.models import DictLikeModel, JsonDict, OperationStatus
from cortex.tools.models_base import (
    ErrorResultBase,
    StrictBaseModel,
    ToolResultBase,
    ToolResultStatus,
)


class CheckStatus(str, Enum):
    """Status of a single pre-commit check."""

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


class CheckResult(DictLikeModel):
    """Result of a single pre-commit check."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        validate_default=True,
    )

    status: CheckStatus
    errors: int | None = None
    warnings: int | None = None
    message: str | None = None
    files_formatted: int | None = None
    score: float | None = None
    tests_run: int | None = None
    tests_passed: int | None = None
    coverage: float | None = None


class CheckStats(StrictBaseModel):
    """Statistics for pre-commit checks."""

    total_errors: int
    total_warnings: int
    files_modified: list[str] = Field(default_factory=list)
    checks_performed: list[str] = Field(default_factory=list)


class ExecutePreCommitChecksResult(ToolResultBase):
    """Result of execute_pre_commit_checks operation (success)."""

    status: ToolResultStatus = Field(default=ToolResultStatus.SUCCESS)
    language: str
    checks: dict[str, CheckResult] = Field(default_factory=dict)
    stats: CheckStats


class ExecutePreCommitChecksErrorResult(ErrorResultBase):
    """Error result for execute_pre_commit_checks operations."""

    language: str | None = None


ExecutePreCommitChecksResultUnion = (
    ExecutePreCommitChecksResult | ExecutePreCommitChecksErrorResult
)


class FixQualityIssuesResult(ToolResultBase):
    """Result of fix_quality_issues operation (success)."""

    status: ToolResultStatus = Field(default=ToolResultStatus.SUCCESS)
    errors_fixed: int
    warnings_fixed: int
    formatting_issues_fixed: int
    markdown_issues_fixed: int
    type_errors_fixed: int
    files_modified: list[str] = Field(default_factory=list)
    remaining_issues: list[str] = Field(default_factory=list)
    error_message: str | None = None


class FixQualityIssuesErrorResult(ErrorResultBase):
    """Error result for fix_quality_issues operations."""

    errors_fixed: int = 0
    warnings_fixed: int = 0
    formatting_issues_fixed: int = 0
    markdown_issues_fixed: int = 0
    type_errors_fixed: int = 0
    files_modified: list[str] = Field(default_factory=list)
    remaining_issues: list[str] = Field(default_factory=list)
    error_message: str | None = None


FixQualityIssuesResultUnion = FixQualityIssuesResult | FixQualityIssuesErrorResult


class PreflightCheckSummary(StrictBaseModel):
    """Summary information for a single preflight check."""

    name: str = Field(..., min_length=1, description="Name of the check or phase step")
    status: OperationStatus = Field(
        ..., description="Check status: success when no errors, error otherwise"
    )
    errors: int | None = Field(
        default=None, ge=0, description="Number of errors reported by the check"
    )
    warnings: int | None = Field(
        default=None, ge=0, description="Number of warnings reported by the check"
    )
    message: str | None = Field(
        default=None,
        description="Optional human-readable message or first-line summary for the check",
    )


class RunPreflightChecksResult(ToolResultBase):
    """Result of run_preflight_checks operation (success)."""

    status: ToolResultStatus = Field(default=ToolResultStatus.SUCCESS)
    preflight_passed: bool = Field(
        ...,
        description=(
            "True when all required preflight checks passed with zero errors, "
            "False when any check reports errors but the tool completed successfully"
        ),
    )
    language: str | None = Field(
        default=None,
        description="Detected project language used for pre-commit checks, if any",
    )
    checks: list[PreflightCheckSummary] = Field(
        default_factory=lambda: list[PreflightCheckSummary](),
        description="Per-check summaries for preflight run (including markdown lint)",
    )
    execute_result: JsonDict | None = Field(
        default=None,
        description=(
            "Raw execute_pre_commit_checks result for detailed inspection. "
            "Shape matches ExecutePreCommitChecksResultUnion."
        ),
    )
    markdown_result: JsonDict | None = Field(
        default=None,
        description=(
            "Raw fix_markdown_lint result for detailed inspection. "
            "Shape matches FixMarkdownLintResultUnion."
        ),
    )


class RunPreflightChecksErrorResult(ErrorResultBase):
    """Error result for run_preflight_checks operations."""

    language: str | None = Field(
        default=None,
        description="Detected project language if available when the error occurred",
    )
    execute_result: JsonDict | None = Field(
        default=None,
        description="Partial execute_pre_commit_checks result, when available",
    )
    markdown_result: JsonDict | None = Field(
        default=None,
        description="Partial fix_markdown_lint result, when available",
    )


RunPreflightChecksResultUnion = RunPreflightChecksResult | RunPreflightChecksErrorResult


class DocsAndMemoryBankSyncResult(ToolResultBase):
    """Result of run_docs_and_memory_bank_sync operation (success)."""

    status: ToolResultStatus = Field(default=ToolResultStatus.SUCCESS)
    docs_phase_passed: bool = Field(
        ...,
        description=(
            "True when all documentation and memory bank validations passed with "
            "zero errors, False when any validation reports errors but the tool "
            "completed successfully"
        ),
    )
    checks: list[PreflightCheckSummary] = Field(
        default_factory=lambda: list[PreflightCheckSummary](),
        description=(
            "Per-check summaries for documentation and memory bank validations "
            "(timestamps, roadmap_sync, etc.)"
        ),
    )
    timestamps_result: JsonDict | None = Field(
        default=None,
        description=(
            "Raw timestamps validation result for detailed inspection. "
            "Shape matches validate(check_type='timestamps') response."
        ),
    )
    roadmap_sync_result: JsonDict | None = Field(
        default=None,
        description=(
            "Raw roadmap_sync validation result for detailed inspection. "
            "Shape matches validate(check_type='roadmap_sync') response."
        ),
    )


class DocsAndMemoryBankSyncErrorResult(ErrorResultBase):
    """Error result for run_docs_and_memory_bank_sync operations."""

    timestamps_result: JsonDict | None = Field(
        default=None,
        description="Partial timestamps validation result, when available",
    )
    roadmap_sync_result: JsonDict | None = Field(
        default=None,
        description="Partial roadmap_sync validation result, when available",
    )


DocsAndMemoryBankSyncResultUnion = (
    DocsAndMemoryBankSyncResult | DocsAndMemoryBankSyncErrorResult
)


class CleanupMetadataIndexResult(ToolResultBase):
    """Result of cleanup_metadata_index operation (success)."""

    status: ToolResultStatus = Field(default=ToolResultStatus.SUCCESS)
    dry_run: bool
    stale_files_found: int
    stale_files: list[str] = Field(default_factory=list)
    entries_cleaned: int
    message: str


class CleanupMetadataIndexErrorResult(ErrorResultBase):
    """Error result for cleanup_metadata_index operations."""


CleanupMetadataIndexResultUnion = (
    CleanupMetadataIndexResult | CleanupMetadataIndexErrorResult
)


class ProjectConfigStatusModel(DictLikeModel):
    """Project configuration status flags."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        validate_default=True,
    )

    memory_bank_initialized: bool = Field(
        ..., description="Whether memory bank is initialized"
    )
    structure_configured: bool = Field(
        ..., description="Whether .cortex structure is configured"
    )
    cursor_integration_configured: bool = Field(
        ..., description="Whether Cursor integration is configured"
    )
    migration_needed: bool = Field(
        ..., description="Whether migration is needed from legacy formats"
    )
    tiktoken_cache_available: bool = Field(
        ..., description="Whether tiktoken cache is available"
    )


class PreCommitCheckResult(StrictBaseModel):
    """Result of a single pre-commit check."""

    passed: bool = Field(..., description="Whether check passed")
    errors: int = Field(default=0, ge=0, description="Number of errors")
    warnings: int = Field(default=0, ge=0, description="Number of warnings")
    files_modified: list[str] = Field(
        default_factory=list, description="Files modified by this check"
    )
    output: str | None = Field(default=None, description="Check output")


class PreCommitResultModel(StrictBaseModel):
    """Result of pre-commit checks execution."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
    )

    status: OperationStatus = Field(..., description="Operation status")
    language: str | None = Field(None, description="Detected language")
    checks_performed: list[str] = Field(
        default_factory=list, description="Checks performed"
    )
    results: dict[str, PreCommitCheckResult] = Field(
        default_factory=dict, description="Results by check type"
    )
    total_errors: int = Field(default=0, ge=0, description="Total errors")
    total_warnings: int = Field(default=0, ge=0, description="Total warnings")
    files_modified: list[str] = Field(
        default_factory=list, description="Files modified"
    )
    success: bool = Field(default=True, description="Whether checks succeeded")
    error: str | None = Field(None, description="Error message if status is error")
    error_type: str | None = Field(None, description="Error type if status is error")
