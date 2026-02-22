"""
Pydantic Models for MCP Tool Return Types

This module defines Pydantic models for all Cortex MCP tool return types,
enabling FastMCP 2.0 structured output with better schema generation,
automatic validation, and improved IDE support.

All models follow Pydantic v2 best practices:
- Use `model_config` instead of `class Config` (Pydantic v2 style)
- `extra="forbid"` to prevent extra fields and catch typos
- `validate_assignment=True` for validation on attribute assignment
- Field constraints (ge, le, min_length, etc.) for data validation
- Comprehensive Field descriptions for API documentation
- Base class with shared configuration (ToolResultBase)
- Operation-specific models for different tool behaviors
- Optional fields with None defaults for conditional responses

Design principles:
- Single responsibility: Each model represents one domain concept
- Type precision: Use concrete types (list[str], dict[str, int]) over generics
- Validation: Leverage Field() constraints for business rules
- Documentation: All fields have descriptions for schema generation
"""

from __future__ import annotations

from typing import Literal

from pydantic import ConfigDict, Field

from cortex.core.constants import MemoryBankFile
from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.models import (
    ConnectionHealth,
    DictLikeModel,
    HealthMetrics,
    JsonDict,
    OperationStatus,
)
from cortex.core.token_counter import TokenCounter
from cortex.core.version_manager import VersionManager

# Re-export ManagersDict for convenience
from cortex.managers.types import ManagersDict
from cortex.validation.models import (
    AllFilesTimestampResult,
    InfrastructureValidationResultModel,
    SingleFileTimestampResult,
)

from .models_base import (
    ErrorResultBase,
    StrictBaseModel,
    ToolResultBase,
)
from .session_models import (
    CheckTaskAvailableResult,
    ClaimTaskErrorResult,
    ClaimTaskResult,
    ConcurrentSession,
    GitStatusSummary,
    InProgressTask,
    ListActiveTasksResult,
    ReleaseTaskResult,
    SessionBrief,
    SessionHandoff,
    SessionHealthSummary,
    SessionRegistryResult,
    SessionStartErrorResult,
    SessionStartResult,
    SessionStartResultUnion,
    TaskLock,
)
from .validation_result_models import (
    ValidateDuplicationsResult,
    ValidateErrorResult,
    ValidateInfrastructureResult,
    ValidateQualityAllResult,
    ValidateQualitySingleResult,
    ValidateRoadmapSyncResult,
    ValidateSchemaAllResult,
    ValidateSchemaSingleResult,
    ValidateTimestampsResult,
)

__all__ = [
    "ManagersDict",
    # Session / task locking / registry (re-exported from session_models)
    "CheckTaskAvailableResult",
    "ClaimTaskErrorResult",
    "ClaimTaskResult",
    "ConcurrentSession",
    "GitStatusSummary",
    "InProgressTask",
    "ListActiveTasksResult",
    "ReleaseTaskResult",
    "SessionBrief",
    "SessionHandoff",
    "SessionHealthSummary",
    "SessionRegistryResult",
    "SessionStartErrorResult",
    "SessionStartResult",
    "SessionStartResultUnion",
    "TaskLock",
]


# ============================================================================
# File Operations Models (manage_file)
# ============================================================================


class FileMetadataSection(StrictBaseModel):
    """Section information in file metadata."""

    heading: str = Field(..., min_length=1, description="Section heading text")
    level: int = Field(..., ge=1, description="Heading level (1-6)")


class FileVersionEntry(StrictBaseModel):
    """Version history entry."""

    version: int = Field(..., ge=1, description="Version number (1-based)")
    timestamp: str = Field(..., min_length=1, description="ISO timestamp")
    change_type: str | None = Field(None, description="Type of change")
    change_description: str | None = Field(None, description="Description of change")
    size_bytes: int | None = Field(None, ge=0, description="File size in bytes")
    token_count: int | None = Field(None, ge=0, description="Token count")


class FileMetrics(StrictBaseModel):
    """Computed metrics for a file (size, tokens, hash)."""

    size_bytes: int = Field(..., ge=0, description="File size in bytes")
    token_count: int = Field(..., ge=0, description="Token count")
    content_hash: str = Field(..., min_length=1, description="Content hash")


class FileMetadata(StrictBaseModel):
    """File metadata structure."""

    size_bytes: int = Field(..., ge=0, description="File size in bytes")
    token_count: int = Field(..., ge=0, description="Token count")
    content_hash: str = Field(..., min_length=1, description="Content hash")
    sections: list[FileMetadataSection] = Field(
        default_factory=lambda: list[FileMetadataSection](),
        description="File sections with headings",
    )
    version_history: list[FileVersionEntry] = Field(
        default_factory=lambda: list[FileVersionEntry](),
        description="Version history entries",
    )


