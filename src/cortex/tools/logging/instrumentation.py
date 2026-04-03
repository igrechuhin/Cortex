"""Emit structured LogEvents from MCP tool results (additive; stderr + response fields)."""

from __future__ import annotations

from cortex.core.models import ModelDict
from cortex.tools.logging.logger import emit, format_for_agent
from cortex.tools.logging.models import LogEvent, LogLevel
from cortex.tools.logging.session_context import get_agent_log_context


def _first_failed_check_summary(result: ModelDict) -> tuple[str, str]:
    checks_raw = result.get("checks")
    if isinstance(checks_raw, list):
        for item in checks_raw:
            if not isinstance(item, dict):
                continue
            st = str(item.get("status", "")).lower()
            if st in ("failed", "error"):
                name = str(item.get("name", "check"))
                msg_o = item.get("message")
                msg = str(msg_o).strip() if isinstance(msg_o, str) else name
                return name, msg[:500]
    return "quality", "preflight failed"


def _quality_gate_passed_event(
    trace_id: str | None,
    requirement_id: str | None,
    commit_hash: str | None,
    component: str,
) -> list[LogEvent]:
    return [
        LogEvent(
            event="quality_gate.passed",
            level=LogLevel.INFO,
            component=component,
            trace_id=trace_id,
            requirement_id=requirement_id,
            commit_hash=commit_hash,
            message="Quality gate passed",
            details=None,
        )
    ]


def _quality_gate_failed_event(
    trace_id: str | None,
    requirement_id: str | None,
    commit_hash: str | None,
    component: str,
    msg: str,
    details: dict[str, str | int | bool],
) -> list[LogEvent]:
    return [
        LogEvent(
            event="quality_gate.failed",
            level=LogLevel.ERROR,
            component=component,
            trace_id=trace_id,
            requirement_id=requirement_id,
            commit_hash=commit_hash,
            message=msg[:500],
            details=details,
        )
    ]


def _quality_gate_status_events(
    result: ModelDict,
    trace_id: str | None,
    requirement_id: str | None,
    commit_hash: str | None,
    component: str,
) -> list[LogEvent]:
    """Handle quality gate events when preflight_passed is absent (status-based path)."""
    status = str(result.get("status", "")).lower()
    err_raw = result.get("error")
    err_text = str(err_raw) if err_raw is not None else ""
    if status in ("error", "timeout") or err_text:
        msg = err_text or status or "quality gate error"
        return _quality_gate_failed_event(
            trace_id,
            requirement_id,
            commit_hash,
            component,
            msg[:500],
            {"check": "gate", "error": msg[:300]},
        )
    if status and status not in ("completed", "success"):
        return _quality_gate_failed_event(
            trace_id,
            requirement_id,
            commit_hash,
            component,
            str(result.get("status", "incomplete")),
            {"check": "gate", "error": err_text[:300] if err_text else status},
        )
    return _quality_gate_passed_event(trace_id, requirement_id, commit_hash, component)


def build_quality_gate_log_events(result: ModelDict) -> list[LogEvent]:
    """Build log events for a ``run_quality_gate`` result dict."""
    trace_id, requirement_id, commit_hash = get_agent_log_context()
    component = "run_quality_gate"
    pf_obj = result.get("preflight_passed")
    if pf_obj is True:
        return _quality_gate_passed_event(
            trace_id, requirement_id, commit_hash, component
        )
    if pf_obj is False:
        check_name, short_msg = _first_failed_check_summary(result)
        return _quality_gate_failed_event(
            trace_id,
            requirement_id,
            commit_hash,
            component,
            "Quality gate failed",
            {"check": check_name, "error": short_msg},
        )
    return _quality_gate_status_events(
        result, trace_id, requirement_id, commit_hash, component
    )


def append_agent_log_to_quality_result(result: ModelDict) -> None:
    """Emit stderr events and set ``agent_log`` markdown on ``result``."""
    events = build_quality_gate_log_events(result)
    for ev in events:
        emit(ev)
    if events:
        result["agent_log"] = format_for_agent(events)


def _autofix_error_event(
    trace_id: str | None,
    requirement_id: str | None,
    commit_hash: str | None,
    component: str,
    parsed: ModelDict,
) -> list[LogEvent]:
    err = str(parsed.get("error", parsed.get("message", "autofix error")))
    return [
        LogEvent(
            event="autofix.error",
            level=LogLevel.ERROR,
            component=component,
            trace_id=trace_id,
            requirement_id=requirement_id,
            commit_hash=commit_hash,
            message=err[:500],
            details={"error": err[:300]},
        )
    ]


