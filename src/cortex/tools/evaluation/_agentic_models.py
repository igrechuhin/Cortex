"""Pydantic models for the agentic (agent-in-the-loop) tool-selection eval.

Holds the case taxonomy (``EvalTaskKind``), the SDK-agnostic model-exchange
models used by the agent loop, and the paired scorecard whose invariants
forbid emitting a selection-accuracy figure without both negative kinds.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from cortex.core.pydantic_extra import EXTRA_FORBID


class EvalTaskKind(str, Enum):
    """Case kind for a selection eval task (paired-eval taxonomy)."""

    POSITIVE = "positive"
    CONTROL = "control"
    NEAR_MISS = "near-miss"


class AgenticSkipReason(str, Enum):
    """Why the agentic mode could not run."""

    DEPENDENCY_MISSING = "dependency_missing"
    API_KEY_MISSING = "api_key_missing"


class UnpairedReason(str, Enum):
    """Why a run may not report a selection-accuracy figure."""

    NO_CONTROL_TASKS = "no_control_tasks"
    NO_NEAR_MISS_TASKS = "no_near_miss_tasks"
    NO_NEGATIVE_TASKS = "no_negative_tasks"
    NO_POSITIVE_TASKS = "no_positive_tasks"


def enforce_kind_invariants(
    kind: EvalTaskKind,
    covered_by: str | None,
    expected_tools: list[str],
) -> None:
    """Raise ValueError when a task violates its kind's fixture contract."""
    if kind is EvalTaskKind.NEAR_MISS and not covered_by:
        raise ValueError("near-miss task requires a covered_by tool")
    if kind is not EvalTaskKind.NEAR_MISS and covered_by:
        raise ValueError(
            f"covered_by is only valid for near-miss tasks, not {kind.value}"
        )
    if kind is EvalTaskKind.CONTROL and expected_tools:
        raise ValueError("control task must not declare expected_tools")
    # AI: only near-miss requires expected_tools. Legacy positive fixtures may be
    # usage-only with no tools declared; those load fine and are simply excluded
    # from selection scoring rather than being rejected at load time.
    if kind is EvalTaskKind.NEAR_MISS and not expected_tools:
        raise ValueError("near-miss task requires non-empty expected_tools")


class ModelToolSchema(BaseModel):
    """A registered MCP tool as exposed to the model."""

    model_config = ConfigDict(extra=EXTRA_FORBID)

    name: str = Field(description="Registered MCP tool name")
    description: str = Field(description="Tool description shown to the model")
    input_schema: dict[str, object] = Field(
        default_factory=dict, description="JSON Schema for the tool's parameters"
    )


class ModelToolCall(BaseModel):
    """A tool invocation requested by the model."""

    model_config = ConfigDict(extra=EXTRA_FORBID)

    call_id: str = Field(description="Provider-assigned tool-call identifier")
    tool_name: str = Field(description="Name of the tool the model chose")
    arguments: dict[str, object] = Field(
        default_factory=dict, description="Arguments the model supplied"
    )


class ModelToolResult(BaseModel):
    """The outcome of executing one model-requested tool call."""

    model_config = ConfigDict(extra=EXTRA_FORBID)

    call_id: str = Field(description="Identifier of the originating tool call")
    content: str = Field(description="Tool output rendered as text")
    is_error: bool = Field(default=False, description="True when the call raised")


class ModelMessage(BaseModel):
    """One entry of the SDK-agnostic conversation transcript."""

    model_config = ConfigDict(extra=EXTRA_FORBID)

    role: Literal["user", "assistant"] = Field(description="Speaker role")
    text: str = Field(default="", description="Plain text content, if any")
    tool_calls: list[ModelToolCall] = Field(default_factory=list[ModelToolCall])
    tool_results: list[ModelToolResult] = Field(default_factory=list[ModelToolResult])


class ModelTurn(BaseModel):
    """A single normalized model response."""

    model_config = ConfigDict(extra=EXTRA_FORBID)

    text: str = Field(default="", description="Concatenated text blocks")
    tool_calls: list[ModelToolCall] = Field(default_factory=list[ModelToolCall])
    stop_reason: str = Field(default="", description="Provider stop reason")