class ManageFileReadResult(ToolResultBase):
    """Result of manage_file read operation."""

    status: Literal["success"] = Field(default="success")
    file_name: str = Field(..., min_length=1, description="Name of the file")
    content: str = Field(..., description="File content")
    metadata: FileMetadata | None = Field(None, description="Optional file metadata")


class ManageFileWriteResult(ToolResultBase):
    """Result of manage_file write operation."""

    status: Literal["success"] = Field(default="success")
    file_name: str = Field(..., min_length=1, description="Name of the file")
    message: str = Field(..., min_length=1, description="Operation message")
    snapshot_id: str | None = Field(None, description="Snapshot ID if created")
    version: int | None = Field(None, ge=1, description="File version number")
    tokens: int | None = Field(None, ge=0, description="Token count")


class ManageFileMetadataResult(ToolResultBase):
    """Result of manage_file metadata operation."""

    status: Literal["success", "warning"] = Field(default="success")
    file_name: str
    metadata: FileMetadata | None = None
    message: str | None = None  # Only for warning status


class ManageFileErrorResult(ErrorResultBase):
    """Error result for manage_file operations."""

    file_name: str | None = None
    available_files: list[str] = Field(default_factory=list)
    suggestion: str | None = None
    valid_operations: list[str] = Field(default_factory=list)


# Union type for manage_file return (handled by operation type)
ManageFileResult = (
    ManageFileReadResult
    | ManageFileWriteResult
    | ManageFileMetadataResult
    | ManageFileErrorResult
)

# Union type for validate return (includes validation module models)
ValidateResult = (
    ValidateSchemaSingleResult
    | ValidateSchemaAllResult
    | ValidateDuplicationsResult
    | ValidateQualitySingleResult
    | ValidateQualityAllResult
    | ValidateInfrastructureResult
    | ValidateTimestampsResult
    | ValidateRoadmapSyncResult
    | ValidateErrorResult
    | SingleFileTimestampResult
    | AllFilesTimestampResult
    | InfrastructureValidationResultModel
)


# ============================================================================
# rollback_file_version Models
# ============================================================================


class RollbackFileVersionResult(ToolResultBase):
    """Result of rollback_file_version operation (success)."""

    status: Literal["success"] = Field(default="success")
    file_name: str
    rolled_back_from_version: int
    new_version: int
    token_count: int | None = None


class RollbackFileVersionErrorResult(ErrorResultBase):
    """Error result for rollback_file_version operations."""

    file_name: str | None = None
    version: int | None = None


# Union type for rollback_file_version return
RollbackFileVersionResultUnion = (
    RollbackFileVersionResult | RollbackFileVersionErrorResult
)


# ============================================================================
# check_structure_health Models
# ============================================================================


class HealthChecks(StrictBaseModel):
    """Health check results."""

    required_directories: bool
    symlinks_valid: bool
    config_exists: bool
    files_organized: bool | None = None
    memory_bank_files: bool | None = None


class HealthInfo(StrictBaseModel):
    """Health information structure."""

    score: int
    grade: Literal["A", "B", "C", "D", "F"]
    status: Literal["healthy", "good", "fair", "warning", "critical", "not_initialized"]
    checks: HealthChecks
    issues: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class CleanupActionResult(StrictBaseModel):
    """Result of a single cleanup action."""

    action: str = Field(..., min_length=1, description="Action performed")
    stale_plans_found: int | None = Field(
        None, ge=0, description="Number of stale plans found"
    )
    files: list[str] = Field(default_factory=list, description="Files affected")
    symlinks_fixed: int | None = Field(
        None, ge=0, description="Number of symlinks fixed"
    )

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
    )


class PostCleanupHealth(StrictBaseModel):
    """Health status after cleanup."""

    score: int
    grade: Literal["A", "B", "C", "D", "F"]
    status: Literal["healthy", "good", "fair", "warning", "critical"]


class CleanupInfo(StrictBaseModel):
    """Cleanup operation information."""

    dry_run: bool
    actions_performed: list[CleanupActionResult] = Field(
        default_factory=lambda: list[CleanupActionResult]()
    )
    files_modified: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    post_cleanup_health: PostCleanupHealth | None = None


class CheckStructureHealthResult(ToolResultBase):
    """Result of check_structure_health operation (success)."""

    status: Literal["success"] = Field(default="success")
    health: HealthInfo
    summary: str
    action_required: bool
    cleanup: CleanupInfo | None = None


class CheckStructureHealthErrorResult(ErrorResultBase):
    """Error result for check_structure_health operations."""


# Union type for check_structure_health return
CheckStructureHealthResultUnion = (
    CheckStructureHealthResult | CheckStructureHealthErrorResult
)


# ============================================================================
# get_structure_info Models
# ============================================================================


