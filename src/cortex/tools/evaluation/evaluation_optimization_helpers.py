"""Helpers for tool description optimization (Plan: Evaluation Framework Maturation Step 4).

Pulls error and usage data for a tool, suggests description improvements,
and generates an A/B test plan. Used by optimize_tool_description MCP tool.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.pydantic_extra import EXTRA_FORBID
from cortex.managers.usage_models import ToolUsageEvent
from cortex.managers.usage_tracker import UsageTracker


def _to_int(val: object, default: int = 0) -> int:
    """Coerce object to int for usage stat fields."""
    if isinstance(val, int) and not isinstance(val, bool):
        return val
    if isinstance(val, float):
        return int(val)
    return default


def _to_error_types_dict(val: object) -> dict[str, int]:
    """Build dict[str, int] from raw error_types field."""
    if not isinstance(val, dict):
        return {}
    d = cast(dict[str, object], val)
    return {str(k): _to_int(d[k]) for k in d}


class ToolDescriptionOptimizationPayload(BaseModel):
    """Payload for optimize_tool_description response."""

    model_config = ConfigDict(extra=EXTRA_FORBID)

    status: str = Field(description="success or unavailable")
    tool_name: str = Field(description="Target tool name")
    total_calls: int = Field(ge=0, description="Total calls in window")
    error_rate: float = Field(ge=0.0, le=1.0, description="Failed calls / total_calls")
    meets_optimization_threshold: bool = Field(
        description="True if error_rate > 5% or redundancy/retry signals suggest optimization"
    )
    suggestions: list[str] = Field(
        default_factory=list,
        description="Description improvement suggestions",
    )
    ab_test_plan: list[str] = Field(
        default_factory=list,
        description="Steps for A/B testing description changes",
    )
    error_types: dict[str, int] = Field(
        default_factory=dict,
        description="Error type to count in window",
    )
    project_root: str = Field(default="", description="Project root path")
    message: str | None = Field(
        default=None,
        description="Reason when status is unavailable",
    )


ERROR_RATE_THRESHOLD = 0.05
"""Error rate above which we recommend description optimization (5%)."""


def _has_validation_errors(error_types: dict[str, int]) -> bool:
    """True if any error type name suggests validation errors."""
    return any("Validation" in et or "validation" in et.lower() for et in error_types)


def _has_param_failures(failed_events: list[ToolUsageEvent]) -> bool:
    """True if any failed event has param_validation_failure set."""
    return any(
        e.param_validation_failure and e.param_validation_failure.strip()
        for e in failed_events
    )


def _has_retries(failed_events: list[ToolUsageEvent]) -> bool:
    """True if any failed event has retry_count > 0."""
    return any(e.retry_count and e.retry_count > 0 for e in failed_events)


def _build_suggestions(
    total_calls: int,
    failed_calls: int,
    error_types: dict[str, int],
    failed_events: list[ToolUsageEvent],
) -> list[str]:
    """Build description improvement suggestions from usage and error data."""
    if total_calls == 0:
        return ["No usage data yet. Add USE WHEN and EXAMPLES to the tool description."]
    suggestions: list[str] = []
    if failed_calls > 0:
        suggestions.append(
            "Clarify when to use (USE WHEN) and required parameters to reduce call failures."
        )
    if _has_validation_errors(error_types):
        suggestions.append(
            "Add parameter examples and type hints to reduce validation errors."
        )
    if _has_param_failures(failed_events):
        suggestions.append(
            "Document parameter constraints and RETURNS/Args to avoid param misuse."
        )
    if _has_retries(failed_events):
        suggestions.append(
            "Clarify expected inputs and outputs to avoid retries and redundant calls."
        )
    suggestions = suggestions or [
        "Consider adding USE WHEN and EXAMPLES if usage is low or inconsistent."
    ]
    return suggestions[:5]


def _build_ab_test_plan() -> list[str]:
    """Return steps for A/B testing a tool description change."""
    return [
        "Run run_tool_evaluation(mode='fast') to capture baseline pass rate.",
        "Update the tool description in the MCP descriptor (e.g. USE WHEN, EXAMPLES, Args).",
        "Run run_tool_evaluation(mode='fast') again with the same task set.",
        "Compare execution_summary.execution_passed/execution_total_run; deploy if pass rate improves.",
        "Optionally run run_tool_optimization_workflow to record baseline vs optimized in optimization_history.json.",
    ]


def _payload_unavailable(
    root: Path, tool_name: str
) -> ToolDescriptionOptimizationPayload:
    """Build payload when usage tracker is not available."""
    return ToolDescriptionOptimizationPayload(
        status="unavailable",
        tool_name=tool_name,
        total_calls=0,
        error_rate=0.0,
        meets_optimization_threshold=False,
        suggestions=[],
        ab_test_plan=_build_ab_test_plan(),
        project_root=str(root),
        message="Usage tracker not available",
    )


def _payload_no_tools(root: Path, tool_name: str) -> ToolDescriptionOptimizationPayload:
    """Build payload when no usage stats exist for the tool."""
    return ToolDescriptionOptimizationPayload(
        status="success",
        tool_name=tool_name,
        total_calls=0,
        error_rate=0.0,
        meets_optimization_threshold=False,
        suggestions=_build_suggestions(0, 0, {}, []),
        ab_test_plan=_build_ab_test_plan(),
        error_types={},
        project_root=str(root),
    )


def _parse_first_tool_stats(
    tools_list: list[dict[str, object]],
) -> tuple[int, int, dict[str, int]]:
    """Extract total_calls, failed_calls, error_types from first tool stat dict."""
    raw = tools_list[0]
    total_calls = _to_int(raw.get("total_calls", 0))
    failed_calls = _to_int(raw.get("failed_calls", 0))
    error_types = _to_error_types_dict(raw.get("error_types"))
    return total_calls, failed_calls, error_types


def _meets_optimization_threshold(
    error_rate: float,
    failed_events: list[ToolUsageEvent],
) -> bool:
    """True if error rate > 5% or events show param/retry signals."""
    if error_rate > ERROR_RATE_THRESHOLD:
        return True
    return any(
        bool(e.param_validation_failure or (e.retry_count and e.retry_count > 0))
        for e in failed_events
    )


def _tools_list_from_stats_result(
    stats_result: dict[str, object],
) -> list[dict[str, object]]:
    """Parse tools list from get_usage_stats result."""
    tools_raw: object = stats_result.get("tools") or []
    raw_list: list[object] = (
        cast(list[object], tools_raw) if isinstance(tools_raw, list) else []
    )
    return [cast(dict[str, object], t) for t in raw_list if isinstance(t, dict)]


def _payload_success(
    root: Path,
    tool_name: str,
    total_calls: int,
    error_types: dict[str, int],
    error_rate: float,
    suggestions: list[str],
    meets: bool,
) -> ToolDescriptionOptimizationPayload:
    """Build success payload with stats and suggestions."""
    return ToolDescriptionOptimizationPayload(
        status="success",
        tool_name=tool_name,
        total_calls=total_calls,
        error_rate=round(error_rate, 4),
        meets_optimization_threshold=meets,
        suggestions=suggestions,
        ab_test_plan=_build_ab_test_plan(),
        error_types=error_types,
        project_root=str(root),
    )


def _build_payload_from_stats(
    root: Path,
    tool_name: str,
    total_calls: int,
    failed_calls: int,
    error_types: dict[str, int],
    error_rate: float,
    failed_events: list[ToolUsageEvent],
) -> ToolDescriptionOptimizationPayload:
    """Build success payload from parsed stats and failed events."""
    suggestions = _build_suggestions(
        total_calls, failed_calls, error_types, failed_events
    )
    meets = _meets_optimization_threshold(error_rate, failed_events)
    return _payload_success(
        root,
        tool_name,
        total_calls,
        error_types,
        error_rate,
        suggestions,
        meets,
    )


async def _fetch_failed_events(
    tracker: UsageTracker,
    start: datetime,
    end: datetime,
    tool_name: str,
) -> list[ToolUsageEvent]:
    """Fetch failed usage events for the tool in the date range."""
    return await tracker.search_usage(
        start_date=start,
        end_date=end,
        tool_name=tool_name,
        success=False,
        limit=50,
        query=None,
    )


async def _fetch_and_build_payload(
    root: Path,
    tracker: UsageTracker,
    tool_name: str,
    start: datetime,
    end: datetime,
) -> ToolDescriptionOptimizationPayload:
    """Fetch usage/failed events and build success payload. Caller ensures tracker is not None."""
    stats_result = await tracker.get_usage_stats(
        start_date=start, end_date=end, tool_name=tool_name
    )
    tools_list = _tools_list_from_stats_result(stats_result)
    if not tools_list:
        return _payload_no_tools(root, tool_name)
    total_calls, failed_calls, error_types = _parse_first_tool_stats(tools_list)
    error_rate = (failed_calls / total_calls) if total_calls else 0.0
    failed_events = await _fetch_failed_events(tracker, start, end, tool_name)
    return _build_payload_from_stats(
        root,
        tool_name,
        total_calls,
        failed_calls,
        error_types,
        error_rate,
        failed_events,
    )


async def get_tool_description_optimization_payload(
    root: Path,
    tracker: UsageTracker | None,
    tool_name: str,
    days: int = 30,
) -> ToolDescriptionOptimizationPayload:
    """Build optimization payload for a single tool from usage and error data."""
    if tracker is None:
        return _payload_unavailable(root, tool_name)
    end = datetime.now(UTC)
    start = end - timedelta(days=days)
    return await _fetch_and_build_payload(root, tracker, tool_name, start, end)
