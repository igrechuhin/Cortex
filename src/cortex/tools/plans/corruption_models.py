"""Pydantic models for roadmap corruption detection and fixing."""

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.pydantic_extra import EXTRA_FORBID


class CorruptionMatch(BaseModel):
    """A detected corruption match."""

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

    line_num: int = Field(ge=1, description="Line number")
    original: str = Field(description="Original corrupted text")
    fixed: str = Field(description="Fixed text")
    pattern: str = Field(description="Pattern that matched")


class FixRoadmapCorruptionResult(BaseModel):
    """Result of roadmap corruption fixing operation."""

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

    success: bool = Field(description="Whether operation succeeded")
    file_name: str = Field(description="File name")
    corruption_count: int = Field(ge=0, description="Number of corruptions found")
    fixes_applied: list[CorruptionMatch] = Field(
        default_factory=lambda: list[CorruptionMatch](),
        description="List of fixes applied",
    )
    error_message: str | None = Field(default=None, description="Error message if any")