class StructurePaths(StrictBaseModel):
    """Structure paths configuration."""

    cursor_dir: str
    memory_bank: str
    memory_bank_symlink: str
    plans: str
    plans_active: str
    plans_completed: str
    plans_archived: str
    rules: str
    rules_symlink: str
    config: str


class StructureExists(StrictBaseModel):
    """Structure existence status."""

    cursor_dir: bool
    memory_bank: bool
    memory_bank_symlink: bool
    plans: bool
    plans_active: bool
    plans_completed: bool
    plans_archived: bool
    rules: bool
    rules_symlink: bool
    config: bool


class SymlinkInfo(StrictBaseModel):
    """Symlink information."""

    path: str
    target: str
    valid: bool
    exists: bool


class StructureSymlinks(StrictBaseModel):
    """Structure symlinks information."""

    memory_bank: SymlinkInfo | None = None
    rules: SymlinkInfo | None = None


class StructureConfig(StrictBaseModel):
    """Structure configuration."""

    version: str
    stale_days: int
    auto_archive: bool
    symlink_targets: dict[str, str] = Field(default_factory=dict)


class HealthSummary(StrictBaseModel):
    """Health summary information."""

    score: int
    grade: Literal["A", "B", "C", "D", "F"]
    status: Literal["healthy", "good", "fair", "warning", "critical", "not_initialized"]
    initialized: bool


class StructureInfo(StrictBaseModel):
    """Complete structure information."""

    version: str
    root: str
    paths: StructurePaths
    exists: StructureExists
    symlinks: StructureSymlinks
    config: StructureConfig | None = None
    health_summary: HealthSummary


class GetStructureInfoResult(ToolResultBase):
    """Result of get_structure_info operation (success)."""

    status: Literal["success"] = Field(default="success")
    structure_info: StructureInfo
    message: str


class GetStructureInfoErrorResult(ErrorResultBase):
    """Error result for get_structure_info operations."""


# Union type for get_structure_info return
GetStructureInfoResultUnion = GetStructureInfoResult | GetStructureInfoErrorResult


# ============================================================================
# rules Models
# ============================================================================


class RulesIndexResult(StrictBaseModel):
    """Result of rules index operation."""

    indexed: int
    total_tokens: int
    cache_hit: bool
    index_time_seconds: float
    rules_folder: str
    rules_by_category: dict[str, int] = Field(default_factory=dict)


class RulesIndexOperationResult(ToolResultBase):
    """Result of rules index operation (success)."""

    status: Literal["success"] = Field(default="success")
    operation: Literal["index"]
    result: RulesIndexResult


class RuleMetadata(StrictBaseModel):
    """Metadata for a single rule."""

    language: str | None = None
    tags: list[str] = Field(default_factory=list)


class RuleInfo(StrictBaseModel):
    """Information about a single rule."""

    file: str
    category: str
    relevance_score: float
    tokens: int
    title: str | None = None
    content: str | None = None
    metadata: RuleMetadata | None = None


class RulesManagerStatus(StrictBaseModel):
    """Rules manager status information."""

    indexed_count: int
    last_indexed: str
    rules_folder: str


class RulesContext(StrictBaseModel):
    """Rules context information."""

    filtered_count: int
    truncated_count: int


class RulesGetRelevantResult(ToolResultBase):
    """Result of rules get_relevant operation (success)."""

    status: Literal["success"] = Field(default="success")
    operation: Literal["get_relevant"]
    task_description: str
    max_tokens: int
    min_relevance_score: float
    rules_count: int
    total_tokens: int
    rules: list[RuleInfo] = Field(default_factory=lambda: list[RuleInfo]())
    rules_manager_status: RulesManagerStatus | None = None
    rules_context: RulesContext | None = None
    rules_source: str | None = None


class RulesDisabledResult(ToolResultBase):
    """Result when rules indexing is disabled."""

    status: Literal["disabled"] = Field(default="disabled")
    message: str


class RulesErrorResult(ErrorResultBase):
    """Error result for rules operations."""

    operation: str | None = None
    valid_operations: list[str] = Field(default_factory=list)


# Union type for rules return
RulesResultUnion = (
    RulesIndexOperationResult
    | RulesGetRelevantResult
    | RulesDisabledResult
    | RulesErrorResult
)


# ============================================================================
# execute_pre_commit_checks Models
# ============================================================================


