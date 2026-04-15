"""Pydantic models for rollback operations.

Extracted from foundation_rollback to keep the main module within line limits.
"""

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.models import SectionMetadata
from cortex.core.pydantic_extra import EXTRA_FORBID
from cortex.core.token_counter import TokenCounter
from cortex.core.version_manager import VersionManager


class RollbackManagers(BaseModel):
    """Typed manager bundle for rollback operations."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra=EXTRA_FORBID)

    fs_manager: FileSystemManager = Field(description="File system manager")
    token_counter: TokenCounter = Field(description="Token counter")
    metadata_index: MetadataIndex = Field(description="Metadata index")
    version_manager: VersionManager = Field(description="Version manager")


class RollbackProcessingData(BaseModel):
    """Rollback processing data structure.

    This model replaces `ModelDict` for rollback processing data.
    """

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

    content_hash: str = Field(..., description="Content hash")
    sections: list[SectionMetadata] = Field(
        default_factory=lambda: list[SectionMetadata](),
        description="Parsed sections",
    )
    token_count: int = Field(..., ge=0, description="Token count")
    size_bytes: int = Field(..., ge=0, description="Size in bytes")