def _autofix_aggregate_fix_total(parsed: ModelDict) -> int:
    ef, wf, tf = (
        parsed.get("errors_fixed", 0),
        parsed.get("warnings_fixed", 0),
        parsed.get("type_errors_fixed", 0),
    )
    return sum(
        int(v)
        for v in (ef, wf, tf)
        if isinstance(v, int) or (isinstance(v, str) and v.isdigit())
    )


def _autofix_no_files_events(
    trace_id: str | None,
    requirement_id: str | None,
    commit_hash: str | None,
    component: str,
    parsed: ModelDict,
) -> list[LogEvent]:
    total = _autofix_aggregate_fix_total(parsed)
    msg = (
        "Autofix applied (no file paths reported)" if total > 0 else "Autofix completed"
    )
    details: dict[str, str | int | bool] = (
        {"fix_type": "aggregate", "fixes": total} if total > 0 else {"fix_type": "none"}
    )
    return [
        LogEvent(
            event="autofix.applied",
            level=LogLevel.INFO,
            component=component,
            trace_id=trace_id,
            requirement_id=requirement_id,
            commit_hash=commit_hash,
            message=msg,
            details=details,
        )
    ]


def _autofix_truncation_tail_event(
    trace_id: str | None,
    requirement_id: str | None,
    commit_hash: str | None,
    component: str,
    extra_count: int,
) -> LogEvent:
    return LogEvent(
        event="autofix.applied",
        level=LogLevel.INFO,
        component=component,
        trace_id=trace_id,
        requirement_id=requirement_id,
        commit_hash=commit_hash,
        message=f"{extra_count} additional files modified",
        details={"fix_type": "truncated", "extra": extra_count},
    )


def _autofix_per_file_events(
    trace_id: str | None,
    requirement_id: str | None,
    commit_hash: str | None,
    component: str,
    paths: list[str],
) -> list[LogEvent]:
    return [
        LogEvent(
            event="autofix.applied",
            level=LogLevel.INFO,
            component=component,
            trace_id=trace_id,
            requirement_id=requirement_id,
            commit_hash=commit_hash,
            message=f"Updated {path}",
            details={"file": path, "fix_type": "quality"},
        )
        for path in paths
    ]


def _autofix_files_events(
    trace_id: str | None,
    requirement_id: str | None,
    commit_hash: str | None,
    component: str,
    files: list[str],
) -> list[LogEvent]:
    max_files = 15
    head = files[:max_files]
    events = _autofix_per_file_events(
        trace_id, requirement_id, commit_hash, component, head
    )
    if len(files) > max_files:
        events.append(
            _autofix_truncation_tail_event(
                trace_id,
                requirement_id,
                commit_hash,
                component,
                len(files) - max_files,
            )
        )
    return events


def build_autofix_log_events(parsed: ModelDict) -> list[LogEvent]:
    """Build log events from parsed autofix JSON (success or tool error)."""
    trace_id, requirement_id, commit_hash = get_agent_log_context()
    component = "autofix"
    if str(parsed.get("status", "")).lower() == "error":
        return _autofix_error_event(
            trace_id, requirement_id, commit_hash, component, parsed
        )
    files_raw = parsed.get("files_modified")
    files = [str(x) for x in files_raw if str(x)] if isinstance(files_raw, list) else []
    if not files:
        return _autofix_no_files_events(
            trace_id, requirement_id, commit_hash, component, parsed
        )
    return _autofix_files_events(
        trace_id, requirement_id, commit_hash, component, files
    )


def append_agent_log_to_autofix_result(parsed: ModelDict) -> None:
    """Emit stderr events and set ``agent_log`` markdown on ``parsed``."""
    events = build_autofix_log_events(parsed)
    for ev in events:
        emit(ev)
    if events:
        parsed["agent_log"] = format_for_agent(events)


def emit_pipeline_handoff_log(operation: str, pipeline: str, phase: str | None) -> None:
    """Emit one structured line for handoff read/write/init/clear (legacy ops normalized)."""
    op = operation.lower().strip()
    if op in ("write_task", "write_result"):
        op = "write"
    elif op == "read_task":
        op = "read"
    elif op == "read_state":
        op = "read"
    if op not in ("write", "read", "init", "clear"):
        return
    trace_id, requirement_id, commit_hash = get_agent_log_context()
    event_id = f"pipeline_handoff.{op}"
    handoff_key = f"{pipeline}/{phase or ''}"
    emit(
        LogEvent(
            event=event_id,
            level=LogLevel.INFO,
            component="pipeline_handoff",
            trace_id=trace_id,
            requirement_id=requirement_id,
            commit_hash=commit_hash,
            message=f"{op} {handoff_key}".strip(),
            details={
                "pipeline": pipeline,
                "phase": phase or "",
                "handoff_key": handoff_key,
            },
        )
    )