class CheckResult(DictLikeModel):
    """Result of a single pre-commit check."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        validate_default=True,
    )

    status: Literal["passed", "failed", "skipped", "error"]
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

    status: Literal["success"] = Field(default="success")
    language: str
    checks: dict[str, CheckResult] = Field(default_factory=dict)
    stats: CheckStats


class ExecutePreCommitChecksErrorResult(ErrorResultBase):
    """Error result for execute_pre_commit_checks operations."""

    language: str | None = None


# Union type for execute_pre_commit_checks return
ExecutePreCommitChecksResultUnion = (
    ExecutePreCommitChecksResult | ExecutePreCommitChecksErrorResult
)


# ============================================================================
# fix_quality_issues Models
# ============================================================================


class FixQualityIssuesResult(ToolResultBase):
    """Result of fix_quality_issues operation (success)."""

    status: Literal["success"] = Field(default="success")
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


# Union type for fix_quality_issues return
FixQualityIssuesResultUnion = FixQualityIssuesResult | FixQualityIssuesErrorResult


# ============================================================================
# run_preflight_checks Models
# ============================================================================


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

    status: Literal["success"] = Field(default="success")
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


# Union type for run_preflight_checks return
RunPreflightChecksResultUnion = RunPreflightChecksResult | RunPreflightChecksErrorResult


# ============================================================================
# run_docs_and_memory_bank_sync Models
# ============================================================================


class DocsAndMemoryBankSyncResult(ToolResultBase):
    """Result of run_docs_and_memory_bank_sync operation (success)."""

    status: Literal["success"] = Field(default="success")
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


# ============================================================================
# cleanup_metadata_index Models
# ============================================================================


class CleanupMetadataIndexResult(ToolResultBase):
    """Result of cleanup_metadata_index operation (success)."""

    status: Literal["success"] = Field(default="success")
    dry_run: bool
    stale_files_found: int
    stale_files: list[str] = Field(default_factory=list)
    entries_cleaned: int
    message: str


class CleanupMetadataIndexErrorResult(ErrorResultBase):
    """Error result for cleanup_metadata_index operations."""


# Union type for cleanup_metadata_index return
CleanupMetadataIndexResultUnion = (
    CleanupMetadataIndexResult | CleanupMetadataIndexErrorResult
)


# ============================================================================
# provide_feedback Models
# ============================================================================


class LearningSummary(StrictBaseModel):
    """Learning engine summary statistics."""

    total_feedback: int
    approval_rate: float
    min_confidence_threshold: float


class ProvideFeedbackResult(ToolResultBase):
    """Result of provide_feedback operation (success)."""

    status: Literal["success"] = Field(default="success")
    feedback_id: str
    learning_enabled: bool
    message: str
    learning_summary: LearningSummary | None = None


class ProvideFeedbackErrorResult(ErrorResultBase):
    """Error result for provide_feedback operations."""

    suggestion_id: str | None = None
    feedback_type: str | None = None


# Union type for provide_feedback return
ProvideFeedbackResultUnion = ProvideFeedbackResult | ProvideFeedbackErrorResult


# ============================================================================
# Synapse Tools Models
# ============================================================================


class PromptInfo(StrictBaseModel):
    """Information about a prompt."""

    file: str
    name: str
    category: str
    description: str
    keywords: list[str] = Field(default_factory=list)


class GetSynapsePromptsResult(ToolResultBase):
    """Result of get_synapse_prompts operation (success)."""

    status: Literal["success"] = Field(default="success")
    category: str | None = None
    categories: list[str] = Field(default_factory=list)
    prompts: list[PromptInfo] = Field(default_factory=lambda: list[PromptInfo]())
    total_count: int


class GetSynapsePromptsErrorResult(ErrorResultBase):
    """Error result for get_synapse_prompts operations."""


# Union type for get_synapse_prompts return
GetSynapsePromptsResultUnion = GetSynapsePromptsResult | GetSynapsePromptsErrorResult


class UpdateSynapsePromptResult(ToolResultBase):
    """Result of update_synapse_prompt operation (success)."""

    status: Literal["success"] = Field(default="success")
    category: str
    file: str
    message: str
    type: Literal["prompt"] = Field(default="prompt")
    commit_hash: str | None = None


class UpdateSynapsePromptErrorResult(ErrorResultBase):
    """Error result for update_synapse_prompt operations."""


# Union type for update_synapse_prompt return
UpdateSynapsePromptResultUnion = (
    UpdateSynapsePromptResult | UpdateSynapsePromptErrorResult
)


# ============================================================================
# fix_roadmap_corruption Models
# ============================================================================


class CorruptionMatch(StrictBaseModel):
    """A detected corruption match."""

    line_num: int = Field(
        ..., ge=1, description="Line number where corruption was found"
    )
    original: str = Field(..., min_length=1, description="Original corrupted content")
    fixed: str = Field(..., description="Fixed content")
    pattern: str = Field(
        ..., min_length=1, description="Pattern that matched the corruption"
    )

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
    )


class FixRoadmapCorruptionResult(ToolResultBase):
    """Result of fix_roadmap_corruption operation (success)."""

    status: Literal["success"] = Field(default="success")
    file_name: str
    corruption_count: int
    fixes_applied: list[CorruptionMatch] = Field(
        default_factory=lambda: list[CorruptionMatch]()
    )
    error_message: str | None = None


class FixRoadmapCorruptionErrorResult(ErrorResultBase):
    """Error result for fix_roadmap_corruption operations."""

    file_name: str
    corruption_count: int = 0
    fixes_applied: list[CorruptionMatch] = Field(
        default_factory=lambda: list[CorruptionMatch]()
    )
    error_message: str | None = None


# Union type for fix_roadmap_corruption return
FixRoadmapCorruptionResultUnion = (
    FixRoadmapCorruptionResult | FixRoadmapCorruptionErrorResult
)


# ============================================================================
# Synapse Tools Models (sync_synapse, update_synapse_rule, get_synapse_rules)
# ============================================================================


class SynapseChanges(StrictBaseModel):
    """Changes detected during sync."""

    added: list[str] = Field(default_factory=list)
    modified: list[str] = Field(default_factory=list)
    deleted: list[str] = Field(default_factory=list)


class SyncSynapseResult(ToolResultBase):
    """Result of sync_synapse operation."""

    status: Literal["success"] = Field(default="success")
    pulled: bool
    pushed: bool
    changes: SynapseChanges
    reindex_triggered: bool
    last_sync: str


class SyncSynapseErrorResult(ErrorResultBase):
    """Error result for sync_synapse operations."""


# Union type for sync_synapse return
SyncSynapseResultUnion = SyncSynapseResult | SyncSynapseErrorResult


class RuleInfoModel(StrictBaseModel):
    """Information about a rule."""

    file: str
    tokens: int
    priority: str | None = None
    relevance_score: float | None = None
    category: str | None = None


class ContextInfo(StrictBaseModel):
    """Context information for rules."""

    languages: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    task_type: str | None = None


class RulesLoaded(StrictBaseModel):
    """Loaded rules by category."""

    generic: list[RuleInfoModel] = Field(default_factory=lambda: list[RuleInfoModel]())
    language: list[RuleInfoModel] = Field(default_factory=lambda: list[RuleInfoModel]())
    local: list[RuleInfoModel] = Field(default_factory=lambda: list[RuleInfoModel]())


class GetSynapseRulesResult(ToolResultBase):
    """Result of get_synapse_rules operation."""

    status: Literal["success"] = Field(default="success")
    task_description: str
    context: ContextInfo
    rules_loaded: RulesLoaded
    total_tokens: int
    token_budget: int
    source: str
    keywords: list[str] = Field(default_factory=list)


class GetSynapseRulesErrorResult(ErrorResultBase):
    """Error result for get_synapse_rules operations."""


# Union type for get_synapse_rules return
GetSynapseRulesResultUnion = GetSynapseRulesResult | GetSynapseRulesErrorResult


class UpdateSynapseRuleResult(ToolResultBase):
    """Result of update_synapse_rule operation."""

    status: Literal["success"] = Field(default="success")
    category: str
    file: str
    message: str
    commit_hash: str | None = None


class UpdateSynapseRuleErrorResult(ErrorResultBase):
    """Error result for update_synapse_rule operations."""


# Union type for update_synapse_rule return
UpdateSynapseRuleResultUnion = UpdateSynapseRuleResult | UpdateSynapseRuleErrorResult


# ============================================================================
# Markdown Operations Models (fix_markdown_lint)
# ============================================================================


class FileResult(StrictBaseModel):
    """Result for a single file processing."""

    file: str
    fixed: bool
    errors: list[str] = Field(default_factory=list)
    error_message: str | None = None


class FixMarkdownLintResult(ToolResultBase):
    """Result of markdown lint fixing operation."""

    status: Literal["success"] = Field(default="success")
    files_processed: int
    files_fixed: int
    files_unchanged: int
    files_with_errors: int
    results: list[FileResult] = Field(default_factory=lambda: list[FileResult]())
    error_message: str | None = None


class FixMarkdownLintErrorResult(ErrorResultBase):
    """Error result for fix_markdown_lint operations."""


# Union type for fix_markdown_lint return
FixMarkdownLintResultUnion = FixMarkdownLintResult | FixMarkdownLintErrorResult


# ============================================================================
# Connection Health Models (check_mcp_connection_health)
# ============================================================================


class ConnectionHealthResult(ToolResultBase):
    """Result of connection health check."""

    status: Literal["success"] = Field(default="success")
    health: HealthMetrics


class MCPHealthCheckResponse(StrictBaseModel):
    """Parsed response from check_mcp_connection_health (for parsing only)."""

    status: OperationStatus
    health: ConnectionHealth | None = None
    error: str | None = None
    error_type: str | None = None


class ConnectionHealthErrorResult(ErrorResultBase):
    """Error result for check_mcp_connection_health operations."""


# Union type for check_mcp_connection_health return
ConnectionHealthResultUnion = ConnectionHealthResult | ConnectionHealthErrorResult


# ============================================================================
# Link Parser Models (parse_file_links)
# ============================================================================


class LinkLocation(StrictBaseModel):
    """Location of a link in a file."""

    line: int
    column: int


class LinkSummary(StrictBaseModel):
    """Summary statistics for parsed links."""

    markdown_links: int
    transclusions: int
    total: int
    unique_files: int


class ParsedMarkdownLink(StrictBaseModel):
    """Parsed markdown link information."""

    text: str = Field(..., description="Link text")
    target: str = Field(..., description="Link target path or URL")
    line: int = Field(..., ge=1, description="Line number")
    column: int = Field(default=1, ge=1, description="Column number")
    is_external: bool = Field(default=False, description="Whether link is external")


class ParsedTransclusion(StrictBaseModel):
    """Parsed transclusion reference."""

    target: str = Field(..., description="Transclusion target path")
    line: int = Field(..., ge=1, description="Line number")
    section: str | None = Field(default=None, description="Target section if specified")
    full_syntax: str = Field(..., description="Full transclusion syntax")


class ParseFileLinksResult(ToolResultBase):
    """Result of parse_file_links operation."""

    status: Literal["success"] = Field(default="success")
    file: str
    summary: LinkSummary
    markdown_links: list[ParsedMarkdownLink] = Field(
        default_factory=lambda: list[ParsedMarkdownLink]()
    )
    transclusions: list[ParsedTransclusion] = Field(
        default_factory=lambda: list[ParsedTransclusion]()
    )


class ParseFileLinksErrorResult(ErrorResultBase):
    """Error result for parse_file_links operations."""

    file: str | None = None


# Union type for parse_file_links return
ParseFileLinksResultUnion = ParseFileLinksResult | ParseFileLinksErrorResult


# ============================================================================
# Project Config Status Models (from config_status.py)
# ============================================================================


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


# ============================================================================
# Pre-Commit Result Models (from pre_commit_tools.py)
# ============================================================================


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


# ============================================================================
# Context Analysis Models
# ============================================================================


class ContextUsageEntry(StrictBaseModel):
    """Structure for a single context usage analysis entry."""

    session_id: str = Field(..., description="Session identifier")
    timestamp: str = Field(..., description="Timestamp of the load_context call")
    task_description: str = Field(..., description="Task description")
    token_budget: int = Field(..., ge=0, description="Token budget allocated")
    total_tokens: int = Field(..., ge=0, description="Total tokens used")
    utilization: float = Field(
        ..., ge=0.0, le=1.0, description="Token utilization ratio"
    )
    files_selected: int = Field(..., ge=0, description="Number of files selected")
    files_excluded: int = Field(..., ge=0, description="Number of files excluded")
    avg_relevance_score: float = Field(
        ..., ge=0.0, le=1.0, description="Average relevance score"
    )
    files_with_high_relevance: int = Field(
        ..., ge=0, description="Number of files with relevance score > 0.7"
    )
    files_with_low_relevance: int = Field(
        ..., ge=0, description="Number of files with relevance score < 0.3"
    )
    selected_file_names: list[str] | None = Field(
        None, description="List of selected file names for tracking"
    )
    relevance_by_file: dict[str, float] | None = Field(
        None, description="Relevance scores by file name"
    )
    role: str | None = Field(
        default=None,
        description="Agent role (feature/quality/testing/docs/planning/debugging/review)",
    )


class TaskTypeInsight(StrictBaseModel):
    """Insights for a specific task type."""

    calls_count: int = Field(
        ..., ge=0, description="Number of calls for this task type"
    )
    recommended_budget: int = Field(..., ge=0, description="Recommended token budget")
    essential_files: list[str] = Field(
        default_factory=list, description="Essential files for this task type"
    )
    avg_utilization: float = Field(
        ..., ge=0.0, le=1.0, description="Average utilization"
    )
    avg_relevance: float = Field(
        ..., ge=0.0, le=1.0, description="Average relevance score"
    )
    notes: str = Field(..., description="Notes and recommendations")


class FileEffectiveness(StrictBaseModel):
    """Effectiveness tracking for a specific file."""

    times_selected: int = Field(
        ..., ge=0, description="Number of times file was selected"
    )
    avg_relevance: float = Field(
        ..., ge=0.0, le=1.0, description="Average relevance score"
    )
    task_types_used: list[str] = Field(
        default_factory=list, description="Task types that used this file"
    )
    recommendation: str = Field(..., description="Recommendation for this file")


class ContextInsights(StrictBaseModel):
    """Actionable insights derived from statistics."""

    task_type_recommendations: dict[str, TaskTypeInsight] = Field(
        default_factory=dict, description="Recommendations by task type"
    )
    file_effectiveness: dict[str, FileEffectiveness] = Field(
        default_factory=dict, description="Effectiveness by file"
    )
    learned_patterns: list[str] = Field(
        default_factory=list, description="Learned usage patterns"
    )
    budget_recommendations: dict[str, int] = Field(
        default_factory=dict, description="Budget recommendations by task type"
    )
    role_recommendations: dict[str, TaskTypeInsight] = Field(
        default_factory=dict,
        description="Recommendations by agent role (feature/quality/testing/docs/planning/debugging/review)",
    )
    role_budget_recommendations: dict[str, int] = Field(
        default_factory=dict, description="Budget recommendations by agent role"
    )


class ContextUsageStatistics(StrictBaseModel):
    """Structure for aggregated context usage statistics."""

    last_updated: str = Field(..., description="Last update timestamp")
    total_sessions_analyzed: int = Field(
        ..., ge=0, description="Total sessions analyzed"
    )
    total_load_context_calls: int = Field(
        ..., ge=0, description="Total load_context calls"
    )
    avg_token_utilization: float = Field(
        ..., ge=0.0, le=1.0, description="Average token utilization"
    )
    avg_files_selected: float = Field(..., ge=0.0, description="Average files selected")
    avg_relevance_score: float = Field(
        ..., ge=0.0, le=1.0, description="Average relevance score"
    )
    common_task_patterns: dict[str, int] = Field(
        default_factory=dict, description="Common task patterns and their counts"
    )
    insights: ContextInsights | None = Field(
        None, description="Actionable insights derived from statistics"
    )
    entries: list[ContextUsageEntry] = Field(
        default_factory=lambda: list[ContextUsageEntry](),
        description="Individual context usage entries",
    )


class SessionStats(StrictBaseModel):
    """Statistics for a single session's context usage."""

    calls_count: int = Field(..., ge=0, description="Number of load_context calls")
    avg_token_utilization: float = Field(
        ..., ge=0.0, le=1.0, description="Average token utilization"
    )
    avg_files_selected: float = Field(..., ge=0.0, description="Average files selected")
    avg_relevance_score: float = Field(
        ..., ge=0.0, le=1.0, description="Average relevance score"
    )
    task_patterns: dict[str, int] = Field(
        default_factory=dict, description="Task patterns and their counts"
    )


