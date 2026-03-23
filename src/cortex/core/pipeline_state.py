"""Lightweight pipeline state helpers with no circular-import risk.

Kept in cortex.core (not cortex.tools) so managers can import it safely.
"""

from __future__ import annotations

import os
from pathlib import Path

from cortex.core.path_resolver import CortexResourceType, get_cortex_path

_SESSION_ENV_KEY = "CORTEX_SESSION_ID"


def _get_session_id() -> str:
    return os.environ.get(_SESSION_ENV_KEY, "")


def is_commit_pipeline_active(project_root: Path) -> bool:
    """Return True when a commit pipeline session is initialized but not yet cleared.

    Uses only Path.exists() so it is safe to call from synchronous contexts
    and from managers that must not import cortex.tools.
    """
    session_id = _get_session_id()
    if not session_id:
        return False
    session_base = get_cortex_path(project_root, CortexResourceType.SESSION)
    return (session_base / session_id / "commit" / "pipeline.json").exists()
