#!/usr/bin/env python3
"""Execution-phase manager factory helpers (Phase 5.3–5.4)."""

from pathlib import Path

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.linking.validator import LinkValidator
from cortex.managers.builder_types import ManagersBuilder
from cortex.managers.lazy_manager import LazyManager
from cortex.managers.types import CoreManagersDict
from cortex.optimization.config import OptimizationConfig
from cortex.refactoring.adaptation_config import AdaptationConfig
from cortex.refactoring.approval_manager import ApprovalManager
from cortex.refactoring.learning_engine import LearningEngine
from cortex.refactoring.refactoring_executor import RefactoringExecutor
from cortex.refactoring.rollback_manager import RollbackManager


async def _create_refactoring_executor(
    project_root: Path, core_managers: CoreManagersDict, managers: ManagersBuilder
) -> RefactoringExecutor:
    """Create RefactoringExecutor instance."""
    from cortex.managers.utils import get_manager

    fs_manager = core_managers.fs
    metadata_index = core_managers.index
    version_manager = core_managers.versions
    link_validator = await get_manager(managers, "link_validator", LinkValidator)
    memory_bank_path = get_cortex_path(project_root, CortexResourceType.MEMORY_BANK)

    return RefactoringExecutor(
        memory_bank_dir=memory_bank_path,
        fs_manager=fs_manager,
        version_manager=version_manager,
        link_validator=link_validator,
        metadata_index=metadata_index,
        config=None,
    )


async def _create_approval_manager(
    project_root: Path, managers: ManagersBuilder
) -> ApprovalManager:
    """Create ApprovalManager instance."""
    _ = managers  # Not needed, kept for API compatibility
    memory_bank_path = get_cortex_path(project_root, CortexResourceType.MEMORY_BANK)
    return ApprovalManager(memory_bank_dir=memory_bank_path, config=None)


async def _create_rollback_manager(
    project_root: Path, core_managers: CoreManagersDict, managers: ManagersBuilder
) -> RollbackManager:
    """Create RollbackManager instance."""
    _ = managers  # Not needed, kept for API compatibility
    fs_manager = core_managers.fs
    version_manager = core_managers.versions
    metadata_index = core_managers.index
    memory_bank_path = get_cortex_path(project_root, CortexResourceType.MEMORY_BANK)

    return RollbackManager(
        memory_bank_dir=memory_bank_path,
        fs_manager=fs_manager,
        version_manager=version_manager,
        metadata_index=metadata_index,
    )


async def _create_learning_engine(
    project_root: Path, managers: ManagersBuilder
) -> LearningEngine:
    """Create LearningEngine instance."""
    from cortex.managers.utils import get_manager

    optimization_config = await get_manager(
        managers, "optimization_config", OptimizationConfig
    )
    memory_bank_path = get_cortex_path(project_root, CortexResourceType.MEMORY_BANK)

    _ = optimization_config  # Kept for API compatibility
    return LearningEngine(
        memory_bank_dir=memory_bank_path,
        config=None,
    )


async def _create_adaptation_config(managers: ManagersBuilder) -> AdaptationConfig:
    """Create AdaptationConfig instance."""
    _ = managers  # Kept for API compatibility
    return AdaptationConfig()


def add_execution_managers(
    managers: ManagersBuilder,
    project_root: Path,
    core_managers: CoreManagersDict,
) -> None:
    """Add Phase 5.3-5.4 execution managers as lazy.

    Args:
        managers: Managers dictionary to update
        project_root: Project root directory
        core_managers: Core managers dictionary
    """
    managers["refactoring_executor"] = LazyManager(
        lambda: _create_refactoring_executor(project_root, core_managers, managers),
        name="refactoring_executor",
    )
    managers["approval_manager"] = LazyManager(
        lambda: _create_approval_manager(project_root, managers),
        name="approval_manager",
    )
    managers["rollback_manager"] = LazyManager(
        lambda: _create_rollback_manager(project_root, core_managers, managers),
        name="rollback_manager",
    )
    managers["learning_engine"] = LazyManager(
        lambda: _create_learning_engine(project_root, managers), name="learning_engine"
    )
    managers["adaptation_config"] = LazyManager(
        lambda: _create_adaptation_config(managers), name="adaptation_config"
    )
