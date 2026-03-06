#!/usr/bin/env python3
"""Validation-phase manager factory helpers (Phase 3)."""

from pathlib import Path
from typing import cast

from cortex.core.metadata_index import MetadataIndex
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.managers.builder_types import ManagersBuilder
from cortex.managers.lazy_manager import LazyManager
from cortex.validation.duplication_detector import DuplicationDetector
from cortex.validation.quality_metrics import QualityMetrics
from cortex.validation.schema_validator import SchemaValidator
from cortex.validation.validation_config import ValidationConfig


async def _create_validation_config(project_root: Path) -> ValidationConfig:
    """Create ValidationConfig instance."""
    return ValidationConfig(project_root)


async def _create_schema_validator(
    project_root: Path, managers: ManagersBuilder
) -> SchemaValidator:
    """Create SchemaValidator instance."""
    _ = managers  # Kept for API compatibility
    config_dir = get_cortex_path(project_root, CortexResourceType.CONFIG)
    return SchemaValidator(config_path=config_dir / "validation.json")


async def _create_duplication_detector() -> DuplicationDetector:
    """Create DuplicationDetector instance."""
    return DuplicationDetector()


async def _create_quality_metrics(managers: ManagersBuilder) -> QualityMetrics:
    """Create QualityMetrics instance."""
    from cortex.managers.utils import get_manager

    schema_validator = await get_manager(managers, "schema_validator", SchemaValidator)
    metadata_index = cast(MetadataIndex, managers["index"])
    return QualityMetrics(
        schema_validator=schema_validator, metadata_index=metadata_index
    )


def add_validation_managers(managers: ManagersBuilder, project_root: Path) -> None:
    """Add Phase 3 validation managers as lazy.

    Args:
        managers: Managers dictionary to update
        project_root: Project root directory
    """
    managers["validation_config"] = LazyManager(
        lambda: _create_validation_config(project_root), name="validation_config"
    )
    managers["schema_validator"] = LazyManager(
        lambda: _create_schema_validator(project_root, managers),
        name="schema_validator",
    )
    managers["duplication_detector"] = LazyManager(
        lambda: _create_duplication_detector(), name="duplication_detector"
    )
    managers["quality_metrics"] = LazyManager(
        lambda: _create_quality_metrics(managers), name="quality_metrics"
    )
