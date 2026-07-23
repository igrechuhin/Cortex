"""Path-allowlist enforcement for propose_framework_optimization.

Every proposed target must resolve inside ``.cortex/synapse/`` or
``.cortex/rules/`` — never anywhere else, including ``src/`` or outside the
project root via traversal (``..``) or absolute-path tricks.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

ALLOWLISTED_DIR_PREFIXES: Final[tuple[str, ...]] = (".cortex/synapse", ".cortex/rules")


class PathAllowlistError(ValueError):
    """Raised when a proposed target path is outside the allowlisted directories."""


def _normalize_relative_path(relative_path: str) -> str:
    normalized = relative_path.strip().replace("\\", "/")
    if not normalized:
        raise PathAllowlistError("target path must be non-empty")
    return normalized


def validate_relative_path_lexically(relative_path: str) -> str:
    """Validate *relative_path* without touching the filesystem.

    Rejects absolute paths, ``..`` traversal segments, and any path whose
    normalized prefix is not one of :data:`ALLOWLISTED_DIR_PREFIXES`.
    """
    normalized = _normalize_relative_path(relative_path)
    candidate = Path(normalized)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise PathAllowlistError(f"path traversal rejected: {relative_path!r}")
    allowed = any(
        normalized == prefix or normalized.startswith(f"{prefix}/")
        for prefix in ALLOWLISTED_DIR_PREFIXES
    )
    if not allowed:
        message = (
            f"target path outside allowlist {ALLOWLISTED_DIR_PREFIXES}: "
            + f"{relative_path!r}"
        )
        raise PathAllowlistError(message)
    return normalized


def resolve_in_worktree(worktree_root: Path, relative_path: str) -> Path:
    """Validate and resolve *relative_path* to an absolute path in *worktree_root*.

    Re-checks the *resolved* path against the allowlisted roots (not just the
    lexical string) so a resolution surprise (e.g. a symlink) cannot silently
    escape the sandbox.
    """
    normalized = validate_relative_path_lexically(relative_path)
    resolved = (worktree_root / normalized).resolve()
    allowed_roots = tuple(
        (worktree_root / prefix).resolve() for prefix in ALLOWLISTED_DIR_PREFIXES
    )
    if not any(resolved.is_relative_to(root) for root in allowed_roots):
        raise PathAllowlistError(f"resolved path escapes allowlist: {relative_path!r}")
    return resolved
