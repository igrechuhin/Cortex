"""Session id resolution for pipeline_handoff — durable across process restarts.

The MCP server process backing an orchestrator's connection is not
guaranteed to stay alive for the whole pipeline run — a long-running
subagent call (e.g. implement-code) can outlast it. Caching the session id
only in ``os.environ`` meant a fresh process had no ``CORTEX_SESSION_ID``,
minted a brand-new random id, and silently resolved to an empty pipeline
directory, orphaning every phase already written under the old session id.

``get_session_id`` now falls back to an on-disk marker
(``.cortex/.session/.active-session.json``) so a fresh process recovers the
same identity instead of diverging. An explicit ``CORTEX_SESSION_ID`` env var
(test isolation, Cursor bridge) still takes precedence.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from pathlib import Path
from typing import cast

from cortex.core.path_resolver import CortexResourceType, get_cortex_path

from .pipeline_handoff_clock import age_seconds
from .pipeline_handoff_clock import now_iso as _now_iso

logger = logging.getLogger(__name__)

_SESSION_ENV_KEY = "CORTEX_SESSION_ID"
_SESSION_MARKER_FILENAME = ".active-session.json"

# Mirrors pipeline_handoff_io.PIPELINE_TTL_SECONDS: a marker older than this
# is treated as abandoned rather than resumed.
SESSION_MARKER_TTL_SECONDS = 4 * 3600  # 4 hours


def _session_marker_path(project_root: Path) -> Path:
    base = get_cortex_path(project_root, CortexResourceType.SESSION)
    return base / _SESSION_MARKER_FILENAME


def _read_persisted_session_id(project_root: Path) -> str | None:
    """Recover the active session id from disk when the process env is empty."""
    marker = _session_marker_path(project_root)
    if not marker.exists():
        return None
    try:
        raw: object = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    data = cast(dict[str, object], raw)
    session_id = data.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        return None
    updated_raw = data.get("updated_at")
    if not isinstance(updated_raw, str):
        return None
    try:
        if age_seconds(updated_raw) > SESSION_MARKER_TTL_SECONDS:
            return None
    except ValueError:
        return None
    return session_id


def _persist_session_id(project_root: Path, session_id: str) -> None:
    marker = _session_marker_path(project_root)
    payload = {"session_id": session_id, "updated_at": _now_iso()}
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        temp_file = marker.with_suffix(f"{marker.suffix}.tmp")
        _ = temp_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        _ = temp_file.replace(marker)
    except OSError:
        logger.warning(
            "pipeline_handoff: failed to persist session id marker at %s", marker
        )


def get_session_id(project_root: Path) -> str:
    """Get or create the active pipeline session id for this project.

    Resolution order: explicit ``CORTEX_SESSION_ID`` env var (set by this
    process earlier, or by a test/override hook) > on-disk marker written by
    the most recent call in this project (survives MCP server process
    restarts that can happen mid-pipeline) > freshly minted id, which is
    immediately persisted so subsequent calls — including from a different
    process — recover the same identity instead of silently diverging.
    """
    session_id = os.environ.get(_SESSION_ENV_KEY)
    if not session_id:
        session_id = _read_persisted_session_id(project_root)
    if not session_id:
        session_id = uuid.uuid4().hex[:12]
        _persist_session_id(project_root, session_id)
    os.environ[_SESSION_ENV_KEY] = session_id
    return session_id
