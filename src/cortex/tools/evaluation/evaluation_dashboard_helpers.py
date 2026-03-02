"""Phase 57: Dashboard formatting helpers for evaluation reports."""

from __future__ import annotations

from cortex.tools.evaluation._models import (
    EvalAnalysis,
    EvalSuiteResult,
    EvalTaskResult,
)
from cortex.tools.usage.redundancy_helpers import RedundancyPayload


def aggregate_tool_metrics(
    suite: EvalSuiteResult,
) -> dict[str, tuple[int, int, int]]:
    """Aggregate per-tool calls, successful, failed across all tasks."""
    agg: dict[str, tuple[int, int, int]] = {}
    for task in suite.tasks:
        for tool_name, m in task.tool_metrics.items():
            prev = agg.get(tool_name, (0, 0, 0))
            agg[tool_name] = (
                prev[0] + m.calls,
                prev[1] + m.successful,
                prev[2] + m.failed,
            )
    return agg


def format_overall_metrics(analysis: EvalAnalysis, suite: EvalSuiteResult) -> list[str]:
    """Format overall metrics section."""
    lines: list[str] = []
    lines.append("# Evaluation Dashboard")
    lines.append("")
    lines.append(f"**Generated:** {suite.generated_at}")
    lines.append("")
    lines.append("## Overall Metrics")
    lines.append("")
    effectiveness_pct = round(analysis.overall_success_rate * 100.0)
    lines.append(f"- **Overall Tool Effectiveness Score:** {effectiveness_pct}/100")
    lines.append(f"- **Overall Success Rate:** {analysis.overall_success_rate:.1%}")
    lines.append(f"- **Total Tasks:** {analysis.total_tasks}")
    lines.append(f"- **Tasks with No Data:** {analysis.tasks_with_no_data}")
    lines.append(f"- **Tasks Unavailable:** {analysis.tasks_unavailable}")
    lines.append(f"- **Average Calls per Task:** {analysis.average_calls_per_task:.1f}")
    lines.append("")
    return lines


def format_top_tools_sections(suite: EvalSuiteResult) -> list[str]:
    """Format Top 5 tools by usage and by improvement needed."""
    lines: list[str] = []
    agg = aggregate_tool_metrics(suite)
    if not agg:
        return lines

    by_usage = sorted(
        agg.items(),
        key=lambda x: x[1][0],
        reverse=True,
    )[:5]
    by_improvement = sorted(
        agg.items(),
        key=lambda x: (x[1][2], -x[1][0]),
        reverse=True,
    )[:5]

    lines.append("## Top 5 Tools by Usage")
    lines.append("")
    for i, (tool_name, (calls, successful, _failed)) in enumerate(by_usage, 1):
        rate = (successful / calls * 100.0) if calls else 0.0
        lines.append(f"{i}. **{tool_name}** — {calls} calls ({rate:.0f}% success)")
    lines.append("")

    lines.append("## Top 5 Tools by Improvement Needed")
    lines.append("")
    for i, (tool_name, (calls, successful, failed)) in enumerate(by_improvement, 1):
        rate = (successful / calls * 100.0) if calls else 0.0
        lines.append(
            f"{i}. **{tool_name}** — {failed} failures, {calls} calls ({rate:.0f}% success)"
        )
    lines.append("")
    return lines


def format_category_success_rates(analysis: EvalAnalysis) -> list[str]:
    """Format success rate by category section."""
    lines: list[str] = []
    if analysis.success_rate_by_category:
        lines.append("## Success Rate by Category")
        lines.append("")
        for category, rate in sorted(
            analysis.success_rate_by_category.items(),
            key=lambda x: x[1],
            reverse=True,
        ):
            lines.append(f"- **{category}:** {rate:.1%}")
        lines.append("")
    return lines


def format_error_patterns(analysis: EvalAnalysis) -> list[str]:
    """Format top error patterns section."""
    lines: list[str] = []
    if analysis.top_error_patterns:
        lines.append("## Top Error Patterns")
        lines.append("")
        for i, pattern in enumerate(analysis.top_error_patterns[:10], 1):
            tools_str = ", ".join(pattern.affected_tools[:5])
            if len(pattern.affected_tools) > 5:
                tools_str += f" (+{len(pattern.affected_tools) - 5} more)"
            lines.append(f"{i}. **{pattern.error_type}** ({pattern.count} occurrences)")
            lines.append(f"   - Affected tools: {tools_str}")
            lines.append("")
    return lines


def _format_redundancy_repeated(redundancy: RedundancyPayload) -> list[str]:
    """Format Top Repeated Identical Calls subsection."""
    lines: list[str] = []
    if not redundancy.repeated_identical:
        return lines
    lines.append("### Top Repeated Identical Calls")
    lines.append("")
    for i, p in enumerate(redundancy.repeated_identical[:5], 1):
        lines.append(
            f"{i}. **{p.tool_name}** — {p.total_occurrences} occurrences "
            + f"in {p.session_count} sessions (max {p.max_per_session}/session)"
        )
    lines.append("")
    return lines


