"""
Pydantic models for managers module.

This module contains Pydantic models for manager operations,
migrated from dataclass definitions for better validation.
"""

from typing import override

from pydantic import BaseModel, ConfigDict, Field


class ManagerGroupModel(BaseModel):
    """Group of related managers that should be initialized together."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        validate_default=True,
    )

    name: str = Field(..., description="Group name")
    managers: list[str] = Field(
        default_factory=list, description="List of manager names"
    )
    priority: int = Field(
        ...,
        ge=1,
        le=4,
        description="Priority level (1=always, 2=frequent, 3=occasional, 4=rare)",
    )

    @override
    def __str__(self) -> str:
        """Return string representation."""
        return f"{self.name} ({len(self.managers)} managers, priority {self.priority})"
