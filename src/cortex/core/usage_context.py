"""Context variable for current managers (Phase 29 usage tracking).

Set by get_managers() when tools run so that usage recording can obtain
the UsageTracker without an extra get_managers() call in the hot path.
"""

import contextvars
from typing import Any

_current_managers: contextvars.ContextVar[dict[str, Any] | None] = (
    contextvars.ContextVar("current_managers", default=None)
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
