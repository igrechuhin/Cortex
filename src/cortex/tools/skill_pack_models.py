"""Pydantic models for Agent Skill Packs (plan: agent-skills-and-composability)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SkillPackManifest(BaseModel):
    """Manifest for a single skill pack: tools, workflows, examples, and guidance."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(description="Unique pack identifier (e.g. core, quality)")
    description: str = Field(description="Short description of the pack's purpose")
    tools: list[str] = Field(
        default_factory=list, description="Tool names in this pack"
    )
    when_to_use: str | None = Field(
        default=None, description="Guidance on when to use this pack"
    )
    workflow_sequences: list[str] = Field(
        default_factory=list,
        description="Common workflow sequences (tool call order)",
    )
    example_invocations: list[str] = Field(
        default_factory=list,
        description="Example tool invocations or patterns",
    )
    troubleshooting_tips: list[str] = Field(
        default_factory=list,
        description="Tips for common issues with these tools",
    )
    keywords: list[str] = Field(
        default_factory=list,
        description="Keywords for discovery matching (task_description)",
    )
