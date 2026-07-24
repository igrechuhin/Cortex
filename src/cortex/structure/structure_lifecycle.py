#!/usr/bin/env python3
"""
Lifecycle management for Memory Bank structure.

This module provides a unified interface to structure setup and health
checking. Delegates to specialized components.
"""

from pathlib import Path

from cortex.core.models import ModelDict
from cortex.structure.lifecycle.health import StructureHealthChecker
from cortex.structure.lifecycle.setup import StructureSetup
from cortex.structure.models import (
    HealthCheckResult,
    SetupReport,
    StructureInfoResult,
    StructurePaths,
)
from cortex.structure.structure_config import (
    PLAN_TEMPLATES,
    STANDARD_MEMORY_BANK_FILES,
    StructureConfig,
)


class StructureLifecycleManager:
    """Manages lifecycle operations for Memory Bank structure.

    This is the main orchestrator that delegates to specialized components:
    - StructureSetup: Directory and file creation
    - StructureHealthChecker: Health validation
    """

    def __init__(self, project_root: Path):
        """Initialize lifecycle manager.

        Args:
            project_root: Root directory of the project
        """
        self.config = StructureConfig(project_root)
        self.setup = StructureSetup(self.config)
        self.health = StructureHealthChecker(self.config)

    @property
    def project_root(self) -> Path:
        """Get project root path."""
        return self.config.project_root

    @property
    def structure_config(self) -> ModelDict:
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

    async def create_structure(self, force: bool = False) -> SetupReport:
        """Create the complete standardized structure.

        Delegates to StructureSetup component.

        Args:
            force: Force recreation even if structure exists

        Returns:
            Report of created directories and files
        """
        return await self.setup.create_structure(force)

    def check_structure_health(self) -> HealthCheckResult:
        """Check the health of the project structure.

        Delegates to StructureHealthChecker component.

        Returns:
            Health report with score and recommendations
        """
        return self.health.check_structure_health()

    def get_structure_info(self) -> StructureInfoResult:
        """Get current structure configuration and status.

        Returns:
            Structure information including paths and configuration
        """
        from cortex.core.models import JsonDict
        from cortex.structure.models import StructureConfigModel

        version_val = self.structure_config.get("version", "2.0")
        version = str(version_val) if isinstance(version_val, str) else "2.0"

        structure_config_dict = JsonDict.model_validate(self.structure_config)
        configuration = StructureConfigModel.model_validate(
            structure_config_dict.model_dump()
        )

        health: HealthCheckResult | None = None
        if self.get_path("root").exists():
            health = self.check_structure_health()

        return StructureInfoResult(
            version=version,
            paths=StructurePaths(
                root=str(self.get_path("root")),
                memory_bank=str(self.get_path("memory_bank")),
                rules=str(self.get_path("rules")),
                plans=str(self.get_path("plans")),
                config=str(self.get_path("config")),
                reviews=str(self.get_path("reviews")),
            ),
            configuration=configuration,
            exists=self.get_path("root").exists(),
            health=health,
        )


# Expose constants and standard files for convenience
__all__ = [
    "StructureLifecycleManager",
    "STANDARD_MEMORY_BANK_FILES",
    "PLAN_TEMPLATES",
]