# ============================================================================
# Cleanup Report Models (for phase8_structure.py)
# ============================================================================


class CleanupReport(StrictBaseModel):
    """Complete cleanup operation report."""

    dry_run: bool = Field(description="Whether this was a dry run")
    actions_performed: list[CleanupActionResult] = Field(
        default_factory=lambda: list[CleanupActionResult](),
        description="List of actions performed",
    )
    files_modified: list[str] = Field(
        default_factory=list, description="List of files modified"
    )
    recommendations: list[str] = Field(
        default_factory=list, description="Recommendations for further cleanup"
    )
    post_cleanup_health: JsonDict = Field(
        description="Health check result after cleanup"
    )

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


# ============================================================================
# Context Analysis Result Models (for context_analysis_operations.py)
# ============================================================================


class CurrentSessionAnalysisResult(StrictBaseModel):
    """Result of analyzing current session's context usage."""

    status: Literal["success", "no_data"] = Field(description="Analysis status")
    session_id: str | None = Field(None, description="Current session ID")
    current_session: JsonDict | None = Field(
        None, description="Current session data (calls, statistics, entries)"
    )
    global_statistics_updated: bool | None = Field(
        None, description="Whether global statistics were updated"
    )
    new_entries_added: int | None = Field(
        None, ge=0, description="Number of new entries added"
    )
    total_sessions: int | None = Field(
        None, ge=0, description="Total sessions analyzed"
    )
    total_entries: int | None = Field(None, ge=0, description="Total entries")
    insights: JsonDict | None = Field(None, description="Context insights")
    message: str | None = Field(None, description="Status message for no_data case")

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class SessionLogsAnalysisResult(StrictBaseModel):
    """Result of analyzing session logs."""

    status: Literal["success", "no_data"] = Field(description="Analysis status")
    new_sessions_analyzed: int | None = Field(
        None, ge=0, description="Number of new sessions analyzed"
    )
    new_entries_added: int | None = Field(
        None, ge=0, description="Number of new entries added"
    )
    total_sessions: int | None = Field(
        None, ge=0, description="Total sessions analyzed"
    )
    total_entries: int | None = Field(None, ge=0, description="Total entries")
    statistics: JsonDict | None = Field(
        None, description="Aggregated statistics (avg_token_utilization, etc.)"
    )
    insights: JsonDict | None = Field(None, description="Context insights")
    message: str | None = Field(None, description="Status message for no_data case")

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class ContextStatisticsResult(StrictBaseModel):
    """Result of getting context usage statistics."""

    status: Literal["success", "no_data"] = Field(description="Status")
    last_updated: str | None = Field(None, description="Last update timestamp")
    total_sessions: int | None = Field(None, ge=0, description="Total sessions")
    total_calls: int | None = Field(None, ge=0, description="Total load_context calls")
    statistics: JsonDict | None = Field(
        None, description="Aggregated statistics (avg_token_utilization, etc.)"
    )
    insights: JsonDict | None = Field(None, description="Context insights")
    recent_entries: list[JsonDict] | None = Field(
        None, description="Last 10 context usage entries"
    )
    message: str | None = Field(None, description="Status message for no_data case")

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


