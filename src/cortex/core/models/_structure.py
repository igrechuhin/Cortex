"""Structure, git, health, and file organization models."""

from pydantic import BaseModel, ConfigDict, Field

from ._base import DictLikeModel
from ._enums import OperationStatus, RiskLevel


class ParsedLink(BaseModel):
    """Parsed markdown link information."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    text: str = Field(description="Link text")
    target: str = Field(description="Link target")
    line_number: int = Field(ge=1, description="Line number")


class ConsolidationImpactAnalysis(BaseModel):
    """Impact analysis for consolidation opportunity."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    opportunity_id: str = Field(description="Opportunity identifier")
    token_savings: int = Field(ge=0, description="Estimated token savings")
    files_affected: int = Field(ge=0, description="Number of files affected")
    extraction_required: bool = Field(
        default=True, description="Whether extraction is required"
    )
    transclusion_count: int = Field(ge=0, description="Number of transclusions")
    similarity_score: float = Field(ge=0.0, le=1.0, description="Similarity score 0-1")
    risk_level: RiskLevel = Field(default=RiskLevel.LOW, description="Risk level")
    benefits: list[str] = Field(default_factory=list, description="List of benefits")
    risks: list[str] = Field(default_factory=list, description="List of risks")


class ReorganizationActionPreview(BaseModel):
    """Preview of a single reorganization action."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    type: str = Field(description="Action type")
    description: str = Field(description="Action description")
    reason: str = Field(description="Reason for action")


class StructureMetrics(BaseModel):
    """Metrics for structure comparison."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    total_files: int = Field(default=0, ge=0, description="Total number of files")
    total_directories: int = Field(
        default=0, ge=0, description="Total number of directories"
    )
    max_depth: int = Field(default=0, ge=0, description="Maximum directory depth")
    total_tokens: int = Field(default=0, ge=0, description="Total token count")
    files_by_category: dict[str, int] = Field(
        default_factory=dict, description="File count by category"
    )
    organization: str | None = Field(
        default=None,
        description=(
            "Organization type: flat, category_based, "
            "dependency_optimized, simplified"
        ),
    )


class StructureComparison(BaseModel):
    """Comparison of current and proposed structure."""

    model_config = ConfigDict(extra="allow", validate_assignment=True)

    current: StructureMetrics | None = Field(
        default=None, description="Current structure metrics"
    )
    proposed: StructureMetrics | None = Field(
        default=None, description="Proposed structure metrics"
    )


class EstimatedImpactMetrics(BaseModel):
    """Estimated impact metrics for reorganization."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    token_savings: int = Field(default=0, ge=0, description="Estimated token savings")
    files_affected: int = Field(default=0, ge=0, description="Number of files affected")
    complexity_reduction: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Complexity reduction percentage",
    )
    dependency_depth_reduction: int = Field(
        default=0, ge=0, description="Dependency depth reduction"
    )


class ReorganizationPreview(BaseModel):
    """Preview of reorganization plan impact."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    plan_id: str = Field(description="Plan identifier")
    optimization_goal: str = Field(description="Optimization goal")
    actions_count: int = Field(ge=0, description="Number of actions")
    estimated_impact: EstimatedImpactMetrics = Field(
        default_factory=EstimatedImpactMetrics,
        description="Estimated impact metrics",
    )
    risks: list[str] = Field(default_factory=list, description="Identified risks")
    benefits: list[str] = Field(default_factory=list, description="Expected benefits")
    actions: list[ReorganizationActionPreview] = Field(
        default_factory=lambda: list[ReorganizationActionPreview](),
        description="Action details",
    )
    structure_comparison: StructureComparison | None = Field(
        default=None, description="Structure comparison"
    )


class HealthMetrics(BaseModel):
    """Health metrics for MCP connection."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    healthy: bool = Field(description="Whether connection is healthy")
    concurrent_operations: int = Field(
        ge=0, description="Current concurrent operations"
    )
    max_concurrent: int = Field(
        ge=0, description="Maximum allowed concurrent operations"
    )
    semaphore_available: int = Field(ge=0, description="Available semaphore slots")
    utilization_percent: float = Field(
        ge=0.0, le=100.0, description="Resource utilization percentage"
    )
    closure_count: int = Field(
        ge=0, description="Number of connection closures recorded"
    )
    recovery_count: int = Field(ge=0, description="Number of successful recoveries")


class GitCommandResult(DictLikeModel):
    """Result of a git command execution."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    success: bool = Field(description="Whether command succeeded")
    stdout: str = Field(default="", description="Standard output")
    stderr: str = Field(default="", description="Standard error")
    returncode: int | None = Field(default=None, description="Process return code")
    error: str | None = Field(default=None, description="Error message if failed")