def _format_redundancy_sequential(redundancy: RedundancyPayload) -> list[str]:
    """Format Top Sequential Same-Tool Runs subsection."""
    lines: list[str] = []
    if not redundancy.sequential_same_tool:
        return lines
    lines.append("### Top Sequential Same-Tool Runs")
    lines.append("")
    for i, p in enumerate(redundancy.sequential_same_tool[:5], 1):
        lines.append(
            f"{i}. **{p.tool_name}** — max run {p.max_run_length} "
            + f"in {p.session_count} sessions"
        )
    lines.append("")
    return lines


def _format_redundancy_error_by_param(redundancy: RedundancyPayload) -> list[str]:
    """Format Error Rate by Parameter subsection."""
    lines: list[str] = []
    if not redundancy.error_rate_by_param:
        return lines
    lines.append("### Error Rate by Parameter")
    lines.append("")
    for i, p in enumerate(redundancy.error_rate_by_param[:5], 1):
        lines.append(
            f"{i}. **{p.tool_name}** — '{p.param_or_error}' "
            + f"{p.error_rate:.0%} ({p.error_count}/{p.total_calls})"
        )
    lines.append("")
    return lines


def format_redundancy(redundancy: RedundancyPayload | None) -> list[str]:
    """Format redundancy metrics section (Anthropic Step 3)."""
    lines: list[str] = []
    if redundancy is None or redundancy.total_events == 0:
        return lines
    if not (
        redundancy.repeated_identical
        or redundancy.sequential_same_tool
        or redundancy.error_rate_by_param
        or redundancy.tool_improvement_hints
    ):
        return lines
    lines.append("## Redundancy Metrics")
    lines.append("")
    lines.append(f"Window: {redundancy.days} days, {redundancy.total_events} events.")
    lines.append("")
    lines.extend(_format_redundancy_repeated(redundancy))
    lines.extend(_format_redundancy_sequential(redundancy))
    lines.extend(_format_redundancy_error_by_param(redundancy))
    if redundancy.tool_improvement_hints:
        lines.append("### Tool Improvement Hints")
        lines.append("")
        for hint in redundancy.tool_improvement_hints[:5]:
            lines.append(f"- {hint}")
        lines.append("")
    return lines


def format_token_efficiency(analysis: EvalAnalysis) -> list[str]:
    """Format token efficiency trends section (when token data is available)."""
    lines: list[str] = []
    has_overall = analysis.average_tokens_per_task > 0
    has_by_category = bool(analysis.token_consumption_by_category)
    if not has_overall and not has_by_category:
        return lines
    lines.append("## Token Efficiency Trends")
    lines.append("")
    if has_overall:
        lines.append(
            f"- **Average tokens per task:** {analysis.average_tokens_per_task:,.0f}"
        )
        lines.append("")
    if has_by_category:
        lines.append("**Average tokens per task by category:**")
        for category, avg_tokens in sorted(
            analysis.token_consumption_by_category.items(),
            key=lambda x: x[1],
            reverse=True,
        ):
            lines.append(f"- **{category}:** {avg_tokens:,.0f}")
        lines.append("")
    return lines


def format_single_task(task: EvalTaskResult) -> list[str]:
    """Format a single task entry."""
    status_emoji = (
        "✅" if task.status == "success" else "⚠️" if task.status == "mixed" else "❌"
    )
    lines = [
        f"- {status_emoji} **{task.task_name}** ({task.task_id})",
        f"  - Status: {task.status}",
        f"  - Success Rate: {task.success_rate:.1%}",
        f"  - Total Calls: {task.total_calls}",
    ]
    if task.error_types:
        top_error = max(task.error_types.items(), key=lambda x: x[1])
        lines.append(f"  - Top Error: {top_error[0]} ({top_error[1]} occurrences)")
    lines.append("")
    return lines


def format_task_details(suite: EvalSuiteResult) -> list[str]:
    """Format task-level details section."""
    lines: list[str] = []
    if suite.tasks:
        lines.append("## Task Details")
        lines.append("")
        tasks_by_category: dict[str, list[EvalTaskResult]] = {}
        for task in suite.tasks:
            category = task.category
            if category not in tasks_by_category:
                tasks_by_category[category] = []
            tasks_by_category[category].append(task)
        for category in sorted(tasks_by_category.keys()):
            lines.append(f"### {category.title()} Tasks")
            lines.append("")
            for task in sorted(
                tasks_by_category[category],
                key=lambda t: t.success_rate,
                reverse=True,
            ):
                lines.extend(format_single_task(task))
    return lines


def generate_evaluation_dashboard(
    analysis: EvalAnalysis,
    suite: EvalSuiteResult,
    redundancy: RedundancyPayload | None = None,
) -> str:
    """Generate Markdown dashboard from evaluation analysis."""
    lines: list[str] = []
    lines.extend(format_overall_metrics(analysis, suite))
    lines.extend(format_top_tools_sections(suite))
    lines.extend(format_category_success_rates(analysis))
    lines.extend(format_error_patterns(analysis))
    lines.extend(format_token_efficiency(analysis))
    lines.extend(format_redundancy(redundancy))
    lines.extend(format_task_details(suite))
    return "\n".join(lines)