# ============================================================================
# Rules Execution Models (for synapse_tools.py)
# ============================================================================


class RulesExecutionResult(StrictBaseModel):
    """Result of executing rules with context."""

    status: OperationStatus = Field(description="Execution status")
    task_description: str | None = Field(None, description="Task description")
    context: JsonDict | None = Field(None, description="Context information")
    rules_loaded: JsonDict | None = Field(
        None, description="Rules loaded (generic, language, local)"
    )
    total_tokens: int | None = Field(None, ge=0, description="Total tokens used")
    token_budget: int | None = Field(None, ge=0, description="Token budget")
    source: str | None = Field(None, description="Rules source")
    error: str | None = Field(None, description="Error message if status is error")

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


# ============================================================================
# Learned Patterns Models (for configuration_operations.py)
# ============================================================================


class LearnedPatternsResult(StrictBaseModel):
    """Result containing learned patterns dictionary."""

    patterns: dict[str, JsonDict] = Field(
        default_factory=dict, description="Dictionary of pattern_id -> pattern data"
    )

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


# ============================================================================
# Manager Initialization Models (for file_operations.py)
# ============================================================================


class ManagersInitResult(StrictBaseModel):
    """Result of initializing managers for file operations."""

    root: str = Field(description="Project root path")
    fs: FileSystemManager = Field(description="FileSystemManager instance")
    index: MetadataIndex = Field(description="MetadataIndex instance")
    tokens: TokenCounter = Field(description="TokenCounter instance")
    versions: VersionManager = Field(description="VersionManager instance")

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        arbitrary_types_allowed=True,
    )


