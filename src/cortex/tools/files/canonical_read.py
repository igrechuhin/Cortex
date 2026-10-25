"""Canonical-root read flow for ``manage_file(operation="read")``.

Reads memory-bank conclusions and closed artifact reports (reviews,
analyses, queries) from the git-verified canonical main worktree so result
references inside approved summaries stay readable from a worktree. Each
file is captured once (exact bytes) for both parsing and provenance, then
re-verified together with the canonical HEAD revision; any mutation during
assembly fails closed. Local freshness applies the same real-path symlink
checks as the canonical read and reports unsafe local counterparts as
``unsafe`` instead of reading them. No managers are initialized for the
canonical root and nothing is written anywhere.
"""

from __future__ import annotations

import json
from pathlib import Path

from cortex.core.canonical_project import (
    ARTIFACT_DIR_NAMES,
    CanonicalLocalState,
    CanonicalProjectError,
    CanonicalProjectIdentity,
    CanonicalReadProvenance,
    CapturedSource,
    canonical_artifact_file,
    canonical_memory_bank_file,
    capture_file,
    local_context_unsafe,
    resolve_canonical_identity,
    revalidate_revision,
    sha256_bytes,
)
from cortex.core.context_logging import MCPContext
from cortex.core.models import PlanReadSource
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.files.operation_helpers import FileOperation


def _error(file_name: str, message: str, error: str) -> str:
    return json.dumps(
        {
            "status": "error",
            "file_name": file_name,
            "message": message,
            "error": error,
        },
        indent=2,
    )


def _is_artifact_path(file_name: str) -> bool:
    return "/" in file_name or file_name.startswith("./")


def _normalized_parts(file_name: str) -> list[str]:
    normalized = file_name.strip()
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return list(Path(normalized).parts)


def _canonical_identity_or_error(
    local_root: Path, file_name: str
) -> tuple[CanonicalProjectIdentity | None, str | None]:
    try:
        return (resolve_canonical_identity(local_root), None)
    except (CanonicalProjectError, OSError) as exc:
        detail = (
            f"{exc.failure.value}: {exc.detail}"
            if isinstance(exc, CanonicalProjectError)
            else str(exc)
        )
        return (None, _error(file_name, "Canonical read unavailable", detail))


def _canonical_target_or_error(
    identity: CanonicalProjectIdentity, file_name: str
) -> tuple[Path | None, str | None]:
    try:
        target = (
            canonical_artifact_file(identity, file_name)
            if _is_artifact_path(file_name)
            else canonical_memory_bank_file(identity, file_name)
        )
    except CanonicalProjectError as exc:
        error = _error(
            file_name,
            "Invalid canonical file name",
            f"{exc.failure.value}: {exc.detail}",
        )
        return (None, error)
    if not target.is_file():
        error = _error(
            file_name,
            "File not found in canonical root",
            f"Canonical file does not exist: {target}",
        )
        return (None, error)
    return (target, None)


def _provenance_payload(
    identity: CanonicalProjectIdentity,
    capture: CapturedSource,
    local_state: CanonicalLocalState,
    local_digest: str | None,
) -> dict[str, object]:
    provenance = CanonicalReadProvenance(
        source=PlanReadSource.CANONICAL,
        root=identity.canonical_root,
        relation=identity.relation,
        git_revision=identity.git_revision,
        content_sha256=capture.sha256,
        local_state=local_state,
        local_content_sha256=local_digest,
    )
    return provenance.model_dump(mode="json")


async def canonical_manage_file_read(
    local_root: Path, file_name: str, sections: list[str] | None
) -> str:
    """Read one memory-bank or artifact file from the canonical main root."""

    from cortex.tools.files.section_helpers import extract_content_sections

    local = local_root.resolve()
    identity, identity_error = _canonical_identity_or_error(local, file_name)
    if identity_error is not None or identity is None:
        return identity_error or _error(file_name, "Unavailable", "unknown")
    target, target_error = _canonical_target_or_error(identity, file_name)
    if target_error is not None or target is None:
        return target_error or _error(file_name, "Unavailable", "unknown")
    capture, capture_error = _capture_or_error(target, file_name)
    if capture_error is not None or capture is None:
        return capture_error or _error(file_name, "Unavailable", "unknown")
    content, section_warning = extract_content_sections(capture.text(), sections)
    local_state, local_digest = _local_freshness(local, file_name, capture.sha256)
    # AI: Final coherence gate — content, provenance and repository context
    # must all describe the same instant, so re-verify after assembly.
    if not capture.unchanged() or not revalidate_revision(identity):
        return _error(
            file_name,
            "Canonical file changed during read",
            "revision_changed_during_read: re-read required",
        )
    return _read_success_response(
        file_name,
        content,
        section_warning,
        _provenance_payload(identity, capture, local_state, local_digest),
    )


