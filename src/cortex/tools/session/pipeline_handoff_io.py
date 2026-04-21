"""Filesystem read/write operations for pipeline_handoff session state."""

from __future__ import annotations

import json
import logging
import os
import shutil
import uuid
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import cast

from pydantic import BaseModel, Field

from cortex.core.file_snapshot import FileStateCache
from cortex.core.models import OperationStatus
from cortex.core.path_resolver import CortexResourceType, get_cortex_path

logger = logging.getLogger(__name__)

PIPELINE_TTL_SECONDS = 4 * 3600  # 4 hours


class PhaseStatus(StrEnum):
    """Canonical lifecycle states for pipeline phases."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


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


def get_file_state_cache(session_id: str, project_root: Path) -> FileStateCache:
    """Create a session-scoped file state cache instance."""
    base = get_cortex_path(project_root, CortexResourceType.SESSION)
    return FileStateCache(base / session_id)


def task_path(pipeline_dir: Path, phase: str) -> Path:
    return pipeline_dir / f"{phase}-task.json"


def result_path(pipeline_dir: Path, phase: str) -> Path:
    return pipeline_dir / f"{phase}-result.json"


def state_path(pipeline_dir: Path) -> Path:
    return pipeline_dir / "pipeline.json"


def event_log_path(pipeline_dir: Path) -> Path:
    return pipeline_dir / "pipeline.log"


class EventLogEntry(BaseModel):
    """Single append-only event log record."""

    phase: str = Field(min_length=1)
    timestamp: str = Field(min_length=1)
    operation: str = Field(min_length=1)
    data_keys: list[str] = Field(default_factory=list)
    status: PhaseStatus | None = None


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
            return json.dumps(
                {"status": OperationStatus.ERROR.value, "error": str(e)}, indent=2
            )
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

# Keys that carry pipeline config/hints rather than phase result data.
# When present in a write_result payload these are lifted to a top-level
# "config" block so they do not pollute the phase result record.
_PHASE_CONFIG_KEYS: frozenset[str] = frozenset({"force_fresh", "test_timeout"})


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


def _phase_status_from_payload(payload: dict[str, object]) -> PhaseStatus:
    raw_status = payload.get("status")
    if isinstance(raw_status, str):
        lowered = raw_status.lower()
        if lowered == PhaseStatus.RUNNING.value:
            return PhaseStatus.RUNNING
        if lowered == PhaseStatus.FAILED.value:
            return PhaseStatus.FAILED
        if lowered in {"completed", "complete", "passed", "pass", "ok", "success"}:
            return PhaseStatus.COMPLETED
    return PhaseStatus.COMPLETED


def _atomic_write_json(target_file: Path, payload: dict[str, object]) -> None:
    temp_file = target_file.with_suffix(f"{target_file.suffix}.tmp")
    _ = temp_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _ = temp_file.replace(target_file)


def _append_event_log(
    pipeline_dir: Path,
    phase: str,
    operation: str,
    data_keys: list[str],
    status: PhaseStatus | None = None,
) -> None:
    entry = EventLogEntry(
        phase=phase,
        timestamp=now_iso(),
        operation=operation,
        data_keys=data_keys,
        status=status,
    )
    elog = event_log_path(pipeline_dir)
    with elog.open("a", encoding="utf-8") as stream:
        _ = stream.write(entry.model_dump_json())
        _ = stream.write("\n")


def _read_event_log_entries(pipeline_dir: Path) -> list[EventLogEntry]:
    elog = event_log_path(pipeline_dir)
    if not elog.exists():
        return []
    entries: list[EventLogEntry] = []
    for raw_line in elog.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            parsed: object = json.loads(line)
            entry = EventLogEntry.model_validate(parsed)
        except (json.JSONDecodeError, ValueError):
            continue
        entries.append(entry)
    return entries


def detect_incomplete_state(pipeline_dir: Path) -> list[str]:
    entries = _read_event_log_entries(pipeline_dir)
    write_phases = {
        entry.phase
        for entry in entries
        if entry.operation == "write" and entry.phase.strip()
    }
    incomplete_phases: list[str] = []
    for phase in sorted(write_phases):
        if not result_path(pipeline_dir, phase).exists():
            incomplete_phases.append(phase)
    return incomplete_phases


def _split_config_from_result(
    incoming: dict[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    """Separate phase config hints from phase result fields.

    Config keys (force_fresh, test_timeout, …) belong in the top-level
    ``config`` block of pipeline state, not mixed into the phase result
    record.  Returns (result_fields, config_fields).
    """
    result_fields = {k: v for k, v in incoming.items() if k not in _PHASE_CONFIG_KEYS}
    config_fields = {k: v for k, v in incoming.items() if k in _PHASE_CONFIG_KEYS}
    return result_fields, config_fields


def _state_phases(state: dict[str, object]) -> dict[str, object]:
    raw_phases = state.get("phases")
    if not isinstance(raw_phases, dict):
        return {}
    return {str(k): v for k, v in cast(dict[str, object], raw_phases).items()}


def _update_pipeline_config(
    state: dict[str, object], config_fields: dict[str, object]
) -> None:
    if not config_fields:
        return
    raw_config = state.get("config")
    config: dict[str, object] = (
        {str(k): v for k, v in cast(dict[str, object], raw_config).items()}
        if isinstance(raw_config, dict)
        else {}
    )
    config.update(config_fields)
    state["config"] = config


def _write_result_payload_file(
    pipeline_dir: Path,
    phase: str,
    result_fields: dict[str, object],
) -> tuple[dict[str, object], Path]:
    payload: dict[str, object] = {"phase": phase, "completed_at": now_iso()}
    payload.update(result_fields)
    _ = payload.setdefault("status", PhaseStatus.COMPLETED.value)
    payload["phase_status"] = _phase_status_from_payload(payload).value
    rfile = result_path(pipeline_dir, phase)
    _atomic_write_json(rfile, payload)
    return payload, rfile


def _running_payload(phase: str) -> dict[str, object]:
    return {
        "phase": phase,
        "status": PhaseStatus.RUNNING.value,
        "phase_status": PhaseStatus.RUNNING.value,
        "started_at": now_iso(),
    }


def _update_pipeline_state_file(
    pipeline_dir: Path,
    pipeline: str,
    phase: str,
    payload: dict[str, object],
    config_fields: dict[str, object],
) -> dict[str, object]:
    sfile = state_path(pipeline_dir)
    state = load_or_create_state(sfile, pipeline)
    phases = _state_phases(state)
    phases[phase] = payload
    state["phases"] = phases
    state["last_updated"] = now_iso()
    _update_pipeline_config(state, config_fields)
    _ = sfile.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return state


def op_write_result(
    project_root: Path, pipeline: str, phase: str, data: str | None
) -> str:
    """Write phase result. Called by subagent when done. Also updates pipeline.json."""
    pdir = pipeline_dir(project_root, pipeline)
    pdir.mkdir(parents=True, exist_ok=True)
    incoming = parse_result_data(data)
    event_status = _phase_status_from_payload(incoming)
    try:
        _append_event_log(
            pdir,
            phase=phase,
            operation="write",
            data_keys=sorted(incoming.keys()),
            status=event_status,
        )
    except OSError as exc:
        return json.dumps(
            {"status": OperationStatus.ERROR.value, "error": str(exc)}, indent=2
        )
    result_fields, config_fields = _split_config_from_result(incoming)
    payload, rfile = _write_result_payload_file(pdir, phase, result_fields)
    state = _update_pipeline_state_file(pdir, pipeline, phase, payload, config_fields)
    return json.dumps(
        {
            "status": "ok",
            "result_file": str(rfile),
            "phase": phase,
            "pipeline_state": state,
        },
        indent=2,
    )


def op_mark_running(project_root: Path, pipeline: str, phase: str) -> str:
    """Mark phase as running and persist atomically for crash-safe resume."""
    pdir = pipeline_dir(project_root, pipeline)
    pdir.mkdir(parents=True, exist_ok=True)
    payload = _running_payload(phase)
    rfile = result_path(pdir, phase)
    try:
        _atomic_write_json(rfile, payload)
        _append_event_log(
            pdir,
            phase=phase,
            operation="mark_running",
            data_keys=sorted(payload.keys()),
            status=PhaseStatus.RUNNING,
        )
    except OSError as exc:
        return json.dumps(
            {"status": OperationStatus.ERROR.value, "error": str(exc)}, indent=2
        )
    state = _update_pipeline_state_file(pdir, pipeline, phase, payload, {})
    return json.dumps(
        {
            "status": "ok",
            "phase": phase,
            "result_file": str(rfile),
            "pipeline_state": state,
        },
        indent=2,
    )


def _phase_status_from_result_file(rfile: Path) -> PhaseStatus:
    try:
        parsed: object = json.loads(rfile.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return PhaseStatus.FAILED
    if not isinstance(parsed, dict):
        return PhaseStatus.FAILED
    payload = cast(dict[str, object], parsed)
    phase_status = payload.get("phase_status")
    if isinstance(phase_status, str) and phase_status:
        lowered = phase_status.lower()
        if lowered == PhaseStatus.RUNNING.value:
            return PhaseStatus.RUNNING
        if lowered == PhaseStatus.FAILED.value:
            return PhaseStatus.FAILED
        if lowered in {"completed", "complete", "passed", "pass", "ok", "success"}:
            return PhaseStatus.COMPLETED
    return _phase_status_from_payload(payload)


def _collect_phase_names_for_status(pdir: Path) -> set[str]:
    phase_names: set[str] = set()
    for task_file in pdir.glob("*-task.json"):
        phase_names.add(task_file.name.removesuffix("-task.json"))
    for result_file in pdir.glob("*-result.json"):
        phase_names.add(result_file.name.removesuffix("-result.json"))
    sfile = state_path(pdir)
    if not sfile.exists():
        return phase_names
    state_obj = _load_pipeline_state_fallback(sfile)
    if not isinstance(state_obj, dict):
        return phase_names
    phases_obj = cast(dict[str, object], state_obj).get("phases")
    if isinstance(phases_obj, dict):
        phase_names.update(
            str(name) for name in cast(dict[str, object], phases_obj).keys()
        )
    return phase_names


def _build_phase_statuses(pdir: Path, phase_names: set[str]) -> dict[str, str]:
    statuses: dict[str, str] = {}
    for phase in sorted(phase_names):
        rfile = result_path(pdir, phase)
        statuses[phase] = (
            _phase_status_from_result_file(rfile).value
            if rfile.exists()
            else PhaseStatus.PENDING.value
        )
    return statuses


def op_status(project_root: Path, pipeline: str) -> str:
    """Return current phase-status map for resume-aware agents."""
    pdir = pipeline_dir(project_root, pipeline)
    if not pdir.exists():
        return json.dumps(
            {"status": "ok", "pipeline": pipeline, "phases": {}}, indent=2
        )
    phase_names = _collect_phase_names_for_status(pdir)
    statuses = _build_phase_statuses(pdir, phase_names)

    return json.dumps(
        {"status": "ok", "pipeline": pipeline, "phases": statuses},
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
        return json.dumps(
            {"status": OperationStatus.ERROR.value, "error": str(e)}, indent=2
        )


def op_read_log(project_root: Path, pipeline: str) -> str:
    """Read append-only event log entries for a pipeline."""
    pdir = pipeline_dir(project_root, pipeline)
    entries = _read_event_log_entries(pdir)
    return json.dumps(
        {
            "status": "ok",
            "pipeline": pipeline,
            "entries": [entry.model_dump(mode="python") for entry in entries],
        },
        indent=2,
    )


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
        return json.dumps(
            {"status": OperationStatus.ERROR.value, "error": str(e)}, indent=2
        )


def op_snapshot(project_root: Path, paths: list[str]) -> str:
    """Snapshot provided file paths for current session."""
    session_id = get_session_id()
    cache = get_file_state_cache(session_id, project_root)
    snapshot_id = cache.snapshot([Path(path) for path in paths])
    return json.dumps(
        {"status": "ok", "snapshot_id": snapshot_id, "session_id": session_id},
        indent=2,
    )


def op_rollback(project_root: Path, snapshot_id: str) -> str:
    """Restore files from a session snapshot."""
    cache = get_file_state_cache(get_session_id(), project_root)
    restored = cache.restore(snapshot_id)
    return json.dumps(
        {
            "status": "ok",
            "snapshot_id": snapshot_id,
            "restored": [str(p) for p in restored],
        },
        indent=2,
    )
