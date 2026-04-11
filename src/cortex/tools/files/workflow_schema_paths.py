"""Filesystem paths for workflow schema YAML (project vs bundled)."""

from __future__ import annotations

from pathlib import Path

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.schema_loader import bundled_workflow_schema_dir


def project_schema_dir(project_root: Path) -> Path:
    return get_cortex_path(project_root, CortexResourceType.SCHEMAS)


def fork_schema_source_file(project_root: Path, base: str) -> Path | None:
    proj = project_schema_dir(project_root)
    project_file = proj / f"{base}.yaml"
    if project_file.is_file():
        return project_file
    bundled = bundled_workflow_schema_dir() / f"{base}.yaml"
    if bundled.is_file():
        return bundled
    return None
