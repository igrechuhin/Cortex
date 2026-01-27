"""
Core Pydantic models for core modules.

These models are defined here to avoid circular imports with tools/models.py.
Used by: version_manager, dependency_graph, metadata_index, migration
"""

from collections.abc import ItemsView, KeysView, ValuesView
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# JSON-serializable value type (Python 3.13+ recursive type alias).
type JsonPrimitive = str | int | float | bool | None
type JsonValue = JsonPrimitive | list[JsonValue] | dict[str, JsonValue]

# Common JSON dictionary shape used at JSON boundaries.
type ModelDict = dict[str, JsonValue]

# ============================================================================
# Dict-like Pydantic base model (preserves legacy call sites)
# ============================================================================


class DictLikeModel(BaseModel):
    """A Pydantic model that supports dict-like access."""

    def __getitem__(self, key: str) -> JsonValue:
        data: ModelDict = self.model_dump(mode="python", by_alias=True)
        return data[key]

    def get(self, key: str, default: JsonValue | None = None) -> JsonValue | None:
        data: ModelDict = self.model_dump(mode="python", by_alias=True)
        return data.get(key, default)

    def __contains__(self, key: object) -> bool:
        if not isinstance(key, str):
            return False
        data: ModelDict = self.model_dump(mode="python", by_alias=True)
        return key in data

    def keys(self) -> KeysView[str]:
        data: ModelDict = self.model_dump(mode="python", by_alias=True)
        return data.keys()

    def items(self) -> ItemsView[str, JsonValue]:
        data: ModelDict = self.model_dump(mode="python", by_alias=True)
        return data.items()

    def values(self) -> ValuesView[JsonValue]:
        data: ModelDict = self.model_dump(mode="python", by_alias=True)
        return data.values()


# ============================================================================
# JSON Value Models (for security.py and other modules handling arbitrary JSON)
# ============================================================================


class JsonDict(BaseModel):
    """Pydantic model for JSON dictionary structures.

    This model replaces `ModelDict` for type-safe JSON dictionary handling.
    It allows arbitrary keys and values, making it suitable for JSON data.
    Uses extra="allow" to accept any keys dynamically.
    """

    model_config = ConfigDict(extra="allow", validate_assignment=True)

    def to_dict(self) -> ModelDict:
        """Convert to plain dictionary.

        Returns:
            Dictionary representation (use model_dump() directly for better typing)
        """
        return self.model_dump(exclude_none=True)

    @classmethod
    def from_dict(cls, data: ModelDict | dict[str, JsonValue]):
        """Create JsonDict from a dictionary.

        Args:
            data: Dictionary to convert

        Returns:
            JsonDict instance
        """
        return cls.model_validate(data)


class JsonList(BaseModel):
    """Pydantic model for JSON list structures.

    This model replaces untyped JSON lists for type-safe JSON list handling.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    items: list[JsonValue] = Field(
        default_factory=lambda: list[JsonValue](), description="List items"
    )

    def to_list(self) -> list[JsonValue]:
        """Convert to plain list.

        Returns:
            List representation (use items directly for better typing)
        """
        return self.items

    @classmethod
    def from_list(cls, data: list[JsonValue]):
        """Create JsonList from a list.

        Args:
            data: List to convert

        Returns:
            JsonList instance
        """
        return cls(items=data)


# ============================================================================
# Version Manager Models
# ============================================================================


class VersionMetadata(DictLikeModel):
    """Version snapshot metadata."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    version: int = Field(ge=1, description="Version number")
    timestamp: str = Field(description="ISO format timestamp")
    content_hash: str = Field(description="SHA-256 hash of content")
    size_bytes: int = Field(ge=0, description="Size in bytes")
    token_count: int = Field(ge=0, description="Token count")
    change_type: Literal["created", "modified", "rollback", "manual_backup"] = Field(
        description="Type of change"
    )
    snapshot_path: str = Field(description="Path to snapshot file")
    changed_sections: list[str] = Field(
        default_factory=lambda: list[str](),
        description="Section headings that changed",
    )
    change_description: str | None = Field(
        default=None, description="Optional description of changes"
    )


class SnapshotInfo(BaseModel):
    """Snapshot file information."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    content: str = Field(description="Snapshot content")
    metadata: VersionMetadata = Field(description="Version metadata")


# ============================================================================
# Dependency Graph Models
# ============================================================================


class FileDependencyInfo(BaseModel):
    """File dependency information."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    priority: int = Field(description="Loading priority")
    dependencies: list[str] = Field(
        default_factory=list, description="List of file dependencies"
    )