def _capture_or_error(
    target: Path, file_name: str
) -> tuple[CapturedSource | None, str | None]:
    try:
        return (capture_file(target), None)
    except OSError as exc:
        return (None, _error(file_name, "Failed to read canonical file", str(exc)))


def _read_success_response(
    file_name: str,
    content: str,
    section_warning: str | None,
    provenance: dict[str, object],
) -> str:
    response: dict[str, object] = {
        "status": "success",
        "file_name": file_name,
        "content": content,
        "provenance": provenance,
    }
    if section_warning:
        response["warning"] = section_warning
    return json.dumps(response, indent=2)


def _validate_canonical_read_request(
    parsed_op: FileOperation, include_metadata: bool
) -> str | None:
    """Canonical reads accept operation=read only, without local metadata."""

    from cortex.core.models import OperationStatus

    if parsed_op is not FileOperation.READ:
        return json.dumps(
            {
                "status": OperationStatus.ERROR.value,
                "error": (
                    "source='canonical' only supports operation='read'; all other "
                    "operations read and write the local root."
                ),
            },
            indent=2,
        )
    if include_metadata:
        return json.dumps(
            {
                "status": OperationStatus.ERROR.value,
                "error": (
                    "include_metadata is not supported for canonical reads; "
                    "version history and snapshots are local state."
                ),
            },
            indent=2,
        )
    return None


async def canonical_read_branch(
    ctx: MCPContext | None,
    resolved_name: str,
    operation: str | None,
    parsed_op: FileOperation,
    include_metadata: bool,
    sections: list[str] | None,
) -> str:
    """Canonical read branch for manage_file validation flow."""

    from cortex.tools.files.manage_file_helpers import (
        log_validation_failure,
        manage_file_get_root,
    )

    canonical_err = _validate_canonical_read_request(parsed_op, include_metadata)
    if canonical_err is not None:
        await log_validation_failure(ctx, resolved_name, operation)
        return canonical_err
    root = await manage_file_get_root(ctx)
    return await canonical_manage_file_read(root, resolved_name, sections)


def _local_freshness(
    local_root: Path, file_name: str, canonical_sha256: str
) -> tuple[CanonicalLocalState, str | None]:
    """Freshness of the local counterpart under the same confinement rules."""

    parts = _normalized_parts(file_name)
    # AI: Shared local-context guard — a symlinked .cortex ancestor must
    # disable local freshness for files and plans alike (fail closed).
    if local_context_unsafe(local_root):
        return (CanonicalLocalState.UNSAFE, None)
    if len(parts) == 3 and parts[0] == CortexResourceType.CORTEX_DIR.value:
        candidate = _artifact_local_path(local_root, parts)
    else:
        candidate = _memory_bank_local_path(local_root, parts, file_name)
    if isinstance(candidate, CanonicalLocalState):
        return (candidate, None)
    if candidate is None or not candidate.exists():
        return (CanonicalLocalState.MISSING, None)
    local_digest = _safe_digest(candidate)
    if local_digest is None:
        return (CanonicalLocalState.UNREADABLE, None)
    if local_digest == canonical_sha256:
        return (CanonicalLocalState.IDENTICAL, local_digest)
    return (CanonicalLocalState.DIVERGED, local_digest)


def _artifact_local_path(
    local_root: Path, parts: list[str]
) -> Path | CanonicalLocalState | None:
    if parts[1] not in ARTIFACT_DIR_NAMES or Path(parts[2]).name != parts[2]:
        return CanonicalLocalState.UNSAFE
    return _confined_local_path(local_root / parts[0] / parts[1], parts[2], local_root)


def _memory_bank_local_path(
    local_root: Path, parts: list[str], file_name: str
) -> Path | CanonicalLocalState | None:
    if len(parts) != 1 or Path(file_name).name != file_name:
        return CanonicalLocalState.UNSAFE
    return _confined_local_path(
        get_cortex_path(local_root, CortexResourceType.MEMORY_BANK),
        parts[0],
        local_root,
    )


def _confined_local_path(
    directory: Path, name: str, local_root: Path
) -> Path | CanonicalLocalState | None:
    """Confined local counterpart path; UNSAFE on symlink interference.

    Returns None when the allowed directory or file is simply absent. The
    resolved path must stay inside the bound local root, so a symlinked
    ``.cortex`` ancestor cannot redirect freshness reads outside it.
    """

    if directory.is_symlink():
        return CanonicalLocalState.UNSAFE
    if not directory.is_dir():
        return None
    candidate = directory / name
    if candidate.is_symlink():
        return CanonicalLocalState.UNSAFE
    resolved = candidate.resolve()
    if not resolved.is_relative_to(directory.resolve()):
        return CanonicalLocalState.UNSAFE
    if not resolved.is_relative_to(local_root):
        return CanonicalLocalState.UNSAFE
    return resolved


def _safe_digest(path: Path) -> str | None:
    if not path.is_file():
        return None
    try:
        return sha256_bytes(path.read_bytes())
    except OSError:
        return None


__all__ = ["canonical_manage_file_read"]
