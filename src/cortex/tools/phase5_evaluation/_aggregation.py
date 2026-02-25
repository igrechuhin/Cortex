"""
Phase 57: Aggregation helpers for evaluation suite.

_AggregatedEvents and _AnalysisAccumulator. Extracted for Phase 9.1.4.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from cortex.managers.usage_models import ToolUsageEvent

from ._models import (
    ErrorPattern,
    EvalTaskResult,
    EvalTaskStatus,
    ToolTaskMetrics,
)


def _empty_category_success() -> dict[str, list[float]]:
    """Typed default factory for category_success accumulator."""
    return {}


def _empty_error_counter() -> dict[str, ErrorPattern]:
    """Typed default factory for error_counter accumulator."""
    return {}


@dataclass(slots=True)
class AggregatedEvents:
    """Helper for aggregating ToolUsageEvent metrics (package-internal)."""

    events: list[ToolUsageEvent]

    @property
    def total_calls(self) -> int:
        return len(self.events)

    @property
    def successful_calls(self) -> int:
        return sum(1 for e in self.events if e.success)

    @property
    def failed_calls(self) -> int:
        return sum(1 for e in self.events if not e.success)

    @property
    def success_rate(self) -> float:
        return (
            float(self.successful_calls) / float(self.total_calls)
            if self.total_calls
            else 0.0
        )

    @property
    def avg_duration_ms(self) -> float:
        if not self.events:
            return 0.0
        durations = [e.duration_ms for e in self.events]
        return float(sum(durations) / len(durations))

    @property
    def total_duration_ms(self) -> float:
        return float(sum(e.duration_ms for e in self.events))

    @property
    def error_types(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for e in self.events:
            if e.error_type:
                out[e.error_type] = out.get(e.error_type, 0) + 1
        return out

    def tool_metrics(self) -> dict[str, ToolTaskMetrics]:
        """Per-tool call and success counts for dashboard aggregation."""
        by_tool: dict[str, list[ToolUsageEvent]] = {}
        for e in self.events:
            by_tool.setdefault(e.tool_name, []).append(e)
        out: dict[str, ToolTaskMetrics] = {}
        for name, evs in by_tool.items():
            successful = sum(1 for e in evs if e.success)
            out[name] = ToolTaskMetrics(
                calls=len(evs),
                successful=successful,
                failed=len(evs) - successful,
            )
        return out


@dataclass(slots=True)
class AnalysisAccumulator:
    """Accumulator for evaluation analysis metrics (package-internal)."""

    total_success_rate: float = 0.0
    total_calls: int = 0
    tasks_with_no_data: int = 0
    tasks_unavailable: int = 0
    category_success: dict[str, list[float]] = field(
        default_factory=_empty_category_success
    )
    error_counter: dict[str, ErrorPattern] = field(default_factory=_empty_error_counter)

    def add_result(self, result: EvalTaskResult) -> None:
        """Update aggregate metrics and error counters for a single task."""
        self.total_success_rate += result.success_rate
        self.total_calls += result.total_calls
        if result.status == EvalTaskStatus.NO_DATA:
            self.tasks_with_no_data += 1
        if result.status == EvalTaskStatus.UNAVAILABLE:
            self.tasks_unavailable += 1

        self.category_success.setdefault(result.category, []).append(
            result.success_rate
        )

        for err_type, count in result.error_types.items():
            existing = self.error_counter.get(err_type)
            tools: set[str] = (
                set(existing.affected_tools) if existing is not None else set()
            )
            tools.update(result.evaluated_tools)
            total_count = (existing.count if existing is not None else 0) + count
            self.error_counter[err_type] = ErrorPattern(
                error_type=err_type,
                count=total_count,
                affected_tools=sorted(tools),
            )
