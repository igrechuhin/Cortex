#!/usr/bin/env python3
"""
Lifecycle management for Memory Bank structure.

This module provides a unified interface to structure setup, health checking,
and Cursor IDE integration. Delegates to specialized components.
"""

from pathlib import Path

from cortex.structure.lifecycle.health import StructureHealthChecker
from cortex.structure.lifecycle.setup import StructureSetup
from cortex.structure.lifecycle.symlinks import CursorSymlinkManager
from cortex.structure.structure_config import (
    PLAN_TEMPLATES,
    STANDARD_MEMORY_BANK_FILES,
    StructureConfig,
)


class StructureLifecycleManager:
    """Manages lifecycle operations for Memory Bank structure.

    This is the main orchestrator that delegates to specialized components:
    - StructureSetup: Directory and file creation
    - CursorSymlinkManager: Symlink management
    - StructureHealthChecker: Health validation
    """

    def __init__(self, project_root: Path):
        """Initialize lifecycle manager.

        Args:
            project_root: Root directory of the project
        """
        self.config = StructureConfig(project_root)
        self.setup = StructureSetup(self.config)
        self.symlinks = CursorSymlinkManager(self.config)
        self.health = StructureHealthChecker(self.config)

    @property
    def project_root(self) -> Path:
        """Get project root path."""
        return self.config.project_root

    @property
    def structure_config(self) -> dict[str, object]:
        """Get structure configuration."""
        return self.config.structure_config

    @property
    def structure_config_path(self) -> Path:
        """Get structure configuration path."""
        return self.config.structure_config_path

    def get_path(self, component: str) -> Path:
        """Get path for a structure component.

        Args:
            component: Component name

        Returns:
            Resolved path
        """
        return self.config.get_path(component)

    async def save_structure_config(self) -> None:
        """Save structure configuration."""
        await self.config.save_structure_config()

    async def create_structure(self, force: bool = False) -> dict[str, object]:
        """Create the complete standardized structure.

        Delegates to StructureSetup component.

        Args:
            force: Force recreation even if structure exists

        Returns:
            Report of created directories and files
        """
        return await self.setup.create_structure(force)

    def setup_cursor_integration(self) -> dict[str, object]:
        """Setup Cursor IDE integration via symlinks.

        Delegates to CursorSymlinkManager component.

        Returns:
            Report of created symlinks
        """
        return self.symlinks.setup_cursor_integration()

    def create_symlink(
        self, target: Path, link: Path, report: dict[str, object]
    ) -> None:
        """Create a symlink with cross-platform compatibility.

        Delegates to CursorSymlinkManager component.

        Args:
            target: Target path (what the symlink points to)
            link: Symlink path (the symlink itself)
            report: Report dictionary to update
        """
        self.symlinks.create_symlink(target, link, report)

    def check_structure_health(self) -> dict[str, object]:
        """Check the health of the project structure.

        Delegates to StructureHealthChecker component.

        Returns:
            Health report with score and recommendations
        """
        return self.health.check_structure_health()

    def get_structure_info(self) -> dict[str, object]:
        """Get current structure configuration and status.

        Returns:
            Structure information including paths and configuration
        """
        return {
            "version": self.structure_config["version"],
            "paths": {
                "root": str(self.get_path("root")),
                "memory_bank": str(self.get_path("memory_bank")),
                "rules": str(self.get_path("rules")),
                "plans": str(self.get_path("plans")),
                "config": str(self.get_path("config")),
            },
            "configuration": self.structure_config,
            "exists": self.get_path("root").exists(),
            "health": (
                self.check_structure_health()
                if self.get_path("root").exists()
                else None
            ),
        }


# Expose constants and standard files for backward compatibility
__all__ = [
    "StructureLifecycleManager",
    "STANDARD_MEMORY_BANK_FILES",
    "PLAN_TEMPLATES",
]
