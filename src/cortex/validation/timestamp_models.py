"""Timestamp validation models.

These models were originally defined in `validation.models` and are now
grouped here by domain (timestamps) as part of Phase 81.
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.models import OperationStatus


class CheckTypeTimestamps(str, Enum):
    """Check type for timestamp validation."""

    TIMESTAMPS = "timestamps"


class TimestampViolationModel(BaseModel):
    """Timestamp format violation."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    line: int = Field(..., ge=1, description="Line number")
    content: str = Field(..., description="Line content (truncated)")
    timestamp: str = Field(..., description="Timestamp found")
    issue: str = Field(..., description="Issue description")


class TimestampScanResult(BaseModel):
    """Result of scanning content for timestamps."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    valid_count: int = Field(..., ge=0, description="Number of valid timestamps")
    invalid_format_count: int = Field(
        ...,
        ge=0,
        description="Number of invalid format timestamps",
    )
    invalid_with_time_count: int = Field(
        ...,
        ge=0,
        description="Number of timestamps with time components",
    )
    invalid_year_count: int = Field(
        default=0,
        ge=0,
        description=(
            "Number of timestamps with year outside allowed range " "(current ± 1)"
        ),
    )
    violations: list[TimestampViolationModel] = Field(
        default_factory=lambda: list[TimestampViolationModel](),
        description="Violation details (limited to 20)",
    )


class FileTimestampResultModel(BaseModel):
    """Timestamp validation result for a single file."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    valid_count: int = Field(..., ge=0, description="Number of valid timestamps")
    invalid_format_count: int = Field(
        ...,
        ge=0,
        description="Number of invalid format timestamps",
    )
    invalid_with_time_count: int = Field(
        ...,
        ge=0,
        description="Number of timestamps with time components",
    )
    violations: list[TimestampViolationModel] = Field(
        default_factory=lambda: list[TimestampViolationModel](),
        description="Violation details",
    )
    valid: bool = Field(..., description="Whether file passes validation")


class SingleFileTimestampResult(BaseModel):
    """Result of timestamp validation for a single file."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    status: OperationStatus = Field(..., description="Operation status")
    check_type: CheckTypeTimestamps = Field(
        default=CheckTypeTimestamps.TIMESTAMPS,
        description="Type of check",
    )
    file_name: str | None = Field(
        default=None,
        description="File name validated",
    )
    valid_count: int = Field(
        default=0,
        ge=0,
        description="Number of valid timestamps",
    )
    invalid_format_count: int = Field(
        default=0,
        ge=0,
        description="Number of invalid format timestamps",
    )
    invalid_with_time_count: int = Field(
        default=0,
        ge=0,
        description="Number of timestamps with time components",
    )
    violations: list[TimestampViolationModel] = Field(
        default_factory=lambda: list[TimestampViolationModel](),
        description="Violation details",
    )
    valid: bool = Field(
        default=True,
        description="Whether validation passed",
    )
    error: str | None = Field(
        default=None,
        description="Error message if status=error",
    )


class AllFilesTimestampResult(BaseModel):
    """Result of timestamp validation for all files."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    status: OperationStatus = Field(
        default=OperationStatus.SUCCESS,
        description="Operation status",
    )
    check_type: CheckTypeTimestamps = Field(
        default=CheckTypeTimestamps.TIMESTAMPS,
        description="Type of check",
    )
    total_valid: int = Field(..., ge=0, description="Total valid timestamps")
    total_invalid_format: int = Field(
        ...,
        ge=0,
        description="Total invalid format timestamps",
    )
    total_invalid_with_time: int = Field(
        ...,
        ge=0,
        description="Total timestamps with time components",
    )
    files_valid: bool = Field(
        ...,
        description="Whether all files pass validation",
    )
    results: dict[str, FileTimestampResultModel] = Field(
        default_factory=dict,
        description="Results by file name",
    )
    valid: bool = Field(..., description="Whether overall validation passed")


__all__ = [
    "CheckTypeTimestamps",
    "TimestampViolationModel",
    "TimestampScanResult",
    "FileTimestampResultModel",
    "SingleFileTimestampResult",
    "AllFilesTimestampResult",
]
