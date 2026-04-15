"""Scoring and file metadata models for optimization.

Phase 9.1.5: Split from optimization/models.py for file size compliance.
"""

from pydantic import BaseModel, ConfigDict, Field, model_validator

from cortex.core.models import JsonValue
from cortex.core.pydantic_extra import EXTRA_ALLOW

from ._base import OptimizationBaseModel


class FileMetadataForScoring(OptimizationBaseModel):
    """Metadata for a file used in scoring and optimization operations."""

    model_config = ConfigDict(extra=EXTRA_ALLOW, validate_assignment=True)

    path: str | None = Field(default=None, description="File path")
    size: int | None = Field(default=None, ge=0, description="File size in bytes")
    size_bytes: int | None = Field(
        default=None, ge=0, description="File size in bytes (alias)"
    )
    token_count: int | None = Field(default=None, ge=0, description="Token count")
    content_hash: str | None = Field(default=None, description="Content hash")
    last_modified: str | None = Field(
        default=None, description="ISO timestamp of last modification"
    )
    sections: list[str] = Field(default_factory=list, description="Section headings")
    priority: int | None = Field(default=None, ge=0, description="Loading priority")

    @model_validator(mode="before")
    @classmethod
    def _normalize_sections(cls, data: JsonValue) -> JsonValue:
        """Normalize section metadata into a list of headings."""
        if isinstance(data, BaseModel):
            data = data.model_dump(mode="python")
        if not isinstance(data, dict):
            return data
        sections_obj = data.get("sections")
        if not isinstance(sections_obj, list):
            return data
        normalized: list[JsonValue] = []
        for item in sections_obj:
            if isinstance(item, str):
                normalized.append(item)
                continue
            if isinstance(item, dict):
                title_obj = item.get("title") or item.get("heading")
                if isinstance(title_obj, str):
                    normalized.append(title_obj)
        data["sections"] = normalized
        return data


class FileContentMetadata(OptimizationBaseModel):
    """Metadata for loaded file content."""

    model_config = ConfigDict(extra=EXTRA_ALLOW, validate_assignment=True)

    content_hash: str | None = Field(default=None, description="Content hash")
    last_modified: str | None = Field(
        default=None, description="ISO timestamp of last modification"
    )
    sections: list[str] = Field(default_factory=list, description="Section headings")
    priority: int | None = Field(default=None, ge=0, description="Loading priority")
    tokens: int | None = Field(default=None, ge=0, description="Token count")


class LoadedFileContentModel(OptimizationBaseModel):
    """Type definition for loaded file content."""

    content: str = Field(..., description="File content")
    tokens: int = Field(..., ge=0, description="Token count")
    cumulative_tokens: int = Field(..., ge=0, description="Cumulative token count")
    metadata: FileContentMetadata = Field(
        default_factory=FileContentMetadata, description="File metadata"
    )


class LoadedContentModel(OptimizationBaseModel):
    """Represents a loaded piece of content."""

    file_name: str = Field(..., description="File name")
    content: str = Field(..., description="File content")
    tokens: int = Field(..., ge=0, description="Token count")
    cumulative_tokens: int = Field(..., ge=0, description="Cumulative token count")
    priority: int = Field(..., ge=0, description="Loading priority")
    relevance_score: float = Field(
        ..., ge=0.0, le=1.0, description="Relevance score 0-1"
    )
    more_available: bool = Field(..., description="Whether more content is available")
    metadata: FileContentMetadata = Field(
        default_factory=FileContentMetadata, description="File metadata"
    )


class FileRelevanceScoreModel(OptimizationBaseModel):
    """Relevance score breakdown for a file."""

    file_name: str | None = Field(default=None, description="File name (optional)")
    relevance_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Overall relevance score"
    )
    total_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Total weighted score"
    )
    keyword_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Keyword match score"
    )
    dependency_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Dependency relevance score"
    )
    recency_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Recency score"
    )
    quality_boost: float = Field(default=1.0, ge=0.0, description="Quality multiplier")
    quality_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Quality score"
    )
    reason: str | None = Field(default=None, description="Explanation of score")

    @model_validator(mode="after")
    def sync_score_aliases(self) -> "FileRelevanceScoreModel":
        """Sync relevance_score and total_score aliases."""
        if self.total_score > 0.0 and self.relevance_score == 0.0:
            object.__setattr__(self, "relevance_score", self.total_score)
        elif self.relevance_score > 0.0 and self.total_score == 0.0:
            object.__setattr__(self, "total_score", self.relevance_score)
        return self


class SectionScoreModel(OptimizationBaseModel):
    """Relevance score for a section within a file."""

    title: str | None = Field(default=None, description="Section title")
    section: str | None = Field(
        default=None, description="Section name (alias for title)"
    )
    score: float = Field(..., ge=0.0, le=1.0, description="Section relevance score")
    start_line: int | None = Field(default=None, ge=1, description="Section start line")
    end_line: int | None = Field(default=None, ge=1, description="Section end line")
    reason: str | None = Field(default=None, description="Explanation of score")

    @model_validator(mode="after")
    def sync_title_section(self) -> "SectionScoreModel":
        """Sync title and section aliases."""
        if self.section is not None and self.title is None:
            object.__setattr__(self, "title", self.section)
        elif self.title is not None and self.section is None:
            object.__setattr__(self, "section", self.title)
        return self


class ScoredSectionModel(OptimizationBaseModel):
    """Section with relevance scoring for summarization."""

    name: str = Field(..., description="Section name/heading")
    content: str = Field(..., description="Section content")
    score: float = Field(..., ge=0.0, le=1.0, description="Importance score")
    tokens: int = Field(..., ge=0, description="Token count")


class SummarizationState(OptimizationBaseModel):
    """State for tracking parsing during summarization."""

    in_code_block: bool = Field(default=False, description="Currently in code block")
    in_example: bool = Field(default=False, description="Currently in example section")
    code_block_lines: list[str] = Field(
        default_factory=list, description="Accumulated code block lines"
    )
