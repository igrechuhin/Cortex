"""Roadmap synchronization validation models.

These models were originally defined in `validation.models` and are now
grouped here by domain (roadmap sync) as part of Phase 81.
"""

from pydantic import BaseModel, ConfigDict, Field


class TodoItemModel(BaseModel):
    """Represents a TODO item found in the codebase."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    file_path: str = Field(description="File path containing TODO")
    line: int = Field(ge=1, description="Line number")
    snippet: str = Field(description="Code snippet")
    category: str = Field(description="TODO category")


class RoadmapReferenceModel(BaseModel):
    """Represents a file reference found in the roadmap."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    file_path: str = Field(description="Referenced file path")
    line: int | None = Field(None, ge=1, description="Line number if specified")
    context: str = Field(description="Context of reference")
    phase: str | None = Field(None, description="Phase if specified")


class SyncValidationResultModel(BaseModel):
    """Result of roadmap synchronization validation."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    valid: bool = Field(description="Whether sync is valid")
    missing_roadmap_entries: list[TodoItemModel] = Field(
        default_factory=lambda: list[TodoItemModel](),
        description="TODOs missing from roadmap",
    )
    invalid_references: list[RoadmapReferenceModel] = Field(
        default_factory=lambda: list[RoadmapReferenceModel](),
        description="Invalid roadmap references",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Warnings",
    )


__all__ = [
    "TodoItemModel",
    "RoadmapReferenceModel",
    "SyncValidationResultModel",
]
