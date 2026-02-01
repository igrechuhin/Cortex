"""Pydantic models for script promotion pipeline."""

from pydantic import BaseModel, Field


class ValidationResult(BaseModel):
    """Result of validating a script for promotion."""

    passed: bool = Field(..., description="True if script meets promotion criteria")
    quality_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Estimated quality 0-1",
    )
    issues: list[str] = Field(
        default_factory=list,
        description="List of validation issues",
    )
