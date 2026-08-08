"""Pydantic models for the linking module."""

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.pydantic_extra import EXTRA_FORBID


class LinkingBaseModel(BaseModel):
    """Base model for linking types with strict validation."""

    model_config = ConfigDict(
        extra=EXTRA_FORBID,
        validate_assignment=True,
        validate_default=True,
    )


class TransclusionOptions(LinkingBaseModel):
    """Parsed transclusion options."""

    lines: int | None = Field(
        default=None, ge=1, description="Number of lines to include"
    )
    recursive: bool = Field(
        default=True, description="Whether to resolve nested transclusions"
    )
