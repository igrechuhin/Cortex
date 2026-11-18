"""Preflight-passed determination shared by the commit pipeline.

``compute_preflight_passed`` is the single source of truth for whether Phase A
checks (quality/tests) plus markdown lint succeeded with zero errors. It is
used by the detached Phase A runner behind ``run_quality_gate()``.
"""

from __future__ import annotations

from collections.abc import Callable
from contextvars import ContextVar

from cortex.core.models import JsonDict, ModelDict

# Bound only by the detached ordinary gate; no effect in repair or direct runs.
swift_test_preflight: ContextVar[Callable[[], bool] | None] = ContextVar(
    "swift_test_preflight", default=None
)


def compute_preflight_passed(
    execute_result: ModelDict,
    markdown_result: JsonDict | None,
) -> bool:
    """Determine whether preflight checks passed with zero errors."""
    status = str(execute_result.get("status"))
    exec_success = status == "success"
    if not exec_success:
        return False

    return markdown_result is None or markdown_preflight_passed(markdown_result)


def markdown_preflight_passed(markdown_result: JsonDict) -> bool:
    """Check the same required Markdown verdict before tests and in the receipt."""
    files_with_errors_obj = markdown_result.get("files_with_errors", 0)
    files_with_errors = (
        int(files_with_errors_obj)
        if isinstance(files_with_errors_obj, (int, str))
        else 0
    )
    error_message = markdown_result.get("error_message")
    markdown_status = str(markdown_result.get("status", "success"))
    markdown_success = files_with_errors == 0 and error_message is None
    markdown_success = markdown_success and markdown_status != "error"
    return markdown_success
