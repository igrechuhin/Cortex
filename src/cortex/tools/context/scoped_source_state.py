"""Internal states for selected scoped source revisions."""

from enum import Enum


class ScopedSourceState(str, Enum):
    """Availability and identity of an exact selected source."""

    PRESENT = "present"
    MISSING = "missing"
    UNREADABLE = "unreadable"
    INVALID = "invalid"
    AMBIGUOUS = "ambiguous"