# ============================================================================
# Roadmap Entry Addition Models (for roadmap_operations.py)
# ============================================================================


class AddRoadmapEntryResult(StrictBaseModel):
    """Result of adding a roadmap entry."""

    status: OperationStatus = Field(description="Operation status")
    file_name: str = Field(description="File that was modified")
    message: str = Field(description="Success or error message")
    line_inserted: int | None = Field(
        None, ge=1, description="Line number where entry was inserted"
    )
    section: str | None = Field(None, description="Section where entry was added")
    error: str | None = Field(None, description="Error message if status is error")

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class RemoveRoadmapEntryResult(StrictBaseModel):
    """Result of removing a single roadmap entry (bullet line)."""

    status: OperationStatus = Field(description="Operation status")
    file_name: str = Field(description="File that was modified")
    message: str = Field(description="Success or error message")
    line_removed: int | None = Field(
        None, ge=1, description="1-based line number that was removed"
    )
    error: str | None = Field(None, description="Error message if status is error")

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class RemoveRoadmapSectionResult(StrictBaseModel):
    """Result of removing a roadmap section by heading."""

    status: OperationStatus = Field(description="Operation status")
    file_name: str = Field(description="File that was modified")
    message: str = Field(description="Success or error message")
    section_heading: str | None = Field(
        None, description="Heading text that was matched and removed"
    )
    lines_removed: int | None = Field(
        None, ge=0, description="Number of lines removed (header and content)"
    )
    error: str | None = Field(None, description="Error message if status is error")

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class AppendProgressEntryResult(StrictBaseModel):
    """Result of appending a single entry to progress.md."""

    status: OperationStatus = Field(description="Operation status")
    file_name: str = Field(
        description=f"File that was modified ({MemoryBankFile.PROGRESS})"
    )
    message: str = Field(description="Success or error message")
    line_inserted: int | None = Field(
        None, ge=1, description="1-based line number where entry was inserted"
    )
    error: str | None = Field(None, description="Error message if status is error")

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class AppendActiveContextEntryResult(StrictBaseModel):
    """Result of appending a single completed entry to activeContext.md."""

    status: OperationStatus = Field(description="Operation status")
    file_name: str = Field(
        description=f"File that was modified ({MemoryBankFile.ACTIVE_CONTEXT})"
    )
    message: str = Field(description="Success or error message")
    line_inserted: int | None = Field(
        None, ge=1, description="1-based line number where entry was inserted"
    )
    error: str | None = Field(None, description="Error message if status is error")

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


# Session types are imported at top from .session_models
