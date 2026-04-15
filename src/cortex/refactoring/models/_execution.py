"""
Refactoring execution, rollback, and reorganization models.

Extracted from refactoring/models.py for Phase 9.1.2 file size compliance.
"""

from datetime import datetime

from pydantic import ConfigDict, Field

from cortex.core.models import RiskLevel
from cortex.core.pydantic_extra import EXTRA_ALLOW, EXTRA_FORBID

from ._base import RefactoringBaseModel, RefactoringImpactMetrics
from ._enums import RefactoringStatus


class OperationParameters(RefactoringBaseModel):
    """Parameters for a refactoring operation."""

    source_file: str | None = Field(default=None, description="Source file path")
    source_files: list[str] | None = Field(
        default=None, description="Source files for multi-file operations"
    )
    destination_file: str | None = Field(
        default=None, description="Destination file path"
    )
    content: str | None = Field(default=None, description="Content to add/modify")
    new_name: str | None = Field(default=None, description="New name for rename")
    section: str | None = Field(default=None, description="Target section")
    sections: list[str] | None = Field(
        default=None, description="List of sections to operate on"
    )
    line_start: int | None = Field(default=None, ge=1, description="Start line number")
    line_end: int | None = Field(default=None, ge=1, description="End line number")
    preserve_history: bool = Field(default=True, description="Preserve version history")
    is_directory: bool = Field(
        default=False, description="Whether to create a directory"
    )


class RefactoringOperationModel(RefactoringBaseModel):
    """Single refactoring operation."""

    operation_id: str = Field(..., description="Unique operation identifier")
    operation_type: str = Field(
        ...,
        description="Type: move, rename, create, delete, modify, consolidate, split",
    )
    target_file: str = Field(..., description="Target file path")
    parameters: OperationParameters = Field(
        default_factory=OperationParameters, description="Operation parameters"
    )
    status: RefactoringStatus = Field(
        default=RefactoringStatus.PENDING, description="Operation status"
    )
    error: str | None = Field(default=None, description="Error message if failed")
    created_at: str | None = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="ISO timestamp of creation",
    )
    completed_at: str | None = Field(
        default=None, description="ISO timestamp of completion"
    )


class RefactoringExecutionModel(RefactoringBaseModel):
    """Record of a refactoring execution."""

    execution_id: str = Field(..., description="Unique execution identifier")
    suggestion_id: str = Field(..., description="Associated suggestion ID")
    approval_id: str = Field(..., description="Associated approval ID")
    operations: list[RefactoringOperationModel] = Field(
        default_factory=lambda: list[RefactoringOperationModel](),
        description="Operations performed",
    )
    status: RefactoringStatus = Field(..., description="Execution status")
    created_at: str = Field(..., description="ISO timestamp of creation")
    completed_at: str | None = Field(
        default=None, description="ISO timestamp of completion"
    )
    snapshot_id: str | None = Field(
        default=None, description="Snapshot ID for rollback"
    )
    validation_results: RefactoringImpactMetrics | None = Field(
        default=None, description="Validation results"
    )
    actual_impact: RefactoringImpactMetrics | None = Field(
        default=None, description="Actual impact"
    )
    error: str | None = Field(default=None, description="Error message if failed")


class RefactoringValidationResult(RefactoringBaseModel):
    """Result of validating a refactoring suggestion."""

    valid: bool = Field(..., description="Whether the suggestion is valid")
    issues: list[str] = Field(default_factory=list, description="Validation issues")
    warnings: list[str] = Field(default_factory=list, description="Validation warnings")
    operations_count: int = Field(default=0, ge=0, description="Number of operations")
    dry_run: bool = Field(default=True, description="Whether this was a dry run")


class RollbackRecordModel(RefactoringBaseModel):
    """Record of a rollback operation."""

    rollback_id: str = Field(..., description="Unique rollback identifier")
    execution_id: str = Field(..., description="Associated execution ID")
    created_at: str = Field(..., description="ISO timestamp of creation")
    completed_at: str | None = Field(
        default=None, description="ISO timestamp of completion"
    )
    status: RefactoringStatus = Field(
        default=RefactoringStatus.PENDING, description="Rollback status"
    )
    files_restored: list[str] = Field(
        default_factory=list, description="Files restored"
    )
    conflicts_detected: list[str] = Field(
        default_factory=list, description="Conflicts detected"
    )
    preserve_manual_edits: bool = Field(
        default=True, description="Whether to preserve manual edits"
    )
    error: str | None = Field(default=None, description="Error message if failed")


