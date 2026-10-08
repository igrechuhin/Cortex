"""Lightweight pipeline state helpers with no circular-import risk.

Kept in cortex.core (not cortex.tools) so managers can import it safely.
"""

from __future__ import annotations

from pathlib import Path

from cortex.core.path_resolver import CortexResourceType, get_cortex_path


def _pipeline_session_id(project_root: Path) -> str:
    """Durable pipeline session id without minting one (see resolver docs)."""
    # Deferred: importing cortex.tools at module load from cortex.core would
    # create an import cycle; at call time both packages are fully loaded.
    from cortex.tools.session.pipeline_handoff_session import get_session_id

    return get_session_id(project_root, mint=False)


def is_commit_pipeline_active(project_root: Path) -> bool:
    """Return True when a commit pipeline session is initialized but not yet cleared.

    Uses only Path.exists() so it is safe to call from synchronous contexts
    and from managers that must not import cortex.tools.
    """
    session_id = _pipeline_session_id(project_root)
    if not session_id:
        return False
    session_base = get_cortex_path(project_root, CortexResourceType.SESSION)
    return (session_base / session_id / "commit" / "pipeline.json").exists()
