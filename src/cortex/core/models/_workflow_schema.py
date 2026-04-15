"""Pydantic models for schema-defined Cortex workflow variants."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.pydantic_extra import EXTRA_FORBID


class WorkflowPhase(BaseModel):
    """One phase in a workflow schema (maps to a slash command or MCP entry)."""

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

    name: str = Field(..., description="Stable phase identifier.")
    tool: str = Field(
        ...,
        description="MCP tool name or slash command to invoke for this phase.",
    )
    required: bool = Field(
        ...,
        description="When True, orchestration must not skip this phase.",
    )
    condition: str | None = Field(
        default=None,
        description=(
            "Optional Python expression evaluated against session state; "
            "phase skipped when expression evaluates to False."
        ),
    )
    config: dict[str, str] = Field(
        default_factory=dict,
        description="Phase-specific string config passed to the tool.",
    )


class WorkflowSchema(BaseModel):
    """Declarative workflow variant (built-in or project-local YAML)."""

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

    name: str = Field(..., description="Schema identifier (file stem or logical name).")
    description: str = Field(..., description="Human-readable summary of the variant.")
    phases: list[WorkflowPhase] = Field(
        ...,
        description="Ordered phases to execute for this workflow.",
    )
    inherits: str | None = Field(
        default=None,
        description="Optional base schema name whose phases this schema extends.",
    )
