"""Internal states for compact scoped task evidence."""

from enum import Enum


class ScopedEvidenceState(str, Enum):
    """Whether task evidence exists and can be interpreted unambiguously."""

    PRESENT = "present"
    MISSING = "missing"
    INVALID = "invalid"
    CONFLICTING = "conflicting"
