"""Version, dependency, and migration models."""

from pydantic import BaseModel, ConfigDict, Field

from ._base import DictLikeModel
from ._enums import ChangeType, FileCategory, MigrationResultStatus


class VersionMetadata(DictLikeModel):
    """Version snapshot metadata."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    version: int = Field(ge=1, description="Version number")
    timestamp: str = Field(description="ISO format timestamp")
    content_hash: str = Field(description="SHA-256 hash of content")
    size_bytes: int = Field(ge=0, description="Size in bytes")
    token_count: int = Field(ge=0, description="Token count")
    change_type: ChangeType = Field(description="Type of change")
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


class DependencyGraph(DictLikeModel):
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


class TransclusionGraph(DictLikeModel):
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


class ReferenceGraph(DictLikeModel):
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
    change_type: ChangeType = Field(description="Type of change")
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

    status: MigrationResultStatus = Field(description="Migration status")
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


class StaticDependencyInfo(BaseModel):
    """Static dependency configuration for a file."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    depends_on: list[str] = Field(
        default_factory=list, description="List of files this file depends on"
    )
    priority: int = Field(ge=0, description="Loading priority (0 = highest)")
    category: FileCategory = Field(description="File category")


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
    change_type: ChangeType | None = Field(default=None, description="Type of change")
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
