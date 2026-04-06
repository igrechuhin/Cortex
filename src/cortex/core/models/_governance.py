"""Governance and constitutional models."""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class ConstitutionDoc(BaseModel):
    """Immutable project governance document stored in memory bank."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    principles: list[str] = Field(
        default_factory=list, description="Immutable architectural principles"
    )
    tech_stack: list[str] = Field(
        default_factory=list, description="Technology stack constraints"
    )
    hard_limits: list[str] = Field(
        default_factory=list, description="Non-negotiable implementation limits"
    )
    compliance_requirements: list[str] = Field(
        default_factory=list,
        description="Planning and delivery compliance requirements",
    )
    created: date = Field(description="Creation date of the constitution")
    last_updated: date = Field(description="Last update date of the constitution")
