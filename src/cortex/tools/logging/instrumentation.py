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


def build_quality_gate_log_events(result: ModelDict) -> list[LogEvent]:
    """Build log events for a ``run_quality_gate`` result dict."""
    trace_id, requirement_id, commit_hash = get_agent_log_context()
    component = "run_quality_gate"

    def _failed(msg: str, details: dict[str, str | int | bool]) -> list[LogEvent]:
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

    pf_obj = result.get("preflight_passed")
    if pf_obj is True:
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
    if pf_obj is False:
        check_name, short_msg = _first_failed_check_summary(result)
        return _failed(
            "Quality gate failed",
            {"check": check_name, "error": short_msg},
        )

    status = str(result.get("status", "")).lower()
    err_raw = result.get("error")
    err_text = str(err_raw) if err_raw is not None else ""
    if status in ("error", "timeout") or err_text:
        msg = err_text or status or "quality gate error"
        return _failed(msg[:500], {"check": "gate", "error": msg[:300]})
    if status and status not in ("completed", "success"):
        return _failed(
            str(result.get("status", "incomplete")),
            {"check": "gate", "error": err_text[:300] if err_text else status},
        )
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


def append_agent_log_to_quality_result(result: ModelDict) -> None:
    """Emit stderr events and set ``agent_log`` markdown on ``result``."""
    events = build_quality_gate_log_events(result)
    for ev in events:
        emit(ev)
    if events:
        result["agent_log"] = format_for_agent(events)


def build_autofix_log_events(parsed: ModelDict) -> list[LogEvent]:
    """Build log events from parsed autofix JSON (success or tool error)."""
    trace_id, requirement_id, commit_hash = get_agent_log_context()
    component = "autofix"
    status = str(parsed.get("status", "")).lower()
    if status == "error":
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
    files_raw = parsed.get("files_modified")
    files: list[str] = []
    if isinstance(files_raw, list):
        files = [str(x) for x in files_raw if str(x)]
    events: list[LogEvent] = []
    if not files:
        ef = parsed.get("errors_fixed", 0)
        wf = parsed.get("warnings_fixed", 0)
        tf = parsed.get("type_errors_fixed", 0)
        total = 0
        for v in (ef, wf, tf):
            if isinstance(v, int):
                total += v
            elif isinstance(v, str) and v.isdigit():
                total += int(v)
        if total > 0:
            events.append(
                LogEvent(
                    event="autofix.applied",
                    level=LogLevel.INFO,
                    component=component,
                    trace_id=trace_id,
                    requirement_id=requirement_id,
                    commit_hash=commit_hash,
                    message="Autofix applied (no file paths reported)",
                    details={"fix_type": "aggregate", "fixes": total},
                )
            )
        else:
            events.append(
                LogEvent(
                    event="autofix.applied",
                    level=LogLevel.INFO,
                    component=component,
                    trace_id=trace_id,
                    requirement_id=requirement_id,
                    commit_hash=commit_hash,
                    message="Autofix completed",
                    details={"fix_type": "none"},
                )
            )
        return events
    max_files = 15
    for path in files[:max_files]:
        events.append(
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
        )
    if len(files) > max_files:
        events.append(
            LogEvent(
                event="autofix.applied",
                level=LogLevel.INFO,
                component=component,
                trace_id=trace_id,
                requirement_id=requirement_id,
                commit_hash=commit_hash,
                message=f"{len(files) - max_files} additional files modified",
                details={"fix_type": "truncated", "extra": len(files) - max_files},
            )
        )
    return events


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
