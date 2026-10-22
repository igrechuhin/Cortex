"""Internal declared-dependency readiness for scoped task evidence."""

from enum import Enum


class ScopedReadiness(str, Enum):
    """Readiness inferred only from selected declared dependency evidence."""

    READY = "ready"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"
