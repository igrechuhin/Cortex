"""Pydantic models for Agent Skill Packs (plan: agent-skills-and-composability)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SkillWorkflowPhase(BaseModel):
    """A single phase in a skill workflow: maps to one MCP tool call."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(description="Unique phase identifier within this workflow")
    tool: str = Field(
        description="MCP tool function name to call (e.g. run_quality_gate)"
    )
    operation: str | None = Field(
        default=None, description="Optional operation argument for the tool"
    )
    required: bool = Field(
        default=True, description="If False, failure of this phase is non-fatal"
    )
    condition: str | None = Field(
        default=None,
        description="Python expression; phase is skipped when evaluates to False",
    )
    retry_condition: str | None = Field(
        default=None,
        description="Python expression; loop this phase when True (up to max_iterations)",
    )
    success_condition: str | None = Field(
        default=None,
        description=(
            "Python expression evaluated against tool result to determine passed; "
            "defaults to status != 'error'"
        ),
    )
    max_iterations: int = Field(
        default=1, ge=1, description="Maximum times this phase may execute (retry cap)"
    )
    inputs: dict[str, str] = Field(
        default_factory=dict,
        description="Map 'prior_phase.field' to param name for data passing",
    )
    outputs: list[str] = Field(
        default_factory=list,
        description="Result JSON field names to capture for downstream phases",
    )


class SkillWorkflow(BaseModel):
    """Execution blueprint for a skill pack (sequential only in v1)."""

    model_config = ConfigDict(frozen=True)

    mode: str = Field(
        default="sequential",
        description="Execution mode (currently only 'sequential' is supported)",
    )
    phases: list[SkillWorkflowPhase] = Field(
        description="Ordered list of phases to execute"
    )


class PhaseResult(BaseModel):
    """Captured result of a single workflow phase execution."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(description="Phase name")
    iterations: int = Field(description="Number of times this phase executed")
    passed: bool = Field(description="Whether the phase succeeded")
    outputs: dict[str, object] = Field(
        default_factory=dict, description="Captured output fields"
    )
    skipped: bool = Field(
        default=False, description="True when condition evaluated False"
    )
    error: str | None = Field(default=None, description="Error message if phase failed")


class SkillWorkflowResult(BaseModel):
    """Structured result returned by skill_pack(operation='execute')."""

    model_config = ConfigDict(frozen=True)

    passed: bool = Field(description="True when all required phases passed")
    iterations: int = Field(description="Total phase executions across all phases")
    phases: list[PhaseResult] = Field(
        description="Per-phase execution results in order"
    )
    error: str | None = Field(
        default=None, description="Top-level error message if workflow could not start"
    )


class EvaluationReport(BaseModel):
    """Structured result of an evaluation workflow execution."""

    model_config = ConfigDict(frozen=True)

    score: float = Field(description="Evaluation score (0.0–1.0)")
    passed: bool = Field(description="True when no actionable gaps were found")
    gaps: list[str] = Field(
        default_factory=list, description="Actionable gaps found during analysis"
    )
    stored_path: str | None = Field(
        default=None,
        description="Memory bank path where report was stored, or None if store was skipped",
    )


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
    workflow: SkillWorkflow | None = Field(
        default=None,
        description="Optional sequential workflow blueprint for execute operation",
    )
