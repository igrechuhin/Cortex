"""Roadmap synchronization validation models.

These models were originally defined in `validation.models` and are now
grouped here by domain (roadmap sync) as part of Phase 81.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class RoadmapSection(StrEnum):
    """Canonical roadmap section headers. Single source of truth."""

    BLOCKERS = "Blockers (ASAP Priority)"
    ACTIVE_WORK = "Active Work (in progress)"
    FUTURE = "Future Enhancements"
    PENDING = "Pending plans (from .cortex/plans)"


SECTION_TO_KEY: dict[str, str] = {
    RoadmapSection.BLOCKERS: "blockers",
    RoadmapSection.ACTIVE_WORK: "active_work",
    RoadmapSection.FUTURE: "future",
    RoadmapSection.PENDING: "pending",
}


KEY_TO_SECTION: dict[str, str] = {v: k for k, v in SECTION_TO_KEY.items()}


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
    "KEY_TO_SECTION",
    "RoadmapSection",
    "SECTION_TO_KEY",
    "TodoItemModel",
    "RoadmapReferenceModel",
    "SyncValidationResultModel",
]
