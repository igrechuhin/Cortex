"""
Data models for progressive loading.

Extracted from progressive_loader to avoid circular imports with helpers.
"""

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from cortex.optimization.models import FileContentMetadata


class LoadedFileContent(BaseModel):
    """Type definition for loaded file content."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    content: str = Field(description="File content")
    tokens: int = Field(ge=0, description="Token count")
    cumulative_tokens: int = Field(ge=0, description="Cumulative token count")
    metadata: FileContentMetadata = Field(
        default_factory=FileContentMetadata, description="File metadata"
    )


@dataclass
class LoadedContent:
    """Represents a loaded piece of content."""

    file_name: str
    content: str
    tokens: int
    cumulative_tokens: int
    priority: int
    relevance_score: float
    more_available: bool
    metadata: FileContentMetadata
