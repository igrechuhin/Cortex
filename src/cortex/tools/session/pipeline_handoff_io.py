"""Filesystem read/write operations for pipeline_handoff session state."""

from __future__ import annotations

import json
import logging
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import cast

from cortex.core.path_resolver import CortexResourceType, get_cortex_path

logger = logging.getLogger(__name__)

PIPELINE_TTL_SECONDS = 4 * 3600  # 4 hours

# ---------------------------------------------------------------------------
# Session ID helpers (mirrors session_logger._get_session_id)
# ---------------------------------------------------------------------------

_SESSION_ENV_KEY = "CORTEX_SESSION_ID"


def get_session_id() -> str:
    session_id = os.environ.get(_SESSION_ENV_KEY)
    if not session_id:
        session_id = uuid.uuid4().hex[:12]
        os.environ[_SESSION_ENV_KEY] = session_id
    return session_id


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def pipeline_dir(project_root: Path, pipeline: str) -> Path:
    """Return .cortex/.session/{session_id}/{pipeline}/."""
    session_id = get_session_id()
    base = get_cortex_path(project_root, CortexResourceType.SESSION)
    return base / session_id / pipeline


def task_path(pipeline_dir: Path, phase: str) -> Path:
    return pipeline_dir / f"{phase}-task.json"


def result_path(pipeline_dir: Path, phase: str) -> Path:
    return pipeline_dir / f"{phase}-result.json"


def state_path(pipeline_dir: Path) -> Path:
    return pipeline_dir / "pipeline.json"


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------


