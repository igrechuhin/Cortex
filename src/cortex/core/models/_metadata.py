"""Metadata, index, and cache models."""

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.pydantic_extra import EXTRA_FORBID

from ._base import DictLikeModel
from ._version import VersionMetadata


class FileMetadata(BaseModel):
    """File metadata entry."""

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

    file_path: str = Field(description="Path to file")
    content_hash: str = Field(description="SHA-256 hash")
    size_bytes: int = Field(ge=0, description="Size in bytes")
    token_count: int = Field(ge=0, description="Token count")
    last_modified: str = Field(description="ISO format timestamp")
    version: int = Field(ge=1, description="Version number")


class SectionMetadata(DictLikeModel):
    """Section metadata within a file."""

    model_config = ConfigDict(
        extra=EXTRA_FORBID, validate_assignment=True, populate_by_name=True
    )

    title: str = Field(
        alias="heading",
        validation_alias="heading",
        serialization_alias="heading",
        description="Section title/heading",
    )
    level: int = Field(default=1, ge=1, le=6, description="Heading level (1-6)")
    line_start: int = Field(default=1, ge=1, description="Starting line number")
    line_end: int = Field(default=1, ge=1, description="Ending line number")
    content_hash: str | None = Field(
        default=None, description="SHA-256 hash of section content"
    )
    token_count: int = Field(
        default=0, ge=0, description="Token count for this section"
    )


class DetailedFileMetadata(BaseModel):
    """Detailed file metadata including history and analytics."""

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

    path: str = Field(
        description="Path to file relative to project root (index.json portability)"
    )
    exists: bool = Field(description="Whether file exists on disk")
    size_bytes: int = Field(ge=0, description="Size in bytes")
    token_count: int = Field(ge=0, description="Token count")
    token_model: str = Field(description="Token model used for counting")
    last_modified: str = Field(description="ISO format timestamp of last modification")
    content_hash: str = Field(description="SHA-256 hash")
    sections: list[SectionMetadata] = Field(
        default_factory=lambda: list[SectionMetadata](),
        description="Section metadata",
    )
    read_count: int = Field(ge=0, default=0, description="Number of reads")
    write_count: int = Field(ge=0, default=0, description="Number of writes")
    last_read: str | None = Field(
        default=None, description="ISO format timestamp of last read"
    )
    current_version: int = Field(ge=0, default=0, description="Current version number")
    version_history: list[VersionMetadata] = Field(
        default_factory=lambda: list[VersionMetadata](),
        description="Version history (in-memory only; excluded from index.json)",
        exclude=True,
    )


class FileFrequency(BaseModel):
    """File access frequency data."""

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

    file: str = Field(description="File name")
    reads: int = Field(ge=0, default=0, description="Read count")
    writes: int = Field(ge=0, default=0, description="Write count")


class UsageAnalytics(BaseModel):
    """Usage analytics data."""

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

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

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

    total_files: int = Field(ge=0, description="Total number of files")
    total_size_bytes: int = Field(ge=0, description="Total size in bytes")
    total_tokens: int = Field(ge=0, description="Total token count")
    last_full_scan: str = Field(description="ISO format timestamp of last full scan")


class IndexGraphEdge(BaseModel):
    """Edge in index dependency graph data structure."""

    model_config = ConfigDict(
        extra=EXTRA_FORBID, validate_assignment=True, populate_by_name=True
    )

    from_node: str = Field(alias="from", description="Source node identifier")
    to_node: str = Field(alias="to", description="Target node identifier")


class IndexDependencyGraphData(BaseModel):
    """Dependency graph structure for index storage."""

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

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

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

    totals: Totals = Field(description="Total statistics")
    usage_analytics: UsageAnalytics = Field(description="Usage analytics")
    file_count: int = Field(ge=0, description="Number of files in index")


class IndexData(BaseModel):
    """Complete index data structure."""

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

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


class CacheStatsModel(BaseModel):
    """Cache statistics for monitoring performance."""

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

    hits: int = Field(..., ge=0, description="Cache hits")
    misses: int = Field(..., ge=0, description="Cache misses")
    evictions: int = Field(..., ge=0, description="Cache evictions")
    size: int = Field(..., ge=0, description="Current cache size")
    hit_rate: float = Field(..., ge=0.0, le=1.0, description="Hit rate 0-1")


class AccessPatternModel(BaseModel):
    """Access pattern for predictive prefetching."""

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

    file: str = Field(..., description="File path")
    co_accessed_files: list[str] = Field(
        default_factory=list, description="Files accessed together"
    )
    frequency: int = Field(..., ge=0, description="Access frequency")
    last_access: float = Field(..., ge=0.0, description="Last access timestamp")


class WarmingStrategyModel(DictLikeModel):
    """Cache warming strategy configuration."""

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

    name: str = Field(..., description="Strategy name")
    enabled: bool = Field(..., description="Whether strategy is enabled")
    priority: int = Field(..., ge=0, description="Strategy priority")
    max_items: int = Field(..., ge=0, description="Maximum items to warm")


class CacheWarmingResultModel(DictLikeModel):
    """Result of cache warming operation."""

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

    strategy: str = Field(..., description="Strategy used")
    items_warmed: int = Field(..., ge=0, description="Items warmed")
    time_ms: float = Field(..., ge=0.0, description="Time taken in milliseconds")
    success: bool = Field(..., description="Whether warming succeeded")
