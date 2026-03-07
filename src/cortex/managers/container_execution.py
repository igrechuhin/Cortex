"""Factory methods for creating Phase 5.3–5.4 execution and learning manager instances."""

from pathlib import Path
from typing import cast

from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.models import ModelDict
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.version_manager import VersionManager
from cortex.linking.validator import LinkValidator
from cortex.optimization.config import OptimizationConfig
from cortex.refactoring.adaptation_config import AdaptationConfig
from cortex.refactoring.approval_manager import ApprovalManager
from cortex.refactoring.learning_engine import LearningEngine
from cortex.refactoring.refactoring_executor import RefactoringExecutor
from cortex.refactoring.rollback_manager import RollbackManager

from .container_config import (
    ExecutionManagers,
    FoundationManagers,
    LinkingManagers,
    OptimizationManagers,
)


def create_execution_managers_from_deps(
    project_root: Path,
    foundation_managers: FoundationManagers,
    linking_managers: LinkingManagers,
    optimization_managers: OptimizationManagers,
) -> ExecutionManagers:
    """Create execution managers from all dependencies."""
    memory_bank_path = get_cortex_path(project_root, CortexResourceType.MEMORY_BANK)
    file_system = foundation_managers[0]
    version_manager = foundation_managers[4]
    metadata_index = foundation_managers[1]
    link_validator = linking_managers[2]
    optimization_config = optimization_managers[0]
    return create_execution_managers(
        memory_bank_path,
        file_system,
        version_manager,
        link_validator,
        metadata_index,
        optimization_config,
    )


def create_execution_managers(
    memory_bank_path: Path,
    file_system: FileSystemManager,
    version_manager: VersionManager,
    link_validator: LinkValidator,
    metadata_index: MetadataIndex,
    optimization_config: OptimizationConfig,
) -> tuple[
    RefactoringExecutor,
    ApprovalManager,
    RollbackManager,
    LearningEngine,
    AdaptationConfig,
]:
    """Create Phase 5.3-5.4 execution and learning managers."""
    managers = _create_all_execution_managers(
        memory_bank_path,
        file_system,
        version_manager,
        link_validator,
        metadata_index,
        optimization_config,
    )
    return _build_execution_managers_tuple(*managers)


def _create_all_execution_managers(
    memory_bank_path: Path,
    file_system: FileSystemManager,
    version_manager: VersionManager,
    link_validator: LinkValidator,
    metadata_index: MetadataIndex,
    optimization_config: OptimizationConfig,
) -> tuple[
    RefactoringExecutor,
    ApprovalManager,
    RollbackManager,
    LearningEngine,
    AdaptationConfig,
]:
    """Create all execution managers."""
    core_managers = _create_core_execution_managers(
        memory_bank_path,
        file_system,
        version_manager,
        link_validator,
        metadata_index,
        optimization_config,
    )
    learning_components = _create_learning_components(
        memory_bank_path, optimization_config
    )
    return _build_execution_managers_tuple(*core_managers, *learning_components)


def _create_core_execution_managers(
    memory_bank_path: Path,
    file_system: FileSystemManager,
    version_manager: VersionManager,
    link_validator: LinkValidator,
    metadata_index: MetadataIndex,
    optimization_config: OptimizationConfig,
) -> tuple[RefactoringExecutor, ApprovalManager, RollbackManager]:
    """Create core execution managers."""
    refactoring_executor = _create_refactoring_executor(
        memory_bank_path,
        file_system,
        version_manager,
        link_validator,
        metadata_index,
        optimization_config,
    )
    approval_manager = _create_approval_manager(memory_bank_path, optimization_config)
    rollback_manager = _create_rollback_manager(
        memory_bank_path,
        file_system,
        version_manager,
        metadata_index,
        optimization_config,
    )
    return refactoring_executor, approval_manager, rollback_manager


def _create_learning_components(
    memory_bank_path: Path, optimization_config: OptimizationConfig
) -> tuple[LearningEngine, AdaptationConfig]:
    """Create learning engine and adaptation config."""
    learning_engine = _create_learning_engine(memory_bank_path, optimization_config)
    adaptation_config = _create_adaptation_config(optimization_config)
    return learning_engine, adaptation_config


def _build_execution_managers_tuple(
    refactoring_executor: RefactoringExecutor,
    approval_manager: ApprovalManager,
    rollback_manager: RollbackManager,
    learning_engine: LearningEngine,
    adaptation_config: AdaptationConfig,
) -> tuple[
    RefactoringExecutor,
    ApprovalManager,
    RollbackManager,
    LearningEngine,
    AdaptationConfig,
]:
    """Build tuple of execution managers."""
    return (
        refactoring_executor,
        approval_manager,
        rollback_manager,
        learning_engine,
        adaptation_config,
    )


def _create_refactoring_executor(
    memory_bank_path: Path,
    file_system: FileSystemManager,
    version_manager: VersionManager,
    link_validator: LinkValidator,
    metadata_index: MetadataIndex,
    optimization_config: OptimizationConfig,
) -> RefactoringExecutor:
    """Create refactoring executor manager."""
    return RefactoringExecutor(
        memory_bank_dir=memory_bank_path,
        fs_manager=file_system,
        version_manager=version_manager,
        link_validator=link_validator,
        metadata_index=metadata_index,
        config=None,
    )


def _create_approval_manager(
    memory_bank_path: Path,
    optimization_config: OptimizationConfig,
) -> ApprovalManager:
    """Create approval manager."""
    return ApprovalManager(memory_bank_dir=memory_bank_path, config=None)


def _create_rollback_manager(
    memory_bank_path: Path,
    file_system: FileSystemManager,
    version_manager: VersionManager,
    metadata_index: MetadataIndex,
    optimization_config: OptimizationConfig,
) -> RollbackManager:
    """Create rollback manager."""
    return RollbackManager(
        memory_bank_dir=memory_bank_path,
        fs_manager=file_system,
        version_manager=version_manager,
        metadata_index=metadata_index,
        config=None,
    )


def _create_learning_engine(
    memory_bank_path: Path,
    optimization_config: OptimizationConfig,
) -> LearningEngine:
    """Create learning engine."""
    return LearningEngine(
        memory_bank_dir=memory_bank_path,
        config=cast(
            ModelDict | None,
            optimization_config.get("self_evolution.learning", {}),
        ),
    )


def _create_adaptation_config(
    optimization_config: OptimizationConfig,
) -> AdaptationConfig:
    """Create adaptation config."""
    return AdaptationConfig(base_config=None)