class GitTimeoutResponse(BaseModel):
    """Response for git command timeout."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    success: bool = Field(default=False, description="Always False for timeout")
    error: str = Field(description="Timeout error message")
    stdout: str = Field(default="", description="Empty stdout")
    stderr: str = Field(default="", description="Empty stderr")


class SubmoduleInitResult(BaseModel):
    """Result of submodule initialization."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    status: OperationStatus = Field(description="Operation status")
    action: str | None = Field(default=None, description="Action performed")
    repo_url: str | None = Field(default=None, description="Repository URL")
    local_path: str | None = Field(default=None, description="Local submodule path")
    submodule_added: bool | None = Field(
        default=None, description="Whether submodule was added"
    )
    error: str | None = Field(default=None, description="Error message if failed")
    stdout: str | None = Field(default=None, description="Standard output")
    stderr: str | None = Field(default=None, description="Standard error")


class SubmoduleSyncResult(BaseModel):
    """Result of submodule synchronization."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    status: OperationStatus = Field(description="Sync status")
    pulled: bool = Field(default=False, description="Whether pull was performed")
    pushed: bool = Field(default=False, description="Whether push was performed")
    changes: dict[str, str] = Field(default_factory=dict, description="Changes summary")
    error: str | None = Field(default=None, description="Error message if failed")


class FileSizeEntry(BaseModel):
    """File size information for organization analysis."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    file: str = Field(description="File name")
    size_bytes: int = Field(ge=0, description="Size in bytes")
    tokens: int = Field(default=0, ge=0, description="Token count")


class FileOrganizationResult(BaseModel):
    """Result of file organization analysis."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    status: str = Field(description="Analysis status: analyzed, empty, error")
    file_count: int = Field(ge=0, description="Total number of files")
    total_size_bytes: int = Field(default=0, ge=0, description="Total size in bytes")
    total_size_kb: float = Field(default=0.0, ge=0.0, description="Total size in KB")
    avg_size_bytes: int = Field(default=0, ge=0, description="Average size in bytes")
    avg_size_kb: float = Field(default=0.0, ge=0.0, description="Average size in KB")
    max_size_bytes: int = Field(default=0, ge=0, description="Maximum file size")
    min_size_bytes: int = Field(default=0, ge=0, description="Minimum file size")
    largest_files: list[FileSizeEntry] = Field(
        default_factory=lambda: list[FileSizeEntry](),
        description="Largest files",
    )
    smallest_files: list[FileSizeEntry] = Field(
        default_factory=lambda: list[FileSizeEntry](),
        description="Smallest files",
    )
    issues: list[str] | None = Field(default=None, description="Identified issues")


class SnapshotMetadataInput(BaseModel):
    """Input metadata for creating version snapshots."""

    model_config = ConfigDict(extra="allow", validate_assignment=True)

    version: int | None = Field(default=None, ge=1, description="Version number")
    change_type: str | None = Field(default=None, description="Type of change")
    change_description: str | None = Field(
        default=None, description="Change description"
    )
    changed_sections: list[str] = Field(
        default_factory=lambda: list[str](),
        description="Changed sections",
    )


class SectionTokenCount(BaseModel):
    """Token count for a single section."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    heading: str = Field(description="Section heading")
    token_count: int = Field(ge=0, description="Token count for this section")
    percentage: float = Field(
        ge=0.0, le=100.0, description="Percentage of total tokens"
    )


class TokenCountSectionsResult(BaseModel):
    """Result of counting tokens per section."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    total_tokens: int = Field(ge=0, description="Total token count")
    sections: list[SectionTokenCount] = Field(
        default_factory=lambda: list[SectionTokenCount](),
        description="Token counts per section",
    )


class ContextSizeEstimate(BaseModel):
    """Estimate of context size for loading files."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    total_tokens: int = Field(ge=0, description="Total token count")
    estimated_cost_gpt4: float = Field(ge=0.0, description="Estimated cost in USD")
    warnings: list[str] = Field(
        default_factory=lambda: list[str](),
        description="Warnings about token count",
    )
    breakdown: dict[str, int] = Field(
        default_factory=lambda: dict[str, int](),
        description="Token count per file",
    )


class ParsedMarkdownSection(BaseModel):
    """Parsed markdown section information."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    title: str = Field(description="Section heading text")
    level: int = Field(ge=1, le=6, description="Heading level (1-6)")
    start_line: int = Field(
        ge=1,
        description="Line number where section starts (1-indexed)",
    )
