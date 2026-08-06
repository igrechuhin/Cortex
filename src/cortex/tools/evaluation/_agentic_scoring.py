"""Per-kind scoring and paired aggregation for the agentic selection eval.

Scoring answers one question only: were the tool's name, description, and
parameter schema enough for the model to select it. Aggregation refuses to
emit a selection-accuracy figure unless the run contains at least one
``control`` and at least one ``near-miss`` task.
"""

from __future__ import annotations

from ._agentic_models import (
    AgenticScorecard,
    AgenticTaskResult,
    AgentLoopOutcome,
    EvalTaskKind,
    ToolFeedbackRecord,
    UnpairedReason,
)
from ._models import EvalTask

NOT_FOUND_SENTINEL = "NOT_FOUND"


def _score_positive(task: EvalTask, outcome: AgentLoopOutcome) -> tuple[bool, str]:
    """Positive: called tools must cover expected_tools and a response must exist."""
    called = set(outcome.tools_called)
    missing = [tool for tool in task.expected_tools if tool not in called]
    if missing:
        return False, f"expected tools not called: {sorted(missing)}"
    text = outcome.parsed.response.strip()
    if not text or text.upper().startswith(NOT_FOUND_SENTINEL):
        return False, "response block missing or NOT_FOUND"
    return True, ""


def _score_control(outcome: AgentLoopOutcome) -> tuple[bool, str]:
    """Control: any Cortex tool call is a false positive."""
    if outcome.tools_called:
        unique = sorted(set(outcome.tools_called))
        return False, f"control task called Cortex tools: {unique}"
    return True, ""


def _score_near_miss(
    task: EvalTask, outcome: AgentLoopOutcome
) -> tuple[bool, str, bool]:
    """Near-miss: the tempting tool must not be called; covering use is recorded."""
    called = set(outcome.tools_called)
    covered_by_used = task.covered_by in called if task.covered_by else False
    tempting = [tool for tool in task.expected_tools if tool in called]
    if tempting:
        return False, f"tempting tool called: {sorted(tempting)}", covered_by_used
    return True, "", covered_by_used


def score_task(task: EvalTask, outcome: AgentLoopOutcome) -> AgenticTaskResult:
    """Score one completed agent loop against its task kind."""
    covered: bool | None = None
    if task.kind is EvalTaskKind.CONTROL:
        passed, reason = _score_control(outcome)
    elif task.kind is EvalTaskKind.NEAR_MISS:
        passed, reason, covered = _score_near_miss(task, outcome)
    else:
        passed, reason = _score_positive(task, outcome)
    if outcome.error and passed:
        passed, reason = False, outcome.error
    return AgenticTaskResult(
        task_id=task.id,
        task_name=task.name,
        kind=task.kind,
        passed=passed,
        reason=reason,
        tools_called=list(outcome.tools_called),
        turns=outcome.turns,
        turn_cap_reached=outcome.turn_cap_reached,
        response=outcome.parsed.response,
        covered_by_used=covered,
    )


def collect_feedback(
    task: EvalTask, outcome: AgentLoopOutcome
) -> list[ToolFeedbackRecord]:
    """Attach the model's feedback block to each tool the task concerns."""
    text = outcome.parsed.feedback.strip()
    if not text:
        return []
    tools = task.expected_tools or ([task.covered_by] if task.covered_by else [])
    if not tools:
        tools = ["<none>"]
    return [
        ToolFeedbackRecord(task_id=task.id, tool_name=tool, feedback=text)
        for tool in tools
    ]


def _unpaired_reason(
    positives: int, controls: int, near_misses: int
) -> UnpairedReason | None:
    """Return why accuracy may not be reported, or None when the run is paired."""
    if controls == 0 and near_misses == 0:
        return UnpairedReason.NO_NEGATIVE_TASKS
    if controls == 0:
        return UnpairedReason.NO_CONTROL_TASKS
    if near_misses == 0:
        return UnpairedReason.NO_NEAR_MISS_TASKS
    if positives == 0:
        return UnpairedReason.NO_POSITIVE_TASKS
    return None


def _rate(numerator: int, denominator: int) -> float | None:
    """Return numerator/denominator, or None when there is nothing to divide."""
    if denominator == 0:
        return None
    return numerator / denominator


def build_scorecard(results: list[AgenticTaskResult]) -> AgenticScorecard:
    """Aggregate per-task results into a paired scorecard.

    Selection accuracy is computed only when both negative kinds are present;
    otherwise a typed ``unpaired_reason`` is carried instead of a number.
    """
    by_kind = {
        kind: [r for r in results if r.kind is kind and not r.skipped]
        for kind in EvalTaskKind
    }
    positives = by_kind[EvalTaskKind.POSITIVE]
    controls = by_kind[EvalTaskKind.CONTROL]
    near_misses = by_kind[EvalTaskKind.NEAR_MISS]
    control_fp = sum(1 for r in controls if not r.passed)
    near_miss_fp = sum(1 for r in near_misses if not r.passed)
    reason = _unpaired_reason(len(positives), len(controls), len(near_misses))
    passed_positive = sum(1 for r in positives if r.passed)
    accuracy = None if reason is not None else _rate(passed_positive, len(positives))
    return AgenticScorecard(
        paired=reason is None,
        unpaired_reason=reason,
        selection_accuracy=accuracy,
        control_false_positive_rate=_rate(control_fp, len(controls)),
        near_miss_false_positive_rate=_rate(near_miss_fp, len(near_misses)),
        positive_total=len(positives),
        positive_passed=passed_positive,
        control_total=len(controls),
        control_false_positives=control_fp,
        near_miss_total=len(near_misses),
        near_miss_false_positives=near_miss_fp,
    )
