"""Pydantic models for workflow templates (plan: agent-skills-and-composability Step 4)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class WorkflowTemplate(BaseModel):
    """A single workflow template: name, description, steps, keywords for matching."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(description="Unique workflow identifier")
    description: str = Field(description="Short description of the workflow")
    steps: list[str] = Field(
        default_factory=list,
        description="Ordered tool/step sequence (guidance; agent adapts as needed)",
    )
    keywords: list[str] = Field(
        default_factory=list,
        description="Keywords for suggest_workflow(task_description) matching",
    )
