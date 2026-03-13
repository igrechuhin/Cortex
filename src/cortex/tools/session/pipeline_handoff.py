"""Pipeline handoff tool — structured inter-agent communication via session files.

Each pipeline run (commit, implement, review, …) creates a session-scoped
subfolder under .cortex/.session/{session_id}/ and exchanges structured
JSON between the orchestrator and its subagents through that folder.

## How it works

Orchestrator (before invoking each subagent):
    pipeline_handoff(operation="write_task", pipeline="commit", phase="checks",
                     data='{"coverage_threshold": 0.9, "snapshot_ref": "abc123"}')

Subagent (first thing it does):
    pipeline_handoff(operation="read_task", pipeline="commit", phase="checks")
    → {"coverage_threshold": 0.9, "snapshot_ref": "abc123", ...}

Subagent (when done):
    pipeline_handoff(operation="write_result", pipeline="commit", phase="checks",
                     data='{"status": "passed", "coverage": 0.94, "fix_iterations": 1}')

Orchestrator (to check all completed phase results / debug):
    pipeline_handoff(operation="read_state", pipeline="commit")
    → {"session_id": "...", "phases": {"preflight": {...}, "checks": {...}}, ...}

## Files on disk

.cortex/.session/{session_id}/{pipeline}/
    pipeline.json             — cumulative state updated after each write_result
    {phase}-task.json         — task data written by orchestrator for each phase
    {phase}-result.json       — result data written by each subagent

## Benefits

- No argument size limit: subagent receives a read_task call, gets all data
- Fully persistent: inspect any pipeline run after the fact for debugging
- Resumable: orchestrator reads read_state to know what already ran
- Environment-portable: works identically in Cursor and Claude Code
- Decoupled: orchestrator need not hold inter-phase data in its context window
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import cast

from cortex.core.constants import MCP_TOOL_TIMEOUT_FAST
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_annotations import safe_write_annotations
from cortex.core.mcp_stability import ensure_usage_context, mcp_tool_wrapper
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.usage_context import get_or_resolve_project_root
from cortex.server import mcp

# ---------------------------------------------------------------------------
# Session ID helpers (mirrors session_logger._get_session_id)
# ---------------------------------------------------------------------------

_SESSION_ENV_KEY = "CORTEX_SESSION_ID"


def _get_session_id() -> str:
    session_id = os.environ.get(_SESSION_ENV_KEY)
    if not session_id:
        session_id = uuid.uuid4().hex[:12]
        os.environ[_SESSION_ENV_KEY] = session_id
    return session_id


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def _pipeline_dir(project_root: Path, pipeline: str) -> Path:
    """Return .cortex/.session/{session_id}/{pipeline}/."""
    session_id = _get_session_id()
    base = get_cortex_path(project_root, CortexResourceType.SESSION)
    return base / session_id / pipeline


def _task_path(pipeline_dir: Path, phase: str) -> Path:
    return pipeline_dir / f"{phase}-task.json"


def _result_path(pipeline_dir: Path, phase: str) -> Path:
    return pipeline_dir / f"{phase}-result.json"


def _state_path(pipeline_dir: Path) -> Path:
    return pipeline_dir / "pipeline.json"


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------


def _op_init(project_root: Path, pipeline: str, data: str | None) -> str:
    """Create the pipeline directory and write initial manifest."""
    pdir = _pipeline_dir(project_root, pipeline)
    pdir.mkdir(parents=True, exist_ok=True)
    state_file = _state_path(pdir)
    extra: dict[str, object] = {}
    if data:
        try:
            parsed: object = json.loads(data)
            extra = (
                cast(dict[str, object], parsed)
                if isinstance(parsed, dict)
                else {"raw": data}
            )
        except json.JSONDecodeError:
            extra = {"raw": data}
    state: dict[str, object] = {
        "session_id": _get_session_id(),
        "pipeline": pipeline,
        "started_at": _now_iso(),
        "phases": {},
        **extra,
    }
    _ = state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return json.dumps(
        {"status": "ok", "pipeline_dir": str(pdir), "session_id": _get_session_id()},
        indent=2,
    )


def _op_write_task(
    project_root: Path, pipeline: str, phase: str, data: str | None
) -> str:
    """Write task data for a subagent. Called by orchestrator before invoking a phase."""
    pdir = _pipeline_dir(project_root, pipeline)
    pdir.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {"phase": phase, "written_at": _now_iso()}
    if data:
        try:
            parsed: object = json.loads(data)
            if isinstance(parsed, dict):
                payload.update(cast(dict[str, object], parsed))
            else:
                payload["data"] = parsed
        except json.JSONDecodeError:
            payload["data"] = data
    task_file = _task_path(pdir, phase)
    _ = task_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return json.dumps(
        {"status": "ok", "task_file": str(task_file), "phase": phase}, indent=2
    )


def _op_read_task(project_root: Path, pipeline: str, phase: str) -> str:
    """Read the task file for a phase. First thing a subagent calls.

    When no explicit task file exists (orchestrator skipped write_task), falls back
    to returning the cumulative pipeline state so the subagent still has context
    from prior phases.  The response includes ``status="not_found"`` so the subagent
    knows it is working from state rather than an explicit task.
    """
    pdir = _pipeline_dir(project_root, pipeline)
    task_file = _task_path(pdir, phase)
    if task_file.exists():
        try:
            return task_file.read_text(encoding="utf-8")
        except OSError as e:
            return json.dumps({"status": "error", "error": str(e)}, indent=2)
    # No explicit task — return pipeline state as context fallback
    state_file = _state_path(pdir)
    prior_state: dict[str, object] = {}
    if state_file.exists():
        try:
            prior_state = json.loads(state_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return json.dumps(
        {
            "status": "not_found",
            "phase": phase,
            "pipeline": pipeline,
            "message": (
                f"No explicit task written for phase '{phase}'. "
                "Using pipeline state as context — orchestrator skipped write_task."
            ),
            "pipeline_state": prior_state,
        },
        indent=2,
    )


def _load_or_create_state(state_file: Path, pipeline: str) -> dict[str, object]:
    """Load pipeline state from file or return fresh state dict."""
    if state_file.exists():
        try:
            loaded = json.loads(state_file.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                loaded_typed: dict[str, object] = cast(dict[str, object], loaded)
                return {
                    str(k): v for k, v in loaded_typed.items()
                }  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
        except (OSError, json.JSONDecodeError):
            pass
    return {
        "session_id": _get_session_id(),
        "pipeline": pipeline,
        "started_at": _now_iso(),
        "phases": {},
    }


def _parse_result_data(data: str | None) -> dict[str, object]:
    """Parse optional JSON data into a dict for payload update."""
    out: dict[str, object] = {}
    if not data:
        return out
    try:
        parsed: object = json.loads(data)
        if isinstance(parsed, dict):
            return cast(dict[str, object], parsed)
        return {"data": parsed}
    except json.JSONDecodeError:
        return {"data": data}


def _op_write_result(
    project_root: Path, pipeline: str, phase: str, data: str | None
) -> str:
    """Write phase result. Called by subagent when done. Also updates pipeline.json."""
    pdir = _pipeline_dir(project_root, pipeline)
    pdir.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {"phase": phase, "completed_at": _now_iso()}
    payload.update(_parse_result_data(data))
    result_file = _result_path(pdir, phase)
    _ = result_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    state_file = _state_path(pdir)
    state = _load_or_create_state(state_file, pipeline)
    raw_phases = state.get("phases")
    phases = (
        {str(k): v for k, v in cast(dict[str, object], raw_phases).items()}
        if isinstance(raw_phases, dict)
        else {}
    )
    phases[phase] = payload
    state["phases"] = phases
    state["last_updated"] = _now_iso()
    _ = state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return json.dumps(
        {"status": "ok", "result_file": str(result_file), "phase": phase}, indent=2
    )


def _op_read_state(project_root: Path, pipeline: str) -> str:
    """Read the full cumulative pipeline state."""
    pdir = _pipeline_dir(project_root, pipeline)
    state_file = _state_path(pdir)
    if not state_file.exists():
        return json.dumps(
            {
                "status": "not_found",
                "pipeline": pipeline,
                "session_id": _get_session_id(),
                "message": (
                    f"No pipeline state found for '{pipeline}'. "
                    "Call init or write_result first."
                ),
            },
            indent=2,
        )
    try:
        return state_file.read_text(encoding="utf-8")
    except OSError as e:
        return json.dumps({"status": "error", "error": str(e)}, indent=2)


def _op_clear(project_root: Path, pipeline: str) -> str:
    """Remove the pipeline directory after a completed or abandoned run."""
    import shutil

    pdir = _pipeline_dir(project_root, pipeline)
    if not pdir.exists():
        return json.dumps(
            {
                "status": "ok",
                "message": "Pipeline directory did not exist",
                "pipeline": pipeline,
            },
            indent=2,
        )
    try:
        shutil.rmtree(pdir)
        return json.dumps(
            {"status": "ok", "cleared": str(pdir), "pipeline": pipeline}, indent=2
        )
    except OSError as e:
        return json.dumps({"status": "error", "error": str(e)}, indent=2)


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


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
            "error": f"Unknown operation '{operation}'. Use: init, write_task, read_task, write_result, read_state, clear",
        },
        indent=2,
    )


def _dispatch_sync(
    project_root: Path,
    operation: str,
    pipeline: str,
    phase: str | None,
    data_str: str | None,
) -> str:
    """Route operation to the correct handler. Call after resolving project root."""
    if operation in ("write_task", "read_task", "write_result") and not phase:
        return json.dumps(
            {"status": "error", "error": f"phase is required for {operation}"}, indent=2
        )
    ph = phase or ""
    if operation == "init":
        return _op_init(project_root, pipeline, data_str)
    if operation == "write_task":
        return _op_write_task(project_root, pipeline, ph, data_str)
    if operation == "read_task":
        return _op_read_task(project_root, pipeline, ph)
    if operation == "write_result":
        return _op_write_result(project_root, pipeline, ph, data_str)
    if operation == "read_state":
        return _op_read_state(project_root, pipeline)
    if operation == "clear":
        return _op_clear(project_root, pipeline)
    return _unknown_op_error(operation)


async def _dispatch(
    operation: str,
    pipeline: str,
    phase: str | None,
    data: object,
    ctx: MCPContext | None,
) -> str:
    data_str = _coerce_data(data)
    root = await get_or_resolve_project_root(ctx)
    project_root = Path(root)
    return _dispatch_sync(project_root, operation, pipeline, phase, data_str)


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

    USE WHEN: Orchestrators and subagents need to exchange structured data
    without relying on context-window relay. Each phase writes its output;
    the next phase reads it. All data persists in .cortex/.session/{id}/{pipeline}/.

    WORKFLOW:
    1. Orchestrator: pipeline_handoff(operation="init", pipeline="commit")
    2. Orchestrator: pipeline_handoff(operation="write_task", pipeline="commit",
         phase="preflight", data='{"snapshot_ref": null}')
    3. Subagent starts → pipeline_handoff(operation="read_task", pipeline="commit",
         phase="preflight") → reads its task
    4. Subagent finishes → pipeline_handoff(operation="write_result", pipeline="commit",
         phase="preflight", data='{"status":"complete","snapshot_ref":"abc123"}')
    5. Orchestrator: pipeline_handoff(operation="read_state", pipeline="commit")
         → sees all completed phases; uses result from step 4 for step 5's task
    6. After commit: pipeline_handoff(operation="clear", pipeline="commit")

    EXAMPLES:
    - pipeline_handoff(operation="init", pipeline="commit")
    - pipeline_handoff(operation="write_task", pipeline="commit", phase="checks",
        data='{"coverage_threshold":0.9,"snapshot_ref":"abc"}')
    - pipeline_handoff(operation="read_task", pipeline="commit", phase="checks")
    - pipeline_handoff(operation="write_result", pipeline="commit", phase="checks",
        data='{"status":"passed","coverage":0.94}')
    - pipeline_handoff(operation="read_state", pipeline="commit")
    - pipeline_handoff(operation="clear", pipeline="commit")

    FILES CREATED:
    .cortex/.session/{session_id}/{pipeline}/
      pipeline.json          — cumulative state (all phase results)
      {phase}-task.json      — per-phase task written by orchestrator
      {phase}-result.json    — per-phase result written by subagent

    RETURNS: JSON with {status, ...} for write ops; JSON file content for reads.

    Args:
        operation: init | write_task | read_task | write_result | read_state | clear
        pipeline: Pipeline name (e.g. "commit", "implement", "review"). Default: "default".
        phase: Phase/subagent name (e.g. "preflight", "checks", "docs"). Required for
            write_task, read_task, write_result.
        data: Payload for write_task, write_result, and init. Accepts either a JSON
            string ('{"key":"val"}') or a native JSON object ({"key":"val"}) — both
            are normalised internally. Optional; pass null/None to omit.
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