def _is_pipeline_stale(state_file: Path) -> bool:
    """Return True if pipeline.json is older than PIPELINE_TTL_SECONDS."""
    if not state_file.exists():
        return False
    try:
        data: object = json.loads(state_file.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return True
        started_raw = cast(dict[str, object], data).get("started_at")
        if not isinstance(started_raw, str):
            return True
        started = datetime.fromisoformat(started_raw)
        age = (datetime.now() - started).total_seconds()
        return age > PIPELINE_TTL_SECONDS
    except (OSError, json.JSONDecodeError, ValueError):
        return True


def _parse_init_data(data: str) -> dict[str, object]:
    try:
        parsed: object = json.loads(data)
        if isinstance(parsed, dict):
            return cast(dict[str, object], parsed)
        return {"raw": data}
    except json.JSONDecodeError:
        return {"raw": data}


def op_init(project_root: Path, pipeline: str, data: str | None) -> str:
    """Create the pipeline directory and write initial manifest."""
    pdir = pipeline_dir(project_root, pipeline)
    state_file = state_path(pdir)
    if state_file.exists() and _is_pipeline_stale(state_file):
        ttl_hours = PIPELINE_TTL_SECONDS // 3600
        logger.warning(
            "pipeline_handoff: stale '%s' pipeline state detected (>%dh); clearing.",
            pipeline,
            ttl_hours,
        )
        shutil.rmtree(pdir, ignore_errors=True)
    pdir.mkdir(parents=True, exist_ok=True)
    extra = _parse_init_data(data) if data else {}
    state: dict[str, object] = {
        "session_id": get_session_id(),
        "pipeline": pipeline,
        "started_at": now_iso(),
        "phases": {},
        **extra,
    }
    _ = state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return json.dumps(
        {"status": "ok", "pipeline_dir": str(pdir), "session_id": get_session_id()},
        indent=2,
    )


def op_write_task(
    project_root: Path, pipeline: str, phase: str, data: str | None
) -> str:
    """Write task data for a subagent. Called by orchestrator before invoking a phase."""
    pdir = pipeline_dir(project_root, pipeline)
    pdir.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {"phase": phase, "written_at": now_iso()}
    if data:
        try:
            parsed: object = json.loads(data)
            if isinstance(parsed, dict):
                payload.update(cast(dict[str, object], parsed))
            else:
                payload["data"] = parsed
        except json.JSONDecodeError:
            payload["data"] = data
    tfile = task_path(pdir, phase)
    _ = tfile.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return json.dumps(
        {"status": "ok", "task_file": str(tfile), "phase": phase}, indent=2
    )


def _load_pipeline_state_fallback(state_file: Path) -> object:
    if not state_file.exists():
        return {}
    try:
        return json.loads(state_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def op_read_task(project_root: Path, pipeline: str, phase: str) -> str:
    """Read the task file for a phase. First thing a subagent calls.

    When no explicit task file exists (orchestrator skipped write_task), falls back
    to returning the cumulative pipeline state so the subagent still has context
    from prior phases.  The response includes ``status="not_found"`` so the subagent
    knows it is working from state rather than an explicit task.
    """
    pdir = pipeline_dir(project_root, pipeline)
    tfile = task_path(pdir, phase)
    if tfile.exists():
        try:
            return tfile.read_text(encoding="utf-8")
        except OSError as e:
            return json.dumps({"status": "error", "error": str(e)}, indent=2)
    sfile = state_path(pdir)
    prior_state = _load_pipeline_state_fallback(sfile)
    return json.dumps(
        {
            "status": "not_found",
            "phase": phase,
            "pipeline": pipeline,
            "message": (
                f"No explicit task written for phase '{phase}'. "
                "Using pipeline state as context — orchestrator skipped write."
            ),
            "pipeline_state": prior_state,
        },
        indent=2,
    )


def load_or_create_state(state_file: Path, pipeline: str) -> dict[str, object]:
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
        "session_id": get_session_id(),
        "pipeline": pipeline,
        "started_at": now_iso(),
        "phases": {},
    }


_ROUTING_KEYS: frozenset[str] = frozenset({"operation", "phase", "pipeline"})


def extract_routing_keys(
    data: str | None,
) -> tuple[dict[str, str], str | None]:
    """Extract operation/phase/pipeline routing overrides from a JSON data string.

    Returns (routing, cleaned_data):
    - routing: dict with string values for any of "op", "phase", "pipeline"
      found in the data ("operation" is normalised to "op" for the dispatcher).
    - cleaned_data: original data with routing keys removed, or the original
      string unchanged if no routing keys were present (or data was not JSON).

    Used by the dispatcher so agents can embed routing alongside payload in a
    single JSON write instead of a separate session-config write per call.
    """
    if not data:
        return {}, data
    try:
        parsed: object = json.loads(data)
    except json.JSONDecodeError:
        return {}, data
    if not isinstance(parsed, dict):
        return {}, data
    parsed_dict = cast(dict[str, object], parsed)
    routing: dict[str, str] = {}
    for key in _ROUTING_KEYS:
        val = parsed_dict.get(key)
        if isinstance(val, str) and val:
            # "operation" → "op" so the dispatcher's existing key checks still work.
            canonical = "op" if key == "operation" else key
            routing[canonical] = val
    if not routing:
        return {}, data
    cleaned = {k: v for k, v in parsed_dict.items() if k not in _ROUTING_KEYS}
    return routing, json.dumps(cleaned) if cleaned else None


def parse_result_data(data: str | None) -> dict[str, object]:
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


def op_write_result(
    project_root: Path, pipeline: str, phase: str, data: str | None
) -> str:
    """Write phase result. Called by subagent when done. Also updates pipeline.json."""
    pdir = pipeline_dir(project_root, pipeline)
    pdir.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {"phase": phase, "completed_at": now_iso()}
    payload.update(parse_result_data(data))
    rfile = result_path(pdir, phase)
    _ = rfile.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    sfile = state_path(pdir)
    state = load_or_create_state(sfile, pipeline)
    raw_phases = state.get("phases")
    phases = (
        {str(k): v for k, v in cast(dict[str, object], raw_phases).items()}
        if isinstance(raw_phases, dict)
        else {}
    )
    phases[phase] = payload
    state["phases"] = phases
    state["last_updated"] = now_iso()
    _ = sfile.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return json.dumps(
        {
            "status": "ok",
            "result_file": str(rfile),
            "phase": phase,
            "pipeline_state": state,
        },
        indent=2,
    )


def op_read_state(project_root: Path, pipeline: str) -> str:
    """Read the full cumulative pipeline state."""
    pdir = pipeline_dir(project_root, pipeline)
    sfile = state_path(pdir)
    if not sfile.exists():
        return json.dumps(
            {
                "status": "not_found",
                "pipeline": pipeline,
                "session_id": get_session_id(),
                "message": (
                    f"No pipeline state found for '{pipeline}'. "
                    "Call init or write_result first."
                ),
            },
            indent=2,
        )
    try:
        return sfile.read_text(encoding="utf-8")
    except OSError as e:
        return json.dumps({"status": "error", "error": str(e)}, indent=2)


def op_clear(project_root: Path, pipeline: str) -> str:
    """Remove the pipeline directory after a completed or abandoned run."""
    pdir = pipeline_dir(project_root, pipeline)
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
