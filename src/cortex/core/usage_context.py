"""Context variable for current managers (Phase 29 usage tracking).

Set by get_managers() when tools run so that usage recording can obtain
the UsageTracker without an extra get_managers() call in the hot path.
Also stores the project root used for those managers so tools can reuse
them and avoid re-initializing on every call.
"""

from __future__ import annotations

import contextvars
from pathlib import Path
from typing import Any

from cortex.core.context_logging import MCPContext

_current_managers: contextvars.ContextVar[dict[str, Any] | None] = (
    contextvars.ContextVar("current_managers", default=None)
)
_current_project_root: contextvars.ContextVar[Path | None] = contextvars.ContextVar(
    "current_project_root", default=None
)


def set_current_managers(managers: dict[str, Any] | None) -> None:
    """Set the current managers dict for this context (e.g. request).

    Called by get_managers() when returning so usage recording can read it.

    Args:
        managers: Managers dictionary or None to clear
    """
    _ = _current_managers.set(managers)


def get_current_managers() -> dict[str, Any] | None:
    """Return the current managers dict for this context, or None."""
    return _current_managers.get()


def set_current_project_root(root: Path | None) -> None:
    """Set the project root for the current managers in this context."""
    _ = _current_project_root.set(root)


def get_current_project_root() -> Path | None:
    """Return the project root for the current managers, or None."""
    return _current_project_root.get()


async def get_or_resolve_project_root(ctx: MCPContext | None) -> Path:
    """Return cached project root if set, otherwise resolve via ctx.

    Use this in tools so root is resolved once per session and reused.
    """
    root = get_current_project_root()
    if root is not None:
        return root
    from cortex.core.project_root_resolver import resolve_project_root_async

    return await resolve_project_root_async(None, ctx)
