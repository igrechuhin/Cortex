"""Phase 57 Step 2: Execution-based evaluation harness.

Runs tasks that have an execution spec: invoke tool, capture result,
apply deterministic check (schema_valid, contains, exact_match).
Supports Fast (10 tasks), Full (all), Focused (by category) modes.
"""

from __future__ import annotations

import json
import time

from cortex.tools.evaluation._models import (
    EvalRunMode,
    EvalTask,
    ExecutionExpectSpec,
    ExecutionExpectType,
    ExecutionResultEntry,
    ExecutionSpec,
    ExecutionSummary,
)


class ExecutionResult:
    """Result of running one execution-based eval task."""

    __slots__ = ("task_id", "passed", "message", "duration_ms", "skipped")

    def __init__(
        self,
        task_id: str,
        passed: bool,
        message: str,
        duration_ms: float = 0.0,
        skipped: bool = False,
    ) -> None:
        self.task_id = task_id
        self.passed = passed
        self.message = message
        self.duration_ms = duration_ms
        self.skipped = skipped

    def to_dict(self) -> dict[str, object]:
        return {
            "task_id": self.task_id,
            "passed": self.passed,
            "message": self.message,
            "duration_ms": self.duration_ms,
            "skipped": self.skipped,
        }


def _check_expect(output: str, expect: ExecutionExpectSpec) -> tuple[bool, str]:
    """Apply deterministic expect check; return (passed, message)."""
    if expect.type == ExecutionExpectType.CONTAINS:
        if expect.substring is None:
            return False, "expect type contains requires substring"
        if expect.substring in output:
            return True, "output contains expected substring"
        return False, f"output missing substring: {expect.substring!r}"

    if expect.type == ExecutionExpectType.SCHEMA_VALID:
        try:
            data = json.loads(output)
        except json.JSONDecodeError as e:
            return False, f"output not valid JSON: {e}"
        if not isinstance(data, dict):
            return False, "output JSON is not an object"
        keys = expect.schema_keys or []
        missing = [k for k in keys if k not in data]
        if missing:
            return False, f"output missing keys: {missing}"
        return True, "output has required keys"

    if expect.type == ExecutionExpectType.EXACT_MATCH:
        try:
            data = json.loads(output)
        except json.JSONDecodeError:
            return False, "output not valid JSON for exact_match"
        if data == expect.expected_value:
            return True, "output matches expected value"
        return False, "output does not match expected value"

    return False, f"unknown expect type: {expect.type.value}"


async def _invoke_tool(tool_name: str, arguments: dict[str, object]) -> str:
    """Invoke a registered tool by name with given arguments; return output string."""
    from cortex.tools.evaluation_execution_registry import get_tool_invoker

    invoker = get_tool_invoker(tool_name)
    if invoker is None:
        raise ValueError(f"no invoker registered for tool: {tool_name}")
    return await invoker(arguments)


async def run_one_execution(task: EvalTask) -> ExecutionResult:
    """Run a single task's execution spec if present; otherwise skipped."""
    if task.execution is None:
        return ExecutionResult(
            task_id=task.id,
            passed=True,
            message="no execution spec (usage-based only)",
            skipped=True,
        )
    spec: ExecutionSpec = task.execution
    t0 = time.monotonic()
    try:
        output = await _invoke_tool(spec.tool, spec.arguments)
        passed, message = _check_expect(output, spec.expect)
        duration_ms = (time.monotonic() - t0) * 1000
        return ExecutionResult(
            task_id=task.id,
            passed=passed,
            message=message,
            duration_ms=duration_ms,
            skipped=False,
        )
    except Exception as e:
        duration_ms = (time.monotonic() - t0) * 1000
        return ExecutionResult(
            task_id=task.id,
            passed=False,
            message=f"execution error: {e!s}",
            duration_ms=duration_ms,
            skipped=False,
        )


def _filter_tasks_by_mode(
    tasks: list[EvalTask],
    mode: EvalRunMode,
    category: str | None,
    fast_cap: int = 10,
) -> list[EvalTask]:
    """Filter tasks for fast (first N with execution), full (all), or focused (category)."""
    if mode == EvalRunMode.FOCUSED and category:
        out = [t for t in tasks if t.category.value == category]
        return out
    if mode == EvalRunMode.FAST:
        with_exec = [t for t in tasks if t.execution is not None]
        return with_exec[:fast_cap]
    return list(tasks)


async def run_execution_suite(
    tasks: list[EvalTask],
    mode: EvalRunMode = EvalRunMode.FULL,
    category: str | None = None,
    fast_cap: int = 10,
) -> list[ExecutionResult]:
    """Run execution-based evals for tasks that have execution spec.

    mode: FAST (first fast_cap tasks with execution), FULL (all),
          FOCUSED (category filter).
    """
    filtered = _filter_tasks_by_mode(tasks, mode, category, fast_cap)
    results: list[ExecutionResult] = []
    for task in filtered:
        if task.execution is None and mode != EvalRunMode.FULL:
            continue
        result = await run_one_execution(task)
        results.append(result)
    return results


def build_execution_summary(
    results: list[ExecutionResult],
) -> ExecutionSummary:
    """Build ExecutionSummary for RunToolEvaluationPayload."""
    run = [r for r in results if not r.skipped]
    passed = sum(1 for r in run if r.passed)
    failed = len(run) - passed
    skipped = sum(1 for r in results if r.skipped)
    entries = [ExecutionResultEntry.model_validate(r.to_dict()) for r in results]
    return ExecutionSummary(
        execution_passed=passed,
        execution_failed=failed,
        execution_skipped=skipped,
        execution_total_run=len(run),
        results=entries,
    )
