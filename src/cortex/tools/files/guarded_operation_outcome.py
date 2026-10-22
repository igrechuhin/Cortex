"""Domain refusals for the existing guarded Markdown and owner operations."""

from enum import StrEnum


class GuardedOperationOutcome(StrEnum):
    """Only established stale-preimage and policy boundaries have domain codes."""

    STALE_BASE = "STALE_BASE"
    POLICY_BLOCKED = "POLICY_BLOCKED"
