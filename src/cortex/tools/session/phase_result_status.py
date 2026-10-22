"""Closed set of exact publication verification outcomes."""

from enum import StrEnum


class PhaseResultStatus(StrEnum):
    """Only missing publication evidence permits explicit replay."""

    EXACT = "exact"
    MISSING = "missing"
    UNCERTAIN = "uncertain"
    CONFLICTING = "conflicting"
