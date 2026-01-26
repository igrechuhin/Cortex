#!/usr/bin/env python3
"""
Structure Manager Facade (DEPRECATED - Use StructureLifecycleManager or StructureMigrationManager).

This module maintains backward compatibility by delegating to the new split modules.
For new code, import directly from structure_lifecycle or structure_migration.
"""

from pathlib import Path

from cortex.core.models import ModelDict
from cortex.structure.structure_config import (
    DEFAULT_STRUCTURE,
    PLAN_TEMPLATES,
    STANDARD_MEMORY_BANK_FILES,
)
from cortex.structure.structure_lifecycle import StructureLifecycleManager
from cortex.structure.structure_migration import StructureMigrationManager


class StructureManager:
    """Facade combining lifecycle and migration managers (DEPRECATED).

    This class is maintained for backward compatibility. New code should use:
    - StructureLifecycleManager for setup, health checks, and housekeeping
    - StructureMigrationManager for legacy structure migration
    """

    # Expose constants for backward compatibility
    DEFAULT_STRUCTURE = DEFAULT_STRUCTURE
    STANDARD_MEMORY_BANK_FILES = STANDARD_MEMORY_BANK_FILES
    PLAN_TEMPLATES = PLAN_TEMPLATES

    def __init__(self, project_root: Path):
        """Initialize structure manager.

        Args:
            project_root: Root directory of the project
        """
        self.project_root = project_root
        self._lifecycle = StructureLifecycleManager(project_root)
        self._migration = StructureMigrationManager(project_root)

        # Expose config for backward compatibility
        self.structure_config_path = self._lifecycle.structure_config_path
        self.structure_config: ModelDict = self._lifecycle.structure_config

    # Delegate lifecycle methods
    async def create_structure(self, force: bool = False) -> ModelDict:
        """Create the complete standardized structure."""
        report = await self._lifecycle.create_structure(force)
        return report.model_dump(mode="json")

    def setup_cursor_integration(self) -> ModelDict:
        """Setup Cursor IDE integration via symlinks."""
        report = self._lifecycle.setup_cursor_integration()
        return report.model_dump(mode="json")

    def check_structure_health(self) -> ModelDict:
        """Check the health of the project structure."""
        health = self._lifecycle.check_structure_health()
        return health.model_dump(mode="json")

    def get_structure_info(self) -> ModelDict:
        """Get current structure configuration and status."""
        info = self._lifecycle.get_structure_info()
        return info.model_dump(mode="json")

    def generate_plans_readme(self) -> str:
        """Generate README content for plans directory."""
        from cortex.structure.structure_templates import generate_plans_readme

        return generate_plans_readme()

    def generate_memory_bank_readme(self) -> str:
        """Generate README content for memory-bank directory."""
        from cortex.structure.structure_templates import (
            generate_memory_bank_readme,
        )

        return generate_memory_bank_readme()

    def generate_rules_readme(self) -> str:
        """Generate README content for rules directory."""
        from cortex.structure.structure_templates import generate_rules_readme

        return generate_rules_readme()

    # Delegate migration methods
    def detect_legacy_structure(self) -> str | None:
        """Detect legacy structure type."""
        return self._migration.detect_legacy_structure()

    async def migrate_legacy_structure(
        self,
        legacy_type: str | None = None,
        backup: bool = True,
        archive: bool = True,
    ) -> ModelDict:
        """Migrate from legacy structure to standardized structure."""
        report = await self._migration.migrate_legacy_structure(
            legacy_type, backup, archive
        )
        return report.model_dump(mode="json")

    # Delegate config methods
    async def save_structure_config(self) -> None:
        """Save structure configuration."""
        await self._lifecycle.save_structure_config()

    def get_path(self, component: str) -> Path:
        """Get path for a structure component."""
        return self._lifecycle.get_path(component)


# Export for public API
__all__ = [
    "StructureManager",
    "StructureLifecycleManager",
    "StructureMigrationManager",
    "DEFAULT_STRUCTURE",
    "STANDARD_MEMORY_BANK_FILES",
    "PLAN_TEMPLATES",
]
