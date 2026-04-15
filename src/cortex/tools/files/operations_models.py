"""
Models for manage_file, rollback_file_version, and manager initialization.
"""

from __future__ import annotations

from enum import Enum

from pydantic import ConfigDict, Field

from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.pydantic_extra import EXTRA_FORBID
from cortex.core.token_counter import TokenCounter
from cortex.core.version_manager import VersionManager

from ..models_base import (
    ErrorResultBase,
    StrictBaseModel,
    ToolResultBase,
    ToolResultStatus,
)


class ManageFileMetadataStatus(str, Enum):
    """Status for manage_file metadata operation."""

    SUCCESS = "success"
    WARNING = "warning"


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

    status: ToolResultStatus = Field(default=ToolResultStatus.SUCCESS)
    file_name: str = Field(..., min_length=1, description="Name of the file")
    content: str = Field(..., description="File content")
    metadata: FileMetadata | None = Field(None, description="Optional file metadata")


class ManageFileWriteResult(ToolResultBase):
    """Result of manage_file write operation."""

    status: ToolResultStatus = Field(default=ToolResultStatus.SUCCESS)
    file_name: str = Field(..., min_length=1, description="Name of the file")
    message: str = Field(..., min_length=1, description="Operation message")
    snapshot_id: str | None = Field(None, description="Snapshot ID if created")
    version: int | None = Field(None, ge=1, description="File version number")
    tokens: int | None = Field(None, ge=0, description="Token count")


class ManageFileMetadataResult(ToolResultBase):
    """Result of manage_file metadata operation."""

    status: ManageFileMetadataStatus = Field(default=ManageFileMetadataStatus.SUCCESS)
    file_name: str
    metadata: FileMetadata | None = None
    message: str | None = None  # Only for warning status


class ManageFileErrorResult(ErrorResultBase):
    """Error result for manage_file operations."""

    file_name: str | None = None
    available_files: list[str] = Field(default_factory=list)
    suggestion: str | None = None
    valid_operations: list[str] = Field(default_factory=list)


ManageFileResult = (
    ManageFileReadResult
    | ManageFileWriteResult
    | ManageFileMetadataResult
    | ManageFileErrorResult
)


class RollbackFileVersionResult(ToolResultBase):
    """Result of rollback_file_version operation (success)."""

    status: ToolResultStatus = Field(default=ToolResultStatus.SUCCESS)
    file_name: str
    rolled_back_from_version: int
    new_version: int
    token_count: int | None = None


class RollbackFileVersionErrorResult(ErrorResultBase):
    """Error result for rollback_file_version operations."""

    file_name: str | None = None
    version: int | None = None


RollbackFileVersionResultUnion = (
    RollbackFileVersionResult | RollbackFileVersionErrorResult
)


class ManagersInitResult(StrictBaseModel):
    """Result of initializing managers for file operations."""

    root: str = Field(description="Project root path")
    fs: FileSystemManager = Field(description="FileSystemManager instance")
    index: MetadataIndex = Field(description="MetadataIndex instance")
    tokens: TokenCounter = Field(description="TokenCounter instance")
    versions: VersionManager = Field(description="VersionManager instance")

    model_config = ConfigDict(
        extra=EXTRA_FORBID,
        validate_assignment=True,
        arbitrary_types_allowed=True,
    )
