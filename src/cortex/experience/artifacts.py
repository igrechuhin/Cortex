"""Artifact persistence for large experience payloads (gate logs, diffs).

Payloads are written under ``.cortex/experience/artifacts/`` and referenced
from ``nodes.artifact_ref`` by project-root-relative posix path, keeping the
SQLite rows small.
"""

from __future__ import annotations

import uuid
from pathlib import Path

ARTIFACTS_DIR_RELATIVE_POSIX = ".cortex/experience/artifacts"


class ArtifactRefError(ValueError):
    """Raised for malformed or out-of-tree artifact references."""


def store_artifact(project_root: Path, name: str, content: str) -> str:
    """Persist ``content`` and return the project-root-relative artifact ref.

    A short random suffix keeps concurrent writers from colliding on the
    same logical name.
    """
    safe_name = _sanitize_name(name)
    artifacts_dir = project_root / ARTIFACTS_DIR_RELATIVE_POSIX
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    file_name = f"{safe_name}-{uuid.uuid4().hex[:8]}.json"
    _ = (artifacts_dir / file_name).write_text(content, encoding="utf-8")
    return f"{ARTIFACTS_DIR_RELATIVE_POSIX}/{file_name}"


def load_artifact(project_root: Path, artifact_ref: str) -> str:
    """Read an artifact by reference; raises ``ArtifactRefError`` when malformed."""
    validate_artifact_ref(artifact_ref)
    return (project_root / artifact_ref).read_text(encoding="utf-8")


def validate_artifact_ref(artifact_ref: str) -> None:
    """Reject refs outside the artifacts directory or containing traversal."""
    prefix = f"{ARTIFACTS_DIR_RELATIVE_POSIX}/"
    if not artifact_ref.startswith(prefix):
        raise ArtifactRefError(
            f"artifact_ref must start with {prefix!r}: {artifact_ref!r}"
        )
    # AI: refs are stored in a shared DB — treat them as untrusted input.
    if ".." in Path(artifact_ref).parts:
        raise ArtifactRefError(f"artifact_ref must not contain '..': {artifact_ref!r}")


def _sanitize_name(name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in name.strip())
    return cleaned.strip("-") or "artifact"