class ParsedAgentOutput(BaseModel):
    """The ``<summary>``/``<feedback>``/``<response>`` blocks from final text."""

    model_config = ConfigDict(extra=EXTRA_FORBID)

    summary: str = Field(default="", description="Model's summary block")
    feedback: str = Field(
        default="", description="Model's critique of tool names and parameter docs"
    )
    response: str = Field(default="", description="Model's task answer block")


class AgentLoopOutcome(BaseModel):
    """Everything the bounded agent loop observed for one task."""

    model_config = ConfigDict(extra=EXTRA_FORBID)

    tools_called: list[str] = Field(default_factory=list[str])
    turns: int = Field(default=0, ge=0, description="Model turns consumed")
    turn_cap_reached: bool = Field(default=False)
    parsed: ParsedAgentOutput = Field(default_factory=ParsedAgentOutput)
    final_text: str = Field(default="", description="Raw final assistant text")
    error: str | None = Field(default=None, description="Loop-level failure message")


class ToolFeedbackRecord(BaseModel):
    """Model feedback about a tool's name, description, or errors."""

    model_config = ConfigDict(extra=EXTRA_FORBID)

    task_id: str = Field(description="Task that produced this feedback")
    tool_name: str = Field(description="Tool the feedback concerns")
    feedback: str = Field(description="Verbatim feedback text from the model")


class AgenticTaskResult(BaseModel):
    """Per-task result of the agentic selection eval."""

    model_config = ConfigDict(extra=EXTRA_FORBID)

    task_id: str
    task_name: str = ""
    kind: EvalTaskKind
    passed: bool
    reason: str = Field(default="", description="Why the task failed (empty on pass)")
    tools_called: list[str] = Field(default_factory=list[str])
    turns: int = Field(default=0, ge=0)
    turn_cap_reached: bool = False
    response: str = ""
    covered_by_used: bool | None = Field(
        default=None, description="near-miss only: was the covering tool used instead"
    )
    skipped: bool = False
    skip_reason: AgenticSkipReason | None = None


class AgenticScorecard(BaseModel):
    """Paired scorecard: accuracy is emitted only alongside both negative kinds."""

    model_config = ConfigDict(extra=EXTRA_FORBID)

    paired: bool = Field(description="True when both negative kinds are present")
    unpaired_reason: UnpairedReason | None = Field(default=None)
    selection_accuracy: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Omitted entirely when unpaired"
    )
    control_false_positive_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    near_miss_false_positive_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    positive_total: int = Field(default=0, ge=0)
    positive_passed: int = Field(default=0, ge=0)
    control_total: int = Field(default=0, ge=0)
    control_false_positives: int = Field(default=0, ge=0)
    near_miss_total: int = Field(default=0, ge=0)
    near_miss_false_positives: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _enforce_pairing(self) -> AgenticScorecard:
        """Structurally forbid an accuracy figure without a paired negative set."""
        # AI: this invariant is the whole point of the harness -- a positives-only
        # score rewards description inflation, so it must be impossible to build.
        if not self.paired and self.selection_accuracy is not None:
            raise ValueError("unpaired scorecard must not carry selection_accuracy")
        if not self.paired and self.unpaired_reason is None:
            raise ValueError("unpaired scorecard must carry an unpaired_reason")
        if self.paired and self.selection_accuracy is None:
            raise ValueError("paired scorecard must carry selection_accuracy")
        return self


class AgenticSummary(BaseModel):
    """Suite-level agentic payload attached to run_tool_evaluation output."""

    model_config = ConfigDict(extra=EXTRA_FORBID)

    scorecard: AgenticScorecard
    results: list[AgenticTaskResult] = Field(default_factory=list[AgenticTaskResult])
    feedback: list[ToolFeedbackRecord] = Field(default_factory=list[ToolFeedbackRecord])
    skipped: bool = Field(default=False, description="True when the whole run skipped")
    skip_reason: AgenticSkipReason | None = None
