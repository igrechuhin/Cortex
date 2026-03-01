"""Eval-fast check for pre-commit tools.

Extracted from pre_commit_tools to keep it under 400 lines.
"""

import json
import logging
from typing import cast

from cortex.services.framework_adapters.base import CheckResult
from cortex.tools.execution.pre_commit_helpers import PreCommitCheck

# Type for JSON numeric/string values that int() accepts (avoids Any)
_IntConvertible = int | float | str

logger = logging.getLogger(__name__)

# Eval-fast pass rate threshold (85% per plan Step 3)
EVAL_FAST_PASS_RATE_THRESHOLD = 0.85


def parse_eval_execution_summary(payload: dict[str, object]) -> tuple[int, int, float]:
    """Extract passed, total, rate from run_tool_evaluation payload."""
    exec_summary = cast(dict[str, object], payload.get("execution_summary") or {})
    passed = int(cast(_IntConvertible, exec_summary.get("execution_passed", 0)))
    total = int(cast(_IntConvertible, exec_summary.get("execution_total_run", 0)))
    rate = (passed / total) if total else 1.0
    return passed, total, rate


def build_eval_fast_result(
    passed: int, total: int, rate: float, success: bool
) -> CheckResult:
    """Build CheckResult for eval_fast from pass stats."""
    pct = round(rate * 100, 1)
    thresh_pct = round(EVAL_FAST_PASS_RATE_THRESHOLD * 100)
    output = f"eval_fast: {passed}/{total} passed ({pct}%). Threshold: {thresh_pct}%."
    errors: list[str] = []
    if not success:
        errors.append(f"Eval fast pass rate {pct}% is below threshold {thresh_pct}%.")
    return CheckResult(
        check_type=PreCommitCheck.EVAL_FAST.value,
        success=success,
        output=output,
        errors=errors,
        warnings=[],
        files_modified=[],
    )


async def run_eval_fast_check(ctx: object | None) -> CheckResult:
    """Run fast eval (10 tasks) and return CheckResult; fail if pass rate < 85%."""
    from cortex.tools.evaluation import run_tool_evaluation

    try:
        payload_str = await run_tool_evaluation(
            task_ids=None,
            mode="fast",
            category=None,
            ctx=ctx,
        )
        payload = cast(dict[str, object], json.loads(payload_str))
        passed, total, rate = parse_eval_execution_summary(payload)
        success = rate >= EVAL_FAST_PASS_RATE_THRESHOLD
        return build_eval_fast_result(passed, total, rate, success)
    except Exception as e:
        logger.exception("eval_fast check failed")
        return CheckResult(
            check_type=PreCommitCheck.EVAL_FAST.value,
            success=False,
            output=f"eval_fast failed: {e!s}",
            errors=[f"eval_fast check failed: {e!s}"],
            warnings=[],
            files_modified=[],
        )