class DependencyNode(BaseModel):
    """Dependency graph node."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    file: str = Field(description="File name")
    priority: int = Field(description="Loading priority")
    category: str = Field(description="File category")


class DependencyEdge(BaseModel):
    """Dependency graph edge."""

    model_config = ConfigDict(
        extra="forbid", validate_assignment=True, populate_by_name=True
    )

    from_: str = Field(alias="from", description="Source file")
    to_: str = Field(alias="to", description="Target file")
    type: str = Field(description="Edge type (links or informs)")
    strength: str = Field(description="Edge strength (strong or medium)")


class DependencyGraph(BaseModel):
    """Dependency graph export."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    nodes: list[DependencyNode] = Field(description="Graph nodes")
    edges: list[DependencyEdge] = Field(description="Graph edges")
    progressive_loading_order: list[str] = Field(
        description="Files in progressive loading order"
    )


class TransclusionNode(BaseModel):
    """Transclusion graph node."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    file: str = Field(description="File name")


class TransclusionEdge(BaseModel):
    """Transclusion graph edge."""

    model_config = ConfigDict(
        extra="forbid", validate_assignment=True, populate_by_name=True
    )

    from_: str = Field(alias="from", description="Source file")
    to_: str = Field(alias="to", description="Target file")
    type: str = Field(description="Edge type (always transclusion)")


class TransclusionGraph(BaseModel):
    """Transclusion graph export."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    nodes: list[TransclusionNode] = Field(description="Graph nodes")
    edges: list[TransclusionEdge] = Field(description="Graph edges")


class ReferenceEdge(BaseModel):
    """Reference graph edge."""

    model_config = ConfigDict(
        extra="forbid", validate_assignment=True, populate_by_name=True
    )

    from_: str = Field(alias="from", description="Source file")
    to_: str = Field(alias="to", description="Target file")
    type: str = Field(description="Edge type (always reference)")


class ReferenceGraph(BaseModel):
    """Reference graph export."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    nodes: list[TransclusionNode] = Field(description="Graph nodes")
    edges: list[ReferenceEdge] = Field(description="Graph edges")


class FileDependencyDetail(BaseModel):
    """Detailed file dependency information."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    depends_on: list[str] = Field(description="Files this file depends on")
    dependents: list[str] = Field(description="Files that depend on this file")


class GraphDict(BaseModel):
    """Complete dependency graph dictionary."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    dependencies: dict[str, FileDependencyDetail] = Field(
        description="File dependency details"
    )


# ============================================================================
# Metadata Index Models
# ============================================================================


class FileMetadata(BaseModel):
    """File metadata entry."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    file_path: str = Field(description="Path to file")
    content_hash: str = Field(description="SHA-256 hash")
    size_bytes: int = Field(ge=0, description="Size in bytes")
    token_count: int = Field(ge=0, description="Token count")
    last_modified: str = Field(description="ISO format timestamp")
    version: int = Field(ge=1, description="Version number")


class SectionMetadata(DictLikeModel):
    """Section metadata within a file."""

    model_config = ConfigDict(
        extra="forbid", validate_assignment=True, populate_by_name=True
    )

    # Support both "title" (internal) and "heading" (legacy/external)
    # - Accept input as either `title` or `heading`
    # - Serialize using `heading` for compatibility with existing tests/index.json
    title: str = Field(
        alias="heading",
        validation_alias="heading",
        serialization_alias="heading",
        description="Section title/heading",
    )
    level: int = Field(default=1, ge=1, le=6, description="Heading level (1-6)")
    # Make line_start and line_end optional with defaults for legacy data
    line_start: int = Field(default=1, ge=1, description="Starting line number")
    line_end: int = Field(default=1, ge=1, description="Ending line number")
    content_hash: str | None = Field(
        default=None, description="SHA-256 hash of section content"
    )


