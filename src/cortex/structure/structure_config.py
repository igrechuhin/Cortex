#!/usr/bin/env python3
"""
Shared configuration and constants for Memory Bank structure management.

This module provides shared infrastructure used by both lifecycle and migration
managers to avoid code duplication.
"""

import json
from pathlib import Path
from typing import cast

from cortex.core.async_file_utils import open_async_text_file

# Default structure definition
DEFAULT_STRUCTURE: dict[str, object] = {
    "version": "2.0",
    "layout": {
        "root": ".cortex",
        "memory_bank": "memory-bank",
        "rules": "rules",
        "plans": "plans",
        "config": "config",
        "archived": "archived",
    },
    "cursor_integration": {
        "enabled": True,
        "symlink_location": ".cursor",
        "symlinks": {
            "memory_bank": True,
            "rules": True,
            "plans": True,
        },
    },
    "housekeeping": {
        "auto_cleanup": True,
        "stale_plan_days": 90,
        "archive_completed_plans": True,
        "detect_duplicates": True,
    },
    "rules": {
        "use_submodule": False,
        "submodule_path": "rules/shared",
        "local_rules_path": "rules/local",
        "shared_repo_url": None,
    },
}

# Standard memory bank files
STANDARD_MEMORY_BANK_FILES: list[str] = [
    "projectBrief.md",
    "productContext.md",
    "activeContext.md",
    "systemPatterns.md",
    "techContext.md",
    "progress.md",
    "roadmap.md",
]

# Plan templates
PLAN_TEMPLATES: list[str] = [
    "feature.md",
    "bugfix.md",
    "refactoring.md",
    "research.md",
]


class StructureConfig:
    """Shared configuration and path resolution for structure management."""

    def __init__(self, project_root: Path):
        """Initialize configuration.

        Args:
            project_root: Root directory of the project
        """
        self.project_root: Path = project_root
        self.structure_config_path: Path = (
            project_root / ".cortex" / "config" / "structure.json"
        )
        self.structure_config: dict[str, object] = self._load_structure_config()

    def _load_structure_config(self) -> dict[str, object]:
        """
        Load structure configuration or return default.

        Note:
            This method uses synchronous I/O during initialization for simplicity.
            For performance-critical paths, consider using async alternatives.
        """
        if self.structure_config_path.exists():
            try:
                with open(self.structure_config_path, encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                from cortex.core.logging_config import logger

                logger.warning(f"Failed to load structure config, using default: {e}")
                return DEFAULT_STRUCTURE.copy()
        return DEFAULT_STRUCTURE.copy()

    async def save_structure_config(self) -> None:
        """Save structure configuration to disk."""
        self.structure_config_path.parent.mkdir(parents=True, exist_ok=True)
        async with open_async_text_file(self.structure_config_path, "w", "utf-8") as f:
            _ = await f.write(json.dumps(self.structure_config, indent=2))

    def get_path(self, component: str) -> Path:
        """Get path for a structure component.

        Args:
            component: Component name (e.g., 'knowledge', 'rules', 'plans')

        Returns:
            Resolved path for the component
        """
        layout_val = self.structure_config.get("layout")
        if not isinstance(layout_val, dict):
            raise ValueError("Invalid structure config: layout must be a dict")
        layout = cast(dict[str, object], layout_val)
        root_val = layout.get("root")
        if not isinstance(root_val, str):
            raise ValueError("Invalid structure config: layout.root must be a string")
        root = self.project_root / root_val

        if component == "root":
            return root
        elif component in layout:
            component_val = layout[component]
            if not isinstance(component_val, str):
                raise ValueError(
                    f"Invalid structure config: layout.{component} must be a string"
                )
            return root / component_val
        else:
            raise ValueError(f"Unknown component: {component}")
