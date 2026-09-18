"""
Models for autofix, run_docs_and_memory_bank_sync, and pre-commit check
result types.
"""

from __future__ import annotations

from enum import Enum

from pydantic import ConfigDict, Field

from cortex.core.models import DictLikeModel, JsonDict, OperationStatus
from cortex.core.pydantic_extra import EXTRA_FORBID
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
        extra=EXTRA_FORBID,
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


class FixQualityIssuesResult(ToolResultBase):
    """Result of autofix operation (success)."""

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
    """Error result for autofix operations."""

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


class ProjectConfigStatusModel(DictLikeModel):
    """Project configuration status flags."""

    model_config = ConfigDict(
        extra=EXTRA_FORBID,
        validate_assignment=True,
        validate_default=True,
    )

    memory_bank_initialized: bool = Field(
        ..., description="Whether memory bank is initialized"
    )
    structure_configured: bool = Field(
        ..., description="Whether .cortex structure is configured"
    )
    migration_needed: bool = Field(
        ..., description="Whether migration is needed from legacy formats"
    )
    tiktoken_cache_available: bool = Field(
        ..., description="Whether tiktoken cache is available"
    )