class DetailedFileMetadata(BaseModel):
    """Detailed file metadata including history and analytics."""

    model_config = ConfigDict(extra="allow", validate_assignment=True)

    path: str = Field(description="Absolute path to file")
    exists: bool = Field(description="Whether file exists on disk")
    size_bytes: int = Field(ge=0, description="Size in bytes")
    token_count: int = Field(ge=0, description="Token count")
    token_model: str = Field(description="Token model used for counting")
    last_modified: str = Field(description="ISO format timestamp of last modification")
    content_hash: str = Field(description="SHA-256 hash")
    sections: list[SectionMetadata] = Field(
        default_factory=lambda: list[SectionMetadata](), description="Section metadata"
    )
    read_count: int = Field(ge=0, default=0, description="Number of reads")
    write_count: int = Field(ge=0, default=0, description="Number of writes")
    last_read: str | None = Field(
        default=None, description="ISO format timestamp of last read"
    )
    current_version: int = Field(ge=0, default=0, description="Current version number")
    version_history: list[VersionMetadata] = Field(
        default_factory=lambda: list[VersionMetadata](), description="Version history"
    )


class FileFrequency(BaseModel):
    """File access frequency data."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    file: str = Field(description="File name")
    reads: int = Field(ge=0, default=0, description="Read count")
    writes: int = Field(ge=0, default=0, description="Write count")


class UsageAnalytics(BaseModel):
    """Usage analytics data."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    total_reads: int = Field(ge=0, description="Total read operations")
    total_writes: int = Field(ge=0, description="Total write operations")
    files_by_read_frequency: list[FileFrequency] = Field(
        default_factory=lambda: list[FileFrequency](),
        description="Files sorted by read frequency",
    )
    files_by_write_frequency: list[FileFrequency] = Field(
        default_factory=lambda: list[FileFrequency](),
        description="Files sorted by write frequency",
    )
    last_session_start: str = Field(
        description="ISO format timestamp of last session start"
    )
    sessions_count: int = Field(ge=0, description="Number of sessions")


class Totals(BaseModel):
    """Total statistics."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    total_files: int = Field(ge=0, description="Total number of files")
    total_size_bytes: int = Field(ge=0, description="Total size in bytes")
    total_tokens: int = Field(ge=0, description="Total token count")
    last_full_scan: str = Field(description="ISO format timestamp of last full scan")


class IndexGraphEdge(BaseModel):
    """Edge in index dependency graph data structure."""

    model_config = ConfigDict(
        extra="forbid", validate_assignment=True, populate_by_name=True
    )

    from_node: str = Field(alias="from", description="Source node identifier")
    to_node: str = Field(alias="to", description="Target node identifier")


class IndexDependencyGraphData(BaseModel):
    """Dependency graph structure for index storage.

    Note: This is different from tools/models.py.DependencyGraphData which is used
    for API responses. This model stores the graph structure in the index file.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    nodes: list[str] = Field(
        default_factory=list, description="List of node identifiers"
    )
    edges: list[IndexGraphEdge] = Field(
        default_factory=lambda: list[IndexGraphEdge](),
        description="List of edges (from, to)",
    )
    progressive_loading_order: list[str] = Field(
        default_factory=list, description="Recommended loading order"
    )


class IndexStats(BaseModel):
    """Index statistics."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    totals: Totals = Field(description="Total statistics")
    usage_analytics: UsageAnalytics = Field(description="Usage analytics")
    file_count: int = Field(ge=0, description="Number of files in index")


class IndexData(BaseModel):
    """Complete index data structure."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    schema_version: str = Field(description="Index schema version")
    created_at: str = Field(description="ISO format timestamp of index creation")
    last_updated: str = Field(description="ISO format timestamp of last update")
    project_root: str = Field(description="Project root directory path")
    memory_bank_dir: str = Field(description="Memory bank directory path")
    files: dict[str, DetailedFileMetadata] = Field(
        default_factory=dict, description="File metadata by name"
    )
    dependency_graph: IndexDependencyGraphData = Field(description="Dependency graph")
    usage_analytics: UsageAnalytics = Field(description="Usage analytics")
    totals: Totals = Field(description="Total statistics")


# ============================================================================
# Migration Models
# ============================================================================


class MigrationStatus(BaseModel):
    """Migration status information."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    current_version: str = Field(description="Current schema version")
    target_version: str = Field(description="Target schema version")
    needs_migration: bool = Field(description="Whether migration is needed")
    migration_path: list[str] = Field(
        default_factory=list, description="Steps required for migration"
    )


class DiskUsageInfo(DictLikeModel):
    """Disk usage information for version history."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    total_bytes: int = Field(ge=0, description="Total bytes used")
    file_count: int = Field(ge=0, description="Number of files")


