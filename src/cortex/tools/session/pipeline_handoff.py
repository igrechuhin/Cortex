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

from cortex.core.constants import MCP_TOOL_TIMEOUT_FAST
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_annotations import safe_write_annotations
from cortex.core.mcp_stability import ensure_usage_context, mcp_tool_wrapper
from cortex.core.usage_context import get_or_resolve_project_root
from cortex.server import mcp

from .pipeline_handoff_io import (
    op_clear,
    op_init,
    op_read_state,
    op_read_task,
    op_write_result,
    op_write_task,
)
from .pipeline_handoff_validation import validate_phase, validate_pipeline

# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_OPS_NEED_PHASE = frozenset({"write_task", "read_task", "write_result", "write"})


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
                "Use: init, write, read, clear "
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
    ph = phase or ""
    if operation == "init":
        return op_init(project_root, pipeline, data_str)
    if operation == "write_task":
        return op_write_task(project_root, pipeline, ph, data_str)
    if operation in ("write_result", "write"):
        return op_write_result(project_root, pipeline, ph, data_str)
    if operation == "read_task":
        return op_read_task(project_root, pipeline, ph)
    if operation == "read_state":
        return op_read_state(project_root, pipeline)
    if operation == "read":
        return (
            op_read_task(project_root, pipeline, ph)
            if phase
            else op_read_state(project_root, pipeline)
        )
    if operation == "clear":
        return op_clear(project_root, pipeline)
    return _unknown_op_error(operation)


async def _dispatch(
    operation: str,
    pipeline: str,
    phase: str | None,
    data: object,
    ctx: MCPContext | None,
) -> str:
    data_str = _coerce_data(data)

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
    return await asyncio.to_thread(
        _dispatch_sync, project_root, operation, pipeline, phase, data_str
    )


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
        operation: init | write | read | clear (legacy: write_task, read_task,
            write_result, read_state)
        pipeline: Pipeline name (e.g. "commit", "implement"). Default: "default".
        phase: Phase name (e.g. "preflight", "checks"). Required for write.
            For read: if given, reads that phase; if omitted, reads full state.
        data: Payload for write and init. Accepts JSON string or native object.
        ctx: MCP context (auto-provided).
    """
    await log_client(
        ctx,
        "debug",
        f"pipeline_handoff({operation}/{pipeline}/{phase})",
        logger_name=__name__,
    )
    return await _dispatch(
        operation, pipeline, phase, data, ctx
    )  # data coerced inside _dispatch
