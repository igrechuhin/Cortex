"""Agentic selection-eval suite: sibling of ``run_execution_suite``.

Runs each eligible task through the bounded agent loop, scores it by kind, and
assembles both an ``EvalSuiteResult`` (identical in type to the deterministic
mode, so persistence and the dashboard writer are reused unchanged) and an
``AgenticSummary`` carrying the paired scorecard and captured model feedback.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.pydantic_extra import EXTRA_FORBID

from ._agent_loop import (
    DEFAULT_MAX_TURNS,
    ModelClientProtocol,
    ToolSessionProtocol,
    build_task_prompt,
    run_agent_loop,
)
from ._agentic_models import (
    AgenticSkipReason,
    AgenticSummary,
    AgenticTaskResult,
    EvalTaskKind,
    ToolFeedbackRecord,
)
from ._agentic_scoring import build_scorecard, collect_feedback, score_task
from ._models import EvalSuiteResult, EvalTask, EvalTaskResult, EvalTaskStatus


class AgenticSuiteOutcome(BaseModel):
    """Both halves of an agentic run: the shared suite shape plus the summary."""

    model_config = ConfigDict(extra=EXTRA_FORBID)

    suite: EvalSuiteResult = Field(description="Same type as the deterministic mode")
    summary: AgenticSummary = Field(description="Paired scorecard and feedback")


def _task_is_scorable(task: EvalTask, exposed: set[str] | None) -> bool:
    """Whether a task can be scored against the surface the model was shown."""
    if task.kind is EvalTaskKind.CONTROL:
        return True
    if not task.expected_tools:
        return False
    if exposed is None:
        return True
    # AI: a tool the model never saw can never be selected. Scoring such a task
    # would book a guaranteed positive failure and a guaranteed near-miss pass --
    # the "negatives are too easy and never fail" trap. Drop it instead.
    return all(tool in exposed for tool in task.expected_tools)


def select_agentic_tasks(
    tasks: list[EvalTask], exposed_tools: set[str] | None = None
) -> list[EvalTask]:
    """Keep tasks scorable against ``exposed_tools`` (the model-visible surface).

    Usage-only positives with no ``expected_tools`` are dropped, as are tasks
    naming a tool absent from the exposed surface. Passing ``None`` disables the
    exposure check, for callers that score against a fixed schema list.
    """
    return [task for task in tasks if _task_is_scorable(task, exposed_tools)]


def _to_eval_task_result(task: EvalTask, result: AgenticTaskResult) -> EvalTaskResult:
    """Project an agentic result onto the shared per-task result shape."""
    if result.skipped:
        status = EvalTaskStatus.UNAVAILABLE
    else:
        status = EvalTaskStatus.SUCCESS if result.passed else EvalTaskStatus.MIXED
    return EvalTaskResult(
        task_id=result.task_id,
        task_name=result.task_name,
        category=task.category,
        status=status,
        total_calls=len(result.tools_called),
        successful_calls=len(result.tools_called) if result.passed else 0,
        failed_calls=0 if result.passed else len(result.tools_called),
        success_rate=1.0 if result.passed else 0.0,
        evaluated_tools=list(result.tools_called),
    )


def _skipped_summary(
    tasks: list[EvalTask], skip_reason: AgenticSkipReason
) -> AgenticSummary:
    """Build a typed all-skipped summary when the model client is unavailable."""
    results = [
        AgenticTaskResult(
            task_id=task.id,
            task_name=task.name,
            kind=task.kind,
            passed=False,
            reason=f"agentic mode skipped: {skip_reason.value}",
            skipped=True,
            skip_reason=skip_reason,
        )
        for task in tasks
    ]
    scorecard = build_scorecard(results)
    return AgenticSummary(
        scorecard=scorecard, results=results, skipped=True, skip_reason=skip_reason
    )


def build_skipped_outcome(
    tasks: list[EvalTask], skip_reason: AgenticSkipReason
) -> AgenticSuiteOutcome:
    """Assemble an outcome for a run that could not call the model at all."""
    return AgenticSuiteOutcome(
        suite=EvalSuiteResult(generated_at=datetime.now(UTC).isoformat(), tasks=[]),
        summary=_skipped_summary(tasks, skip_reason),
    )


async def _run_one_task(
    task: EvalTask,
    session: ToolSessionProtocol,
    client: ModelClientProtocol,
    max_turns: int,
) -> tuple[AgenticTaskResult, list[ToolFeedbackRecord]]:
    """Run and score a single task, returning its result and captured feedback."""
    prompt = build_task_prompt(task.description, task.expected_outcome)
    outcome = await run_agent_loop(session, client, prompt, max_turns=max_turns)
    return score_task(task, outcome), collect_feedback(task, outcome)


async def run_agentic_suite(
    tasks: list[EvalTask],
    session: ToolSessionProtocol,
    client: ModelClientProtocol,
    max_turns: int = DEFAULT_MAX_TURNS,
) -> AgenticSuiteOutcome:
    """Run the agentic selection eval over ``tasks`` and assemble the outcome."""
    exposed = {schema.name for schema in await session.list_tool_schemas()}
    selected = select_agentic_tasks(tasks, exposed)
    generated_at = datetime.now(UTC).isoformat()
    results: list[AgenticTaskResult] = []
    feedback: list[ToolFeedbackRecord] = []
    task_results: list[EvalTaskResult] = []
    for task in selected:
        result, task_feedback = await _run_one_task(task, session, client, max_turns)
        results.append(result)
        feedback.extend(task_feedback)
        task_results.append(_to_eval_task_result(task, result))
    summary = AgenticSummary(
        scorecard=build_scorecard(results), results=results, feedback=feedback
    )
    return AgenticSuiteOutcome(
        suite=EvalSuiteResult(generated_at=generated_at, tasks=task_results),
        summary=summary,
    )


__all__ = [
    "AgenticSuiteOutcome",
    "build_skipped_outcome",
    "run_agentic_suite",
    "select_agentic_tasks",
]