class FormattedVersionMetadata(BaseModel):
    """Formatted version metadata for export."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    version: int = Field(ge=1, description="Version number")
    timestamp: str = Field(description="ISO format timestamp")
    change_type: Literal["created", "modified", "rollback", "manual_backup"] = Field(
        description="Type of change"
    )
    size_bytes: int = Field(ge=0, description="Size in bytes")
    token_count: int = Field(ge=0, description="Token count")
    content_hash: str = Field(description="Abbreviated content hash")
    changed_sections: list[str] = Field(
        default_factory=list, description="Section headings that changed"
    )
    description: str | None = Field(
        default=None, description="Optional description of changes"
    )


class MigrationInfo(BaseModel):
    """Migration information result."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    needs_migration: bool = Field(description="Whether migration is needed")
    reason: str | None = Field(
        default=None, description="Reason when migration is not needed"
    )
    files_found: int | None = Field(
        default=None, description="Number of markdown files found"
    )
    file_names: list[str] = Field(
        default_factory=list, description="List of markdown file names"
    )
    total_size_bytes: int | None = Field(
        default=None, description="Total size of all files in bytes"
    )
    estimated_tokens: int | None = Field(
        default=None, description="Estimated token count"
    )
    backup_location: str | None = Field(
        default=None, description="Backup directory location"
    )


class VerificationResult(BaseModel):
    """Migration verification result."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    success: bool = Field(description="Whether verification succeeded")
    error: str | None = Field(
        default=None, description="Error message if verification failed"
    )
    files_verified: int | None = Field(
        default=None, description="Number of files verified"
    )
    index_valid: bool | None = Field(default=None, description="Whether index is valid")
    snapshots_created: bool | None = Field(
        default=None, description="Whether snapshots were created"
    )


class MigrationResult(BaseModel):
    """Migration execution result."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    status: Literal["success", "failure"] = Field(description="Migration status")
    files_migrated: int = Field(ge=0, description="Number of files migrated")
    backup_location: str | None = Field(
        default=None, description="Backup directory location"
    )
    details: VerificationResult = Field(description="Verification details")


class BackupInfo(BaseModel):
    """Backup information."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    path: str = Field(description="Path to backup directory")
    timestamp: str = Field(description="Timestamp string from directory name")
    created: str | None = Field(
        default=None, description="ISO format creation timestamp"
    )
    size_bytes: int = Field(ge=0, description="Total size of backup in bytes")


# ============================================================================
# Cache Models (from advanced_cache.py, cache_warming.py)
# ============================================================================


class CacheStatsModel(BaseModel):
    """Cache statistics for monitoring performance."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    hits: int = Field(..., ge=0, description="Cache hits")
    misses: int = Field(..., ge=0, description="Cache misses")
    evictions: int = Field(..., ge=0, description="Cache evictions")
    size: int = Field(..., ge=0, description="Current cache size")
    hit_rate: float = Field(..., ge=0.0, le=1.0, description="Hit rate 0-1")


class AccessPatternModel(BaseModel):
    """Access pattern for predictive prefetching."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    file: str = Field(..., description="File path")
    co_accessed_files: list[str] = Field(
        default_factory=list, description="Files accessed together"
    )
    frequency: int = Field(..., ge=0, description="Access frequency")
    last_access: float = Field(..., ge=0.0, description="Last access timestamp")


class WarmingStrategyModel(BaseModel):
    """Cache warming strategy configuration."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    name: str = Field(..., description="Strategy name")
    enabled: bool = Field(..., description="Whether strategy is enabled")
    priority: int = Field(..., ge=0, description="Strategy priority")
    max_items: int = Field(..., ge=0, description="Maximum items to warm")


class CacheWarmingResultModel(BaseModel):
    """Result of cache warming operation."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    strategy: str = Field(..., description="Strategy used")
    items_warmed: int = Field(..., ge=0, description="Items warmed")
    time_ms: float = Field(..., ge=0.0, description="Time taken in milliseconds")
    success: bool = Field(..., description="Whether warming succeeded")


# ============================================================================
# Dependency Graph Internal Models
# ============================================================================


class StaticDependencyInfo(BaseModel):
    """Static dependency configuration for a file.

    Used internally by DependencyGraph to define the static dependency hierarchy.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    depends_on: list[str] = Field(
        default_factory=list, description="List of files this file depends on"
    )
    priority: int = Field(ge=0, description="Loading priority (0 = highest)")
    category: Literal["meta", "foundation", "context", "active", "status"] = Field(
        description="File category"
    )


# ============================================================================
# Protocol Return Type Models (for VersionManagerProtocol)
# ============================================================================


