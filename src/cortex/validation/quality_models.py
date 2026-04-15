"""Quality, duplication, and link-related validation models."""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.models import DictLikeModel
from cortex.core.pydantic_extra import EXTRA_ALLOW, EXTRA_FORBID
from cortex.structure.models import HealthGrade

from .schema_models import QualityConfigModel, QualityWeightsModel


class ValidationSeverity(str, Enum):
    """Validation error severity."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class QualityHealthStatus(str, Enum):
    """Quality score health status."""

    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"


class FileMetadataForQuality(BaseModel):
    """File metadata used in quality calculations."""

    model_config = ConfigDict(extra=EXTRA_ALLOW, validate_assignment=True)

    last_modified: str | None = Field(
        default=None,
        description="ISO timestamp of last modification",
    )
    token_count: int = Field(default=0, ge=0, description="Token count")
    size_bytes: int = Field(default=0, ge=0, description="File size in bytes")
    read_count: int = Field(default=0, ge=0, description="Number of reads")
    write_count: int = Field(default=0, ge=0, description="Number of writes")


class DuplicateEntryData(BaseModel):
    """Duplicate entry data structure."""

    model_config = ConfigDict(extra=EXTRA_ALLOW, validate_assignment=True)

    file: str = Field(default="", description="File name")
    section: str = Field(default="", description="Section name")
    content: str = Field(default="", description="Content")


class DuplicationDataModel(BaseModel):
    """Duplication scan result data for quality calculations."""

    model_config = ConfigDict(extra=EXTRA_ALLOW, validate_assignment=True)

    duplicates_found: int = Field(
        default=0,
        ge=0,
        description="Number of duplicates found",
    )
    exact_duplicates: list[DuplicateEntryData] = Field(
        default_factory=lambda: list[DuplicateEntryData](),
        description="Exact duplicate entries",
    )
    similar_content: list[DuplicateEntryData] = Field(
        default_factory=lambda: list[DuplicateEntryData](),
        description="Similar content entries",
    )


class LinkValidationErrorData(BaseModel):
    """Link validation error data structure."""

    model_config = ConfigDict(extra=EXTRA_ALLOW, validate_assignment=True)

    file: str = Field(default="", description="File name")
    target: str = Field(default="", description="Link target")
    error: str = Field(default="", description="Error message")


class LinkValidationDataModel(BaseModel):
    """Link validation result data for quality calculations."""

    model_config = ConfigDict(extra=EXTRA_ALLOW, validate_assignment=True)

    validation_errors: list[LinkValidationErrorData] = Field(
        default_factory=lambda: list[LinkValidationErrorData](),
        description="Validation errors",
    )
    validation_warnings: list[LinkValidationErrorData] = Field(
        default_factory=lambda: list[LinkValidationErrorData](),
        description="Validation warnings",
    )
    broken_links: int = Field(
        default=0,
        ge=0,
        description="Number of broken links",
    )


class SectionEntry(BaseModel):
    """Section entry for duplication detection."""

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

    file: str = Field(..., description="File name")
    section: str = Field(..., description="Section name")
    content_hash: str = Field(..., description="Content hash")


class HashMapEntry(BaseModel):
    """Entry in the hash map for duplicate detection."""

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

    file: str = Field(..., description="File name")
    section: str = Field(..., description="Section name")
    content: str = Field(..., description="Section content")


class ValidationError(BaseModel):
    """Validation error structure."""

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

    type: str = Field(description="Error type identifier")
    severity: ValidationSeverity = Field(description="Error severity level")
    message: str = Field(description="Error message")
    suggestion: str | None = Field(default=None, description="Suggested fix")


class ValidationResult(BaseModel):
    """Result of file validation."""

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

    valid: bool = Field(description="Whether validation passed")
    errors: list[ValidationError] = Field(
        default_factory=lambda: list[ValidationError](),
        description="Validation errors",
    )
    warnings: list[ValidationError] = Field(
        default_factory=lambda: list[ValidationError](),
        description="Validation warnings",
    )
    score: int = Field(ge=0, le=100, description="Validation score 0-100")


class DuplicateEntry(DictLikeModel):
    """Duplicate content entry."""

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

    file1: str = Field(description="First file name")
    section1: str = Field(description="First section name")
    file2: str = Field(description="Second file name")
    section2: str = Field(description="Second section name")
    similarity: float = Field(
        ge=0.0,
        le=1.0,
        description="Similarity score 0.0-1.0",
    )
    type: str = Field(description="Duplicate type (exact or similar)")
    suggestion: str = Field(description="Refactoring suggestion")


class DuplicationScanResult(DictLikeModel):
    """Result of duplication scan across files."""

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

    duplicates_found: int = Field(
        ge=0,
        description="Total number of duplicates found",
    )
    exact_duplicates: list[DuplicateEntry] = Field(
        default_factory=lambda: list[DuplicateEntry](),
        description="Exact duplicate entries",
    )
    similar_content: list[DuplicateEntry] = Field(
        default_factory=lambda: list[DuplicateEntry](),
        description="Similar content entries",
    )


class CategoryBreakdown(BaseModel):
    """Quality score category breakdown."""

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

    completeness: int = Field(ge=0, le=100, description="Completeness score")
    consistency: int = Field(ge=0, le=100, description="Consistency score")
    freshness: int = Field(ge=0, le=100, description="Freshness score")
    structure: int = Field(ge=0, le=100, description="Structure score")
    token_efficiency: int = Field(
        ge=0,
        le=100,
        description="Token efficiency score",
    )


class QualityScoreResult(BaseModel):
    """Overall Memory Bank quality score result."""

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

    overall_score: int = Field(ge=0, le=100, description="Overall quality score")
    breakdown: CategoryBreakdown = Field(
        description="Score breakdown by category",
    )
    grade: HealthGrade = Field(description="Letter grade")
    status: QualityHealthStatus = Field(description="Health status")
    issues: list[str] = Field(
        default_factory=list,
        description="Identified issues",
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description="Actionable recommendations",
    )


class FileQualityScore(BaseModel):
    """Quality score for individual file."""

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

    file_name: str = Field(description="File name")
    score: int = Field(ge=0, le=100, description="File quality score")
    grade: HealthGrade = Field(description="Letter grade")
    validation: ValidationResult = Field(description="Validation results")
    freshness: int = Field(ge=0, le=100, description="Freshness score")
    structure: int = Field(ge=0, le=100, description="Structure score")


class TransclusionFix(BaseModel):
    """Transclusion fix suggestion for duplicated files."""

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

    files: list[str] = Field(
        ...,
        min_length=2,
        description="List of files with duplicate content",
    )
    suggestion: str = Field(
        ...,
        description="Suggestion text for using transclusion",
    )
    steps: list[str] = Field(
        ...,
        min_length=1,
        description="Step-by-step instructions for applying the fix",
    )


__all__ = [
    "ValidationSeverity",
    "QualityHealthStatus",
    "FileMetadataForQuality",
    "DuplicateEntryData",
    "DuplicationDataModel",
    "LinkValidationErrorData",
    "LinkValidationDataModel",
    "SectionEntry",
    "HashMapEntry",
    "ValidationError",
    "ValidationResult",
    "DuplicateEntry",
    "DuplicationScanResult",
    "CategoryBreakdown",
    "QualityScoreResult",
    "FileQualityScore",
    "TransclusionFix",
    "QualityConfigModel",
    "QualityWeightsModel",
]