class ReorganizationActionModel(RefactoringBaseModel):
    """Represents a single reorganization action."""

    action_type: str = Field(
        ..., description="Type: move, rename, reorder, create_category"
    )
    source: str = Field(..., description="Source path")
    target: str = Field(..., description="Target path")
    reason: str = Field(..., description="Reason for action")
    dependencies_affected: list[str] = Field(
        default_factory=list, description="Dependencies affected"
    )


class ReorganizationStructure(RefactoringBaseModel):
    """Structure representation for reorganization."""

    files: list[str] = Field(default_factory=list, description="List of files")
    directories: list[str] = Field(
        default_factory=list, description="List of directories"
    )
    files_by_category: dict[str, list[str]] = Field(
        default_factory=dict, description="Files grouped by category"
    )
    max_depth: int = Field(default=0, ge=0, description="Maximum directory depth")


class MemoryBankStructureData(RefactoringBaseModel):
    """Analyzed structure data for Memory Bank reorganization."""

    model_config = ConfigDict(extra=EXTRA_ALLOW, validate_assignment=True)

    total_files: int = Field(default=0, ge=0, description="Total number of files")
    files: list[str] = Field(default_factory=list, description="List of file paths")
    organization: str = Field(
        default="flat",
        description=(
            "Organization type: flat, category_based, dependency_optimized, simplified"
        ),
    )
    categories: dict[str, list[str]] = Field(
        default_factory=dict, description="Files grouped by category"
    )
    dependency_depth: int = Field(
        default=0, ge=0, description="Maximum dependency depth"
    )
    dependency_order: list[str] = Field(
        default_factory=list, description="Optimized dependency order"
    )
    hub_files: list[str] = Field(
        default_factory=list, description="Files with many dependents (hubs)"
    )
    orphaned_files: list[str] = Field(
        default_factory=list, description="Files with no dependencies"
    )
    complexity_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Overall structural complexity 0-1"
    )


class DependencyInfo(RefactoringBaseModel):
    """Dependency information for a single file."""

    depends_on: list[str] = Field(
        default_factory=list, description="Files this file depends on"
    )
    dependents: list[str] = Field(
        default_factory=list, description="Files that depend on this file"
    )


class DependencyGraphInput(RefactoringBaseModel):
    """Dependency graph input for reorganization."""

    model_config = ConfigDict(extra=EXTRA_ALLOW, validate_assignment=True)

    dependencies: dict[str, DependencyInfo] = Field(
        default_factory=dict, description="File dependency information"
    )


class ReorganizationImpactModel(RefactoringBaseModel):
    """Impact metrics for reorganization operations."""

    files_moved: int = Field(..., ge=0, description="Number of files moved")
    categories_created: int = Field(
        ..., ge=0, description="Number of categories created"
    )
    dependency_depth_reduction: float = Field(
        ..., ge=0.0, le=1.0, description="Dependency depth reduction factor"
    )
    complexity_reduction: float = Field(
        ..., ge=0.0, le=1.0, description="Complexity reduction factor"
    )
    maintainability_improvement: float = Field(
        ..., ge=0.0, le=1.0, description="Maintainability improvement factor"
    )
    navigation_improvement: float = Field(
        ..., ge=0.0, le=1.0, description="Navigation improvement factor"
    )
    estimated_effort: RiskLevel = Field(..., description="Estimated effort level")


class ReorganizationPlanModel(RefactoringBaseModel):
    """Represents a complete reorganization plan."""

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

    plan_id: str = Field(..., description="Unique plan identifier")
    optimization_goal: str = Field(
        ..., description="Goal: dependency_depth, category_based, complexity"
    )
    current_structure: MemoryBankStructureData = Field(
        default_factory=MemoryBankStructureData, description="Current structure"
    )
    proposed_structure: MemoryBankStructureData = Field(
        default_factory=MemoryBankStructureData, description="Proposed structure"
    )
    actions: list[ReorganizationActionModel] = Field(
        default_factory=lambda: list[ReorganizationActionModel](),
        description="Actions to perform",
    )
    estimated_impact: ReorganizationImpactModel = Field(
        ..., description="Estimated impact"
    )
    risks: list[str] = Field(default_factory=list, description="Identified risks")
    benefits: list[str] = Field(default_factory=list, description="Expected benefits")
    preserve_history: bool = Field(
        default=True, description="Whether to preserve history"
    )


class ReorganizationPreviewResult(RefactoringBaseModel):
    """Result of previewing a reorganization plan."""

    files_to_move: int = Field(..., ge=0, description="Number of files to move")
    estimated_improvement: float = Field(
        ..., ge=0.0, le=1.0, description="Estimated improvement factor"
    )
    risks: list[str] = Field(default_factory=list, description="Identified risks")
