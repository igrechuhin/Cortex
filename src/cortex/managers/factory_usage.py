#!/usr/bin/env python3
"""Usage-tracker manager factory helper (Phase 29)."""

from pathlib import Path

from cortex.managers.builder_types import ManagersBuilder
from cortex.managers.lazy_manager import LazyManager
from cortex.managers.usage_tracker import UsageTracker


async def _create_usage_tracker(project_root: Path) -> UsageTracker:
    """Create UsageTracker instance (Phase 29)."""
    return UsageTracker(project_root)


def add_usage_tracker(managers: ManagersBuilder, project_root: Path) -> None:
    """Add usage tracker manager (Phase 29).

    Args:
        managers: Managers dictionary to update
        project_root: Project root directory
    """
    managers["usage_tracker"] = LazyManager(
        lambda: _create_usage_tracker(project_root), name="usage_tracker"
    )
