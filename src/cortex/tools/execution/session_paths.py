"""Shared paths for detached pre-commit session artifacts."""

from pathlib import Path

from cortex.core.path_resolver import CortexResourceType, get_cortex_path


def session_dir(project_root: Path) -> Path:
    """Return session directory for pre-commit result files, creating it if needed."""
    d = get_cortex_path(project_root, CortexResourceType.SESSION)
    d.mkdir(parents=True, exist_ok=True)
    return d