class VersionHistoryMetadata(BaseModel):
    """Metadata for version history entry."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    changed_sections: list[str] = Field(
        default_factory=list, description="Section headings that changed"
    )
    change_description: str | None = Field(
        default=None, description="Description of changes"
    )
    content_hash: str | None = Field(default=None, description="Content hash")


class VersionHistoryEntryModel(BaseModel):
    """Entry in version history."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    snapshot_id: str = Field(..., description="Snapshot identifier")
    timestamp: str = Field(..., description="ISO timestamp of snapshot")
    version: int = Field(..., ge=1, description="Version number")
    change_type: Literal["created", "modified", "rollback", "manual_backup"] | None = (
        Field(default=None, description="Type of change")
    )
    size_bytes: int | None = Field(default=None, ge=0, description="Size in bytes")
    token_count: int | None = Field(default=None, ge=0, description="Token count")
    metadata: VersionHistoryMetadata = Field(
        default_factory=VersionHistoryMetadata, description="Additional metadata"
    )


class RollbackToVersionResult(BaseModel):
    """Result of rolling back to a specific version."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    file_name: str = Field(..., description="File that was rolled back")
    content: str = Field(..., description="Restored content")
    restored_from: str = Field(..., description="Snapshot ID restored from")
    previous_version: int = Field(..., ge=1, description="Version before rollback")
    new_version: int = Field(..., ge=1, description="Version after rollback")


# ============================================================================
# Protocol Return Type Models (for DependencyGraphProtocol)
# ============================================================================


class DependencyGraphDict(BaseModel):
    """Dictionary representation of dependency graph."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    graph: dict[str, list[str]] = Field(
        default_factory=dict, description="Forward dependencies"
    )
    reverse: dict[str, list[str]] = Field(
        default_factory=dict, description="Reverse dependencies"
    )
    loading_order: list[str] = Field(
        default_factory=list, description="Optimal loading order"
    )
    cycles: list[list[str]] = Field(
        default_factory=lambda: list[list[str]](), description="Detected cycles"
    )


class FileDependencyData(BaseModel):
    """Dependency data for a single file."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    priority: int = Field(ge=0, description="Loading priority")
    dependencies: list[str] = Field(
        default_factory=list, description="List of file dependencies"
    )


class GraphDataDict(BaseModel):
    """Graph data dictionary for dependency visualization."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    files: dict[str, FileDependencyData] = Field(
        default_factory=dict, description="File dependency data by file name"
    )


# ============================================================================
# File System Protocol Models
# ============================================================================


class ParsedLink(BaseModel):
    """Parsed markdown link information."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    text: str = Field(description="Link text")
    target: str = Field(description="Link target")
    line_number: int = Field(ge=1, description="Line number")


# ============================================================================
# Refactoring Protocol Models
# ============================================================================


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
    risk_level: Literal["low", "medium", "high"] = Field(
        default="low", description="Risk level"
    )
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
    """Comparison of current and proposed structure.

    Note: Uses extra="allow" because reorganization_planner.py passes dicts with
    "organization" key. This will be migrated to StructureMetrics in a future refactor.
    """

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
        default=0.0, ge=0.0, le=1.0, description="Complexity reduction percentage"
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
        default_factory=EstimatedImpactMetrics, description="Estimated impact metrics"
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


# ============================================================================
# MCP Connection Health Models
# ============================================================================


class HealthMetrics(BaseModel):
    """Health metrics for MCP connection.

    This model is defined in core/models.py to avoid circular imports
    between core/mcp_stability.py and tools/models.py.
    """

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


# ============================================================================
# Git Command Models
# ============================================================================


class GitCommandResult(BaseModel):
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

    status: Literal["success", "error"] = Field(description="Operation status")
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

    status: Literal["success", "error"] = Field(description="Sync status")
    pulled: bool = Field(default=False, description="Whether pull was performed")
    pushed: bool = Field(default=False, description="Whether push was performed")
    changes: dict[str, str] = Field(default_factory=dict, description="Changes summary")
    error: str | None = Field(default=None, description="Error message if failed")


# ============================================================================
# File Organization Result Models
# ============================================================================


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
        default_factory=lambda: list[FileSizeEntry](), description="Largest files"
    )
    smallest_files: list[FileSizeEntry] = Field(
        default_factory=lambda: list[FileSizeEntry](), description="Smallest files"
    )
    issues: list[str] | None = Field(default=None, description="Identified issues")


# ============================================================================
# Snapshot Metadata Model (for versioning.py protocol)
# ============================================================================


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


# ============================================================================
# Token Counter Models
# ============================================================================


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
        ge=1, description="Line number where section starts (1-indexed)"
    )


# ============================================================================
# MCP Stability Models
# ============================================================================


class ConnectionHealth(BaseModel):
    """MCP connection health metrics."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    healthy: bool = Field(description="Whether connection is healthy")
    concurrent_operations: int = Field(
        ge=0, description="Current concurrent operations"
    )
    max_concurrent: int = Field(
        ge=1, description="Maximum allowed concurrent operations"
    )
    semaphore_available: int = Field(ge=0, description="Available semaphore slots")
    utilization_percent: float = Field(
        ge=0.0, le=100.0, description="Resource utilization percentage"
    )


