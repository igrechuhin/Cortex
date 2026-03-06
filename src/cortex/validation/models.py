"""
Pydantic models for validation module return types.

Re-exports from domain-specific modules to preserve the public API.
Consumers should use `from cortex.validation.models import ...` unchanged.
"""

from cortex.structure.models import HealthGrade
from cortex.validation.infrastructure_models import (
    CheckTypeInfrastructure,
    InfrastructureIssueModel,
    InfrastructureValidationResultModel,
    JobConfigModel,
    JobStepModel,
)
from cortex.validation.quality_models import (
    CategoryBreakdown,
    DuplicateEntry,
    DuplicateEntryData,
    DuplicationDataModel,
    DuplicationScanResult,
    FileMetadataForQuality,
    FileQualityScore,
    HashMapEntry,
    LinkValidationDataModel,
    LinkValidationErrorData,
    QualityHealthStatus,
    QualityScoreResult,
    SectionEntry,
    TransclusionFix,
    ValidationError,
    ValidationResult,
    ValidationSeverity,
)
from cortex.validation.roadmap_models import (
    RoadmapReferenceModel,
    SyncValidationResultModel,
    TodoItemModel,
)
from cortex.validation.schema_models import (
    DuplicationConfigModel,
    FileSchemaModel,
    QualityConfigModel,
    QualityWeightsModel,
    SchemasConfigModel,
    TokenBudgetConfigModel,
    ValidationConfigModel,
)
from cortex.validation.timestamp_models import (
    AllFilesTimestampResult,
    CheckTypeTimestamps,
    FileTimestampResultModel,
    SingleFileTimestampResult,
    TimestampScanResult,
    TimestampViolationModel,
)

__all__ = [
    "AllFilesTimestampResult",
    "CategoryBreakdown",
    "HealthGrade",
    "CheckTypeInfrastructure",
    "CheckTypeTimestamps",
    "DuplicateEntry",
    "DuplicateEntryData",
    "DuplicationConfigModel",
    "DuplicationDataModel",
    "DuplicationScanResult",
    "FileMetadataForQuality",
    "FileQualityScore",
    "FileSchemaModel",
    "FileTimestampResultModel",
    "HashMapEntry",
    "InfrastructureIssueModel",
    "InfrastructureValidationResultModel",
    "JobConfigModel",
    "JobStepModel",
    "LinkValidationDataModel",
    "LinkValidationErrorData",
    "QualityConfigModel",
    "QualityHealthStatus",
    "QualityScoreResult",
    "QualityWeightsModel",
    "RoadmapReferenceModel",
    "SchemasConfigModel",
    "SectionEntry",
    "SingleFileTimestampResult",
    "SyncValidationResultModel",
    "TimestampScanResult",
    "TimestampViolationModel",
    "TodoItemModel",
    "TokenBudgetConfigModel",
    "TransclusionFix",
    "ValidationConfigModel",
    "ValidationError",
    "ValidationResult",
    "ValidationSeverity",
]
