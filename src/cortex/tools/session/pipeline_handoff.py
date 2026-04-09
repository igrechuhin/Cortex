"""Pipeline handoff tool — structured inter-phase communication via session files.

Each pipeline run (commit, implement, …) creates a session-scoped subfolder
under .cortex/.session/{session_id}/ and exchanges structured JSON between
pipeline phases through that folder.

## Simplified API (4 operations)

    pipeline_handoff(operation="init",  pipeline="commit")
    pipeline_handoff(operation="write", pipeline="commit", phase="checks",
                     data='{"status": "passed", "coverage": 0.94}')
    pipeline_handoff(operation="read",  pipeline="commit", phase="checks")
    pipeline_handoff(operation="read",  pipeline="commit")  # full state
    pipeline_handoff(operation="clear", pipeline="commit")

Legacy operation names (write_task, read_task, write_result, read_state) are
mapped to the simplified API automatically.

## Files on disk

.cortex/.session/{session_id}/{pipeline}/
    pipeline.json             — cumulative state updated after each write
    {phase}-result.json       — per-phase data
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import cast

from cortex.core.constants import MCP_TOOL_TIMEOUT_FAST
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_annotations import safe_write_annotations
from cortex.core.mcp_stability import ensure_usage_context, mcp_tool_wrapper
from cortex.core.usage_context import get_or_resolve_project_root
from cortex.server import mcp
from cortex.tools.logging.instrumentation import emit_pipeline_handoff_log

from .pipeline_handoff_io import (
    extract_routing_keys,
    op_clear,
    op_init,
    op_read_state,
    op_read_task,
    op_rollback,
    op_snapshot,
    op_write_result,
    op_write_task,
)
from .pipeline_handoff_validation import validate_phase, validate_pipeline

# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_OPS_NEED_PHASE = frozenset({"write_task", "read_task", "write_result", "write"})


def _resolve_zero_arg_defaults(
    operation: str,
    pipeline: str,
    phase: str | None,
) -> tuple[str, str, str | None]:
    """Fall back to session config when Cursor strips all tool arguments.

    Cursor's MCP bridge sends {} for every tool call, leaving all parameters
    at their declared defaults.  Detect this by checking whether both
    ``operation`` and ``pipeline`` are still at their default values, then read
    ``operation``, ``pipeline``, and ``phase`` from the session config file
    written by the orchestrator prompt before it called this tool.

    If session config is absent or incomplete the original values are returned
    unchanged, so non-Cursor callers are unaffected.
    """
    if operation != "read_state" or pipeline != "default":
        # At least one arg was explicitly set — not a zero-arg call.
        return operation, pipeline, phase

    from cortex.core.session_config import read_session_config

    cfg = read_session_config()
    resolved_op = str(cfg.get("operation", operation))
    resolved_pipeline = str(cfg.get("pipeline", pipeline))
    resolved_phase = phase or (
        str(cfg["phase"]) if isinstance(cfg.get("phase"), str) else phase
    )
    return resolved_op, resolved_pipeline, resolved_phase


def _coerce_data(data: object) -> str | None:
    """Normalize data to a JSON string regardless of what the LLM sent.

    Cursor agents may send data as a native JSON object (dict) even though the
    MCP schema declares str | None.  Accept both: if already a string, use it
    as-is; if a dict/list/scalar, serialise it; if None/empty, return None.
    """
    if data is None:
        return None
    if isinstance(data, str):
        return data if data.strip() else None
    return json.dumps(data)


def _unknown_op_error(operation: str) -> str:
    return json.dumps(
        {
            "status": "error",
            "error": (
                f"Unknown operation '{operation}'. "
                "Use: init, write, read, clear, snapshot, rollback "
                "(aliases: write_task, read_task, write_result, read_state)"
            ),
        },
        indent=2,
    )


def _phase_required_error(operation: str) -> str:
    return json.dumps(
        {"status": "error", "error": f"phase is required for {operation}"},
        indent=2,
    )


def _snapshot_paths_required_error() -> str:
    return json.dumps(
        {"status": "error", "error": "paths is required for snapshot"},
        indent=2,
    )


def _rollback_snapshot_id_required_error() -> str:
    return json.dumps(
        {"status": "error", "error": "snapshot_id is required for rollback"},
        indent=2,
    )


def _extract_snapshot_paths(data_str: str | None) -> list[str]:
    if not data_str:
        return []
    try:
        parsed = json.loads(data_str)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, dict):
        return []
    parsed_dict = cast(dict[str, object], parsed)
    paths = parsed_dict.get("paths")
    if not isinstance(paths, list):
        return []
    raw_paths = cast(list[object], paths)
    return [path for path in raw_paths if isinstance(path, str) and path]


def _extract_snapshot_id(data_str: str | None) -> str | None:
    if not data_str:
        return None
    try:
        parsed = json.loads(data_str)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    parsed_dict = cast(dict[str, object], parsed)
    snapshot_id = parsed_dict.get("snapshot_id")
    return snapshot_id if isinstance(snapshot_id, str) and snapshot_id else None


def _dispatch_read(project_root: Path, pipeline: str, phase: str | None) -> str:
    ph = phase or ""
    return (
        op_read_task(project_root, pipeline, ph)
        if phase
        else op_read_state(project_root, pipeline)
    )


def _dispatch_snapshot_or_rollback(
    project_root: Path, operation: str, data_str: str | None
) -> str:
    if operation == "snapshot":
        snapshot_paths = _extract_snapshot_paths(data_str)
        if not snapshot_paths:
            return _snapshot_paths_required_error()
        return op_snapshot(project_root, snapshot_paths)
    snapshot_id = _extract_snapshot_id(data_str)
    if snapshot_id is None:
        return _rollback_snapshot_id_required_error()
    return op_rollback(project_root, snapshot_id)


def _dispatch_sync(
    project_root: Path,
    operation: str,
    pipeline: str,
    phase: str | None,
    data_str: str | None,
) -> str:
    """Route operation to the correct handler. Call after resolving project root.

    Simplified API (preferred):
        init, write (needs phase), read (phase optional), clear
    Legacy operations (still supported):
        write_task, read_task, write_result, read_state
    """
    if operation in _OPS_NEED_PHASE and not phase:
        return _phase_required_error(operation)
    if operation == "init":
        return op_init(project_root, pipeline, data_str)
    if operation == "write_task":
        return op_write_task(project_root, pipeline, phase or "", data_str)
    if operation in ("write_result", "write"):
        return op_write_result(project_root, pipeline, phase or "", data_str)
    if operation == "read_task":
        return op_read_task(project_root, pipeline, phase or "")
    if operation == "read_state":
        return op_read_state(project_root, pipeline)
    if operation == "read":
        return _dispatch_read(project_root, pipeline, phase)
    if operation == "clear":
        return op_clear(project_root, pipeline)
    if operation in ("snapshot", "rollback"):
        return _dispatch_snapshot_or_rollback(project_root, operation, data_str)
    return _unknown_op_error(operation)


async def _dispatch(
    operation: str,
    pipeline: str,
    phase: str | None,
    data: object,
    ctx: MCPContext | None,
) -> str:
    data_str = _coerce_data(data)

    # Extract routing overrides embedded in the data payload (Cursor protocol).
    # Agents write {"operation":"write","phase":"select","pipeline":"implement",...payload...}
    # to current-task.json so routing + payload travel in one write instead of two.
    routing, data_str = extract_routing_keys(data_str)
    if routing.get("op"):
        operation = routing["op"]
    if routing.get("phase"):
        phase = routing["phase"]
    if routing.get("pipeline"):
        pipeline = routing["pipeline"]

    # When Cursor strips all args and no routing keys were in data, recover
    # operation/pipeline/phase from the session config file.
    operation, pipeline, phase = _resolve_zero_arg_defaults(operation, pipeline, phase)

    # Validate tokens before any filesystem path construction.
    pipeline_error = validate_pipeline(pipeline)
    if pipeline_error is not None:
        return pipeline_error
    if phase is not None:
        phase_error = validate_phase(phase)
        if phase_error is not None:
            return phase_error

    root = await get_or_resolve_project_root(ctx)
    project_root = Path(root)
    # Offload all blocking filesystem operations in _dispatch_sync.
    out = await asyncio.to_thread(
        _dispatch_sync, project_root, operation, pipeline, phase, data_str
    )
    emit_pipeline_handoff_log(operation, pipeline, phase)
    return out


# ---------------------------------------------------------------------------
# MCP tool
# ---------------------------------------------------------------------------


@mcp.tool(annotations=safe_write_annotations("Pipeline Handoff (Inter-Agent State)"))
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def pipeline_handoff(
    operation: str = "read_state",
    pipeline: str = "default",
    phase: str | None = None,
    data: object = None,
    paths: list[str] | None = None,
    snapshot_id: str | None = None,
    ctx: MCPContext | None = None,
) -> str:
    """Structured inter-agent communication for pipeline workflows.

    USE WHEN: Orchestrators need to exchange structured data between pipeline
    phases. Each phase writes its output; the next phase reads it. All data
    persists in .cortex/.session/{id}/{pipeline}/.

    WORKFLOW (simplified):
    1. pipeline_handoff(operation="init", pipeline="commit")
    2. pipeline_handoff(operation="write", pipeline="commit", phase="preflight",
         data='{"status":"complete","snapshot_ref":"abc123"}')
    3. pipeline_handoff(operation="read", pipeline="commit", phase="preflight")
         → reads phase data
    4. pipeline_handoff(operation="read", pipeline="commit")
         → reads full pipeline state (all phases)
    5. pipeline_handoff(operation="clear", pipeline="commit")

    EXAMPLES:
    - pipeline_handoff(operation="init", pipeline="commit")
    - pipeline_handoff(operation="write", pipeline="commit", phase="checks",
        data='{"status":"passed","coverage":0.94}')
    - pipeline_handoff(operation="read", pipeline="commit", phase="checks")
    - pipeline_handoff(operation="read", pipeline="commit")
    - pipeline_handoff(operation="clear", pipeline="commit")

    Legacy aliases (write_task, read_task, write_result, read_state) still work.

    RETURNS: JSON with {status, ...} for write ops; JSON file content for reads.

    Args:
        operation: init | write | read | clear | snapshot | rollback
            (legacy: write_task, read_task,
            write_result, read_state)
        pipeline: Pipeline name (e.g. "commit", "implement"). Default: "default".
        phase: Phase name (e.g. "preflight", "checks"). Required for write.
            For read: if given, reads that phase; if omitted, reads full state.
        data: Payload for write and init. Accepts JSON string or native object.
            When the JSON includes free-text fields such as `context` or
            `summary`, write compact technical prose (see cortex://rules,
            Agent-Internal Communication): no filler or hedging; keep file
            paths and error messages verbatim.
        paths: Paths to snapshot for operation="snapshot". Can be passed via
            this argument or via data={"paths":[...]} for arg-stripping clients.
        snapshot_id: Snapshot id for operation="rollback". Can be passed via
            this argument or via data={"snapshot_id":"..."}.
        ctx: MCP context (auto-provided).
    """
    await log_client(
        ctx,
        "debug",
        f"pipeline_handoff({operation}/{pipeline}/{phase})",
        logger_name=__name__,
    )
    payload = data
    if operation == "snapshot" and payload is None and paths is not None:
        payload = {"paths": paths}
    if operation == "rollback" and payload is None and snapshot_id is not None:
        payload = {"snapshot_id": snapshot_id}
    return await _dispatch(
        operation, pipeline, phase, payload, ctx
    )  # data coerced inside _dispatch