# ============================================================================
# Container Models
# ============================================================================

# ============================================================================
# MCP Tool Execution Models
# ============================================================================


class MCPToolArguments(BaseModel):
    """Arguments for MCP tool execution.

    This model replaces `ModelDict` for kwargs in MCP tool execution.
    Since tool arguments are dynamic and vary by tool, we use a flexible
    model that can accept any keyword arguments.
    """

    model_config = ConfigDict(extra="allow", validate_assignment=False)

    # Use model_dump(exclude_none=True) directly instead of to_kwargs()
    # This avoids `ModelDict` return type


# ============================================================================
# Cache Configuration Models
# ============================================================================


class CacheConfig(BaseModel):
    """Cache configuration settings.

    This model replaces `ModelDict` for cache configuration.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    ttl_seconds: int = Field(default=3600, ge=0, description="Time-to-live in seconds")
    lru_max_size: int = Field(default=100, ge=1, description="LRU cache maximum size")

    def to_dict(self) -> ModelDict:
        """Convert to dictionary for compatibility.

        Returns:
            Dictionary representation (use model_dump() directly for better typing)
        """
        return self.model_dump()


class ManagerCacheDefaults(BaseModel):
    """Default cache configurations per manager type.

    This model replaces `dict[str, ModelDict]` for manager cache defaults.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    token_counter: CacheConfig = Field(
        default_factory=lambda: CacheConfig(ttl_seconds=600, lru_max_size=200),
        description="Token counter cache config",
    )
    file_system: CacheConfig = Field(
        default_factory=lambda: CacheConfig(ttl_seconds=300, lru_max_size=100),
        description="File system cache config",
    )
    dependency_graph: CacheConfig = Field(
        default_factory=lambda: CacheConfig(ttl_seconds=900, lru_max_size=50),
        description="Dependency graph cache config",
    )
    structure_analyzer: CacheConfig = Field(
        default_factory=lambda: CacheConfig(ttl_seconds=1800, lru_max_size=50),
        description="Structure analyzer cache config",
    )
    pattern_analyzer: CacheConfig = Field(
        default_factory=lambda: CacheConfig(ttl_seconds=3600, lru_max_size=100),
        description="Pattern analyzer cache config",
    )

    def get_manager_config(self, manager_name: str) -> CacheConfig:
        """Get cache config for a manager.

        Args:
            manager_name: Name of the manager

        Returns:
            CacheConfig for the manager, or default if not found
        """
        try:
            return getattr(self, manager_name)
        except AttributeError:
            # Conservative fallback for unknown managers.
            return self.file_system


# ============================================================================
# Response Models (for responses.py)
# ============================================================================


class SuccessResponseData(BaseModel):
    """Data for a success response.

    This model replaces `ModelDict` for success response data.
    """

    model_config = ConfigDict(extra="allow", validate_assignment=True)

    def to_dict(self) -> ModelDict:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dictionary representation (use model_dump(exclude_none=True)
            directly for better typing)
        """
        return self.model_dump(exclude_none=True)


class ErrorContext(BaseModel):
    """Context information for error responses.

    This model replaces `ModelDict` for error context.
    """

    model_config = ConfigDict(extra="allow", validate_assignment=True)

    def to_dict(self) -> ModelDict:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dictionary representation (use model_dump(exclude_none=True)
            directly for better typing)
        """
        return self.model_dump(exclude_none=True)


class ErrorResponseModel(BaseModel):
    """Complete error response model.

    This model replaces `ModelDict` for error responses.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    status: Literal["error"] = Field(description="Response status")
    error: str = Field(description="Error message")
    error_type: str = Field(description="Error type name")
    action_required: str | None = Field(
        default=None, description="Action required to resolve"
    )
    context: JsonDict | None = Field(default=None, description="Error context")
