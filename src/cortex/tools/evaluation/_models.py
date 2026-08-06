"""
Phase 57: Evaluation models (Pydantic enums and BaseModel).

Extracted for Phase 9.1.4 file size compliance.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from cortex.core.pydantic_extra import EXTRA_ALLOW, EXTRA_FORBID

from ._agentic_models import (
    EvalTaskKind,
    enforce_kind_invariants,
)


class EvalTaskCategory(str, Enum):
    """Workflow category for an evaluation task."""

    CONTEXT = "context"
    PRE_COMMIT = "pre_commit"
    PLAN = "plan"
    MEMORY_BANK = "memory_bank"
    OTHER = "other"


class EvalTaskStatus(str, Enum):
    """Status of a single evaluation task result."""

    SUCCESS = "success"
    MIXED = "mixed"
    NO_DATA = "no_data"
    UNAVAILABLE = "unavailable"


class ExecutionExpectType(str, Enum):
    """Type of deterministic check for execution-based eval output."""

    SCHEMA_VALID = "schema_valid"
    CONTAINS = "contains"
    EXACT_MATCH = "exact_match"


class EvalRunMode(str, Enum):
    """Execution mode for run_tool_evaluation."""

    FULL = "full"
    FAST = "fast"
    FOCUSED = "focused"
    AGENTIC = "agentic"


class ExecutionExpectSpec(BaseModel):
    """Expected outcome for a single execution (deterministic check)."""

    model_config = ConfigDict(extra=EXTRA_FORBID)

    type: ExecutionExpectType = Field(
        description="Check type: schema_valid (dict has keys), contains (output has substring), exact_match"
    )
    schema_keys: list[str] | None = Field(
        default=None,
        description="Required top-level keys when type is schema_valid (after JSON parse).",
    )
    substring: str | None = Field(
        default=None,
        description="Substring that must appear in tool output when type is contains.",
    )
    expected_value: object | None = Field(
        default=None,
        description="Exact value to compare when type is exact_match (JSON-serializable).",
    )


class ExecutionSpec(BaseModel):
    """Spec to run one tool and check its output (for execution-based evals)."""

    model_config = ConfigDict(extra=EXTRA_FORBID)

    tool: str = Field(description="MCP tool name to invoke (e.g. get_structure_info).")
    arguments: dict[str, object] = Field(
        default_factory=dict,
        description="Arguments to pass to the tool (JSON-serializable).",
    )
    expect: ExecutionExpectSpec = Field(
        description="How to validate the tool output (deterministic check)."
    )


class EvidenceLink(BaseModel):
    """Reference to the experience-graph node backing an eval task.

    Links a ``failure_based_evals.json`` entry to the analytics query
    (``cortex.experience.analytics``) that produced it, so evidence can be
    traced back to its originating node and artifact.
    """

    model_config = ConfigDict(extra=EXTRA_FORBID)

    node_id: str = Field(description="Experience-store node id backing this entry")
    artifact_ref: str | None = Field(
        default=None, description="Relative path to the node's stored artifact"
    )
    confidence_source: Literal["graph", "transcript"] = Field(
        description=(
            "Whether evidence came from a graph query (high) or transcript "
            "scraping (fallback, lower confidence)"
        )
    )


def _empty_evidence_links() -> list[EvidenceLink]:
    """Typed default factory for EvalTask.evidence."""
    return []


class EvalTask(BaseModel):
    """Single evaluation task definition grounded in a real workflow."""

    model_config = ConfigDict(extra=EXTRA_ALLOW)

    id: str = Field(description="Stable identifier for this evaluation task")
    name: str = Field(description="Human-readable task name")
    description: str = Field(description="Detailed task description")
    category: EvalTaskCategory = Field(
        default=EvalTaskCategory.OTHER,
        description="High-level workflow category for the task",
    )
    expected_tools: list[str] = Field(
        default_factory=list,
        description="List of MCP tools that should be involved in this task",
    )
    expected_outcome: str = Field(
        description="What success looks like for this task (free-form summary)"
    )
    token_budget_baseline: int | None = Field(
        default=None,
        ge=0,
        description="Expected token budget for this task, if known",
    )
    common_failure_modes: list[str] = Field(
        default_factory=list,
        description="Known or anticipated failure modes for this task",
    )
    usage_query: str | None = Field(
        default=None,
        description=(
            "Optional query string used to filter historical usage events when "
            "computing metrics (e.g., by tool name, error substring, or summary)."
        ),
    )
    execution: ExecutionSpec | None = Field(
        default=None,
        description="Optional execution spec for deterministic run (tool + expect check).",
    )
    evidence: list[EvidenceLink] = Field(
        default_factory=_empty_evidence_links,
        description=(
            "Graph-pattern evidence (experience-store node ids/artifacts) backing "
            "this task; empty for legacy entries with no store coverage."
        ),
    )
    kind: EvalTaskKind = Field(
        default=EvalTaskKind.POSITIVE,
        description="Selection-eval case kind: positive, control, or near-miss.",
    )
    covered_by: str | None = Field(
        default=None,
        description="Tool that already covers a near-miss task; near-miss only.",
    )

    @model_validator(mode="after")
    def _check_kind_invariants(self) -> EvalTask:
        """Enforce the covered_by / expected_tools contract for this kind."""
        enforce_kind_invariants(self.kind, self.covered_by, self.expected_tools)
        return self


class ToolTaskMetrics(BaseModel):
    """Per-tool metrics within a single evaluation task."""

    model_config = ConfigDict(extra=EXTRA_FORBID)

    calls: int = Field(ge=0, description="Number of calls for this tool")
    successful: int = Field(ge=0, description="Number of successful calls")
    failed: int = Field(ge=0, description="Number of failed calls")


class EvalTaskResult(BaseModel):
    """Computed metrics for a single evaluation task."""

    model_config = ConfigDict(extra=EXTRA_FORBID)

    task_id: str
    task_name: str
    category: EvalTaskCategory
    status: EvalTaskStatus
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    success_rate: float = 0.0
    avg_duration_ms: float = 0.0
    total_duration_ms: float = 0.0
    total_input_tokens: int = Field(
        default=0,
        ge=0,
        description="Total input tokens consumed (0 when usage events lack token data)",
    )
    total_output_tokens: int = Field(
        default=0,
        ge=0,
        description="Total output tokens consumed (0 when usage events lack token data)",
    )
    error_types: dict[str, int] = Field(default_factory=dict)
    evaluated_tools: list[str] = Field(default_factory=list)
    tool_metrics: dict[str, ToolTaskMetrics] = Field(
        default_factory=dict,
        description="Per-tool call and success counts for dashboard aggregation",
    )


def _empty_eval_results() -> list[EvalTaskResult]:
    """Typed default factory for EvalSuiteResult.tasks."""
    return []


class EvalSuiteResult(BaseModel):
    """Aggregate results for an evaluation suite run."""

    model_config = ConfigDict(extra=EXTRA_FORBID)

    generated_at: str = Field(
        description="ISO 8601 timestamp when the suite was evaluated"
    )
    tasks: list[EvalTaskResult] = Field(default_factory=_empty_eval_results)


class ErrorPattern(BaseModel):
    """Aggregated error pattern across tasks and tools."""

    model_config = ConfigDict(extra=EXTRA_FORBID)

    error_type: str
    count: int
    affected_tools: list[str]


class ToolCombination(BaseModel):
    """Tool usage pattern: set of tools used together in tasks."""

    model_config = ConfigDict(extra=EXTRA_FORBID)

    tools: list[str] = Field(description="Tool names that co-occur in tasks")
    task_count: int = Field(ge=0, description="Number of tasks using this combination")


def _empty_tool_combinations() -> list[ToolCombination]:
    """Typed default factory for EvalAnalysis.top_tool_combinations."""
    return []


class EvalAnalysis(BaseModel):
    """High-level analysis of an evaluation suite."""

    model_config = ConfigDict(extra=EXTRA_FORBID)

    overall_success_rate: float
    total_tasks: int
    tasks_with_no_data: int
    tasks_unavailable: int
    average_calls_per_task: float
    average_tokens_per_task: float = Field(
        default=0.0,
        ge=0,
        description="Average input+output tokens per task (0 when usage lacks token data)",
    )
    token_consumption_by_category: dict[str, float] = Field(
        default_factory=dict,
        description="Average tokens per task by category (empty when no token data)",
    )
    top_error_patterns: list[ErrorPattern]
    success_rate_by_category: dict[str, float]
    top_tool_combinations: list[ToolCombination] = Field(
        default_factory=_empty_tool_combinations,
        description="Most common tool sets used together across tasks",
    )


class ABWinner(str, Enum):
    """Winner of an A/B comparison (baseline vs optimized)."""

    baseline = "baseline"
    optimized = "optimized"
    tie = "tie"


class OptimizationRunWinner(str, Enum):
    """Winner or status of an optimization run (includes baseline-only)."""

    baseline = "baseline"
    optimized = "optimized"
    tie = "tie"
    baseline_only = "baseline_only"


class ABComparisonResult(BaseModel):
    """Result of comparing baseline vs optimized evaluation analyses (A/B)."""

    model_config = ConfigDict(extra=EXTRA_FORBID)

    winner: ABWinner
    success_rate_delta: float = Field(
        description="optimized minus baseline overall_success_rate"
    )
    total_error_count_baseline: int = 0
    total_error_count_optimized: int = 0
    error_count_delta: int = Field(
        description="optimized total errors minus baseline (negative = fewer errors)"
    )


class OptimizationRunRecord(BaseModel):
    """Single optimization run for history persistence."""

    model_config = ConfigDict(extra=EXTRA_FORBID)

    run_id: str
    generated_at: str = Field(description="ISO 8601 timestamp")
    baseline_success_rate: float = 0.0
    optimized_success_rate: float | None = None
    winner: OptimizationRunWinner = OptimizationRunWinner.baseline_only
    success_rate_delta: float | None = None
    total_error_count_baseline: int = 0
    total_error_count_optimized: int | None = None


class ExecutionResultEntry(BaseModel):
    """Single execution result for execution_summary.results."""

    model_config = ConfigDict(extra=EXTRA_FORBID)

    task_id: str = Field(description="Evaluation task id")
    passed: bool = Field(description="Whether the execution check passed")
    message: str = Field(description="Result message")
    duration_ms: float = Field(ge=0, description="Duration in milliseconds")
    skipped: bool = Field(description="True if task had no execution spec")


def _empty_execution_result_entries() -> list[ExecutionResultEntry]:
    """Typed default factory for ExecutionSummary.results."""
    return []


class ExecutionSummary(BaseModel):
    """Pass/fail summary for execution-based evals."""

    model_config = ConfigDict(extra=EXTRA_FORBID)

    execution_passed: int = Field(ge=0, description="Count of passed executions")
    execution_failed: int = Field(ge=0, description="Count of failed executions")
    execution_skipped: int = Field(ge=0, description="Count of skipped (no spec)")
    execution_total_run: int = Field(ge=0, description="Total executions run")
    results: list[ExecutionResultEntry] = Field(
        default_factory=_empty_execution_result_entries,
        description="Per-task execution results",
    )
