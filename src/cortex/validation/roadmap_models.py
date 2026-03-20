"""Roadmap section constants and enums.

Canonical section headers for roadmap.md. The legacy duplicate model classes
(TodoItemModel, RoadmapReferenceModel, SyncValidationResultModel) were removed
in HI-4; use the canonical models in ``roadmap_sync.py`` instead.
"""

from enum import StrEnum


class RoadmapSection(StrEnum):
    """Canonical roadmap section headers. Single source of truth."""

    BLOCKERS = "Blockers (ASAP Priority)"
    ACTIVE_WORK = "Active Work (in progress)"
    FUTURE = "Future Enhancements"
    PENDING = "Pending plans (from .cortex/plans)"


SECTION_TO_KEY: dict[str, str] = {
    RoadmapSection.BLOCKERS: "blockers",
    RoadmapSection.ACTIVE_WORK: "active_work",
    RoadmapSection.FUTURE: "future",
    RoadmapSection.PENDING: "pending",
}


KEY_TO_SECTION: dict[str, str] = {v: k for k, v in SECTION_TO_KEY.items()}


__all__ = [
    "KEY_TO_SECTION",
    "RoadmapSection",
    "SECTION_TO_KEY",
]
