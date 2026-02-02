"""
MCP tool annotations helpers.

This module provides small helper utilities for defining MCP tool
`annotations` metadata in a consistent, type-safe way.

The helpers return `mcp.types.ToolAnnotations` instances that can be
passed directly to `@mcp.tool(annotations=...)`.
"""

from typing import Final

from mcp.types import ToolAnnotations

# Re-export ToolAnnotations for convenience
__all__ = [
    "ToolAnnotations",
    "destructive_annotations",
    "external_annotations",
    "read_only_annotations",
    "safe_write_annotations",
]

_READ_ONLY_HINT: Final[bool] = True
_NOT_DESTRUCTIVE: Final[bool] = False


def read_only_annotations(
    title: str,
    *,
    open_world: bool = False,
    idempotent: bool = True,
) -> ToolAnnotations:
    """Annotations for read-only, idempotent tools.

    Intended for tools that only read internal state and return the
    same result for the same inputs.
    """
    return ToolAnnotations(
        title=title,
        readOnlyHint=_READ_ONLY_HINT,
        destructiveHint=_NOT_DESTRUCTIVE,
        idempotentHint=idempotent,
        openWorldHint=open_world,
    )


def safe_write_annotations(
    title: str,
    *,
    open_world: bool = False,
) -> ToolAnnotations:
    """Annotations for tools that create or update data safely.

    These tools may modify files or configuration but are not
    considered destructive (no hard deletes or irreversible changes).
    Results are typically not idempotent because repeated calls can
    create additional versions or apply changes multiple times.
    """
    return ToolAnnotations(
        title=title,
        readOnlyHint=False,
        destructiveHint=_NOT_DESTRUCTIVE,
        idempotentHint=False,
        openWorldHint=open_world,
    )


def destructive_annotations(
    title: str,
    *,
    open_world: bool = False,
) -> ToolAnnotations:
    """Annotations for destructive tools.

    Use for tools that can overwrite or delete data (for example,
    rollback operations).
    """
    return ToolAnnotations(
        title=title,
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=open_world,
    )


def external_annotations(
    title: str,
    *,
    read_only: bool,
    destructive: bool = False,
    idempotent: bool = False,
) -> ToolAnnotations:
    """Annotations for tools that interact with external systems.

    Use this helper for tools that rely on subprocesses, network
    access, or other out-of-process integrations. The behavioral flags
    mirror the standard MCP hints while always setting ``openWorldHint``
    to ``True``.
    """
    return ToolAnnotations(
        title=title,
        readOnlyHint=read_only,
        destructiveHint=destructive,
        idempotentHint=idempotent,
        openWorldHint=True,
    )
