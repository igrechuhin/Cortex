"""Validation dispatch and orchestration functions."""

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Literal, TypeAlias, TypedDict, cast

from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.managers.initialization import get_managers, get_project_root
from cortex.managers.manager_utils import get_manager
from cortex.tools.validation_duplication import handle_duplications_validation
from cortex.tools.validation_helpers import create_invalid_check_type_error
from cortex.tools.validation_infrastructure import handle_infrastructure_validation
from cortex.tools.validation_quality import handle_quality_validation
from cortex.tools.validation_roadmap_sync import handle_roadmap_sync_validation
from cortex.tools.validation_schema import handle_schema_validation
from cortex.tools.validation_timestamps import handle_timestamps_validation
from cortex.validation.duplication_detector import DuplicationDetector
from cortex.validation.quality_metrics import QualityMetrics
from cortex.validation.schema_validator import SchemaValidator
from cortex.validation.validation_config import ValidationConfig

ValidationManagers: TypeAlias = dict[
    str,
    FileSystemManager
    | MetadataIndex
    | SchemaValidator
    | DuplicationDetector
    | QualityMetrics
    | ValidationConfig,
]

CheckType: TypeAlias = Literal[
    "schema",
    "duplications",
    "quality",
    "infrastructure",
    "timestamps",
    "roadmap_sync",
]


class InfrastructureOptions(TypedDict):
    """Options for infrastructure validation."""

    commit_ci: bool
    code_quality: bool
    documentation: bool
    config: bool


async def handle_schema_validation_wrapper(
    validation_managers: ValidationManagers,
    root: Path,
    file_name: str | None,
) -> str:
    """Handle schema validation routing wrapper."""
    return await handle_schema_validation(
        cast(FileSystemManager, validation_managers["fs_manager"]),
        cast(SchemaValidator, validation_managers["schema_validator"]),
        root,
        file_name,
    )


async def handle_duplications_validation_wrapper(
    validation_managers: ValidationManagers,
    root: Path,
    similarity_threshold: float | None,
    suggest_fixes: bool,
) -> str:
    """Handle duplications validation wrapper."""
    return await handle_duplications_validation(
        cast(FileSystemManager, validation_managers["fs_manager"]),
        cast(DuplicationDetector, validation_managers["duplication_detector"]),
        cast(ValidationConfig, validation_managers["validation_config"]),
        root,
        similarity_threshold,
        suggest_fixes,
    )


async def handle_quality_validation_wrapper(
    validation_managers: ValidationManagers,
    root: Path,
    file_name: str | None,
) -> str:
    """Handle quality validation routing wrapper."""
    return await handle_quality_validation(
        cast(FileSystemManager, validation_managers["fs_manager"]),
        cast(MetadataIndex, validation_managers["metadata_index"]),
        cast(QualityMetrics, validation_managers["quality_metrics"]),
        cast(DuplicationDetector, validation_managers["duplication_detector"]),
        root,
        file_name,
    )


async def handle_infrastructure_validation_wrapper(
    root: Path,
    check_commit_ci_alignment: bool,
    check_code_quality_consistency: bool,
    check_documentation_consistency: bool,
    check_config_consistency: bool,
) -> str:
    """Handle infrastructure validation wrapper."""
    return await handle_infrastructure_validation(
        root,
        check_commit_ci_alignment,
        check_code_quality_consistency,
        check_documentation_consistency,
        check_config_consistency,
    )


async def handle_timestamps_validation_wrapper(
    validation_managers: ValidationManagers,
    root: Path,
    file_name: str | None,
) -> str:
    """Handle timestamps validation routing wrapper."""
    return await handle_timestamps_validation(
        cast(FileSystemManager, validation_managers["fs_manager"]),
        root,
        file_name,
    )


async def handle_roadmap_sync_validation_wrapper(
    validation_managers: ValidationManagers,
    root: Path,
    file_name: str | None,
) -> str:
    """Handle roadmap synchronization validation wrapper."""
    return await handle_roadmap_sync_validation(
        cast(FileSystemManager, validation_managers["fs_manager"]),
        root,
        file_name,
    )


def _create_validation_handlers(
    managers: ValidationManagers,
    root: Path,
    file_name: str | None,
    sim_threshold: float | None,
    suggest_fixes: bool,
    infra_opts: InfrastructureOptions,
) -> dict[str, Callable[[], Awaitable[str]]]:
    """Create validation handler functions."""
    return {
        "schema": lambda: handle_schema_validation_wrapper(managers, root, file_name),
        "duplications": lambda: handle_duplications_validation_wrapper(
            managers, root, sim_threshold, suggest_fixes
        ),
        "quality": lambda: handle_quality_validation_wrapper(managers, root, file_name),
        "infrastructure": lambda: handle_infrastructure_validation_wrapper(
            root,
            infra_opts["commit_ci"],
            infra_opts["code_quality"],
            infra_opts["documentation"],
            infra_opts["config"],
        ),
        "timestamps": lambda: handle_timestamps_validation_wrapper(
            managers, root, file_name
        ),
        "roadmap_sync": lambda: handle_roadmap_sync_validation_wrapper(
            managers, root, file_name
        ),
    }


async def _dispatch_validation(
    check_type: CheckType,
    validation_managers: dict[str, object],
    root: Path,
    file_name: str | None,
    similarity_threshold: float | None,
    suggest_fixes: bool,
    check_commit_ci_alignment: bool,
    check_code_quality_consistency: bool,
    check_documentation_consistency: bool,
    check_config_consistency: bool,
) -> str:
    """Dispatch validation to appropriate handler."""
    typed_managers = _get_typed_validation_managers(validation_managers)
    infra_opts: InfrastructureOptions = {
        "commit_ci": check_commit_ci_alignment,
        "code_quality": check_code_quality_consistency,
        "documentation": check_documentation_consistency,
        "config": check_config_consistency,
    }
    handlers = _create_validation_handlers(
        typed_managers, root, file_name, similarity_threshold, suggest_fixes, infra_opts
    )
    return await _execute_validation_handler(handlers, check_type)


async def _execute_validation_handler(
    handlers: dict[str, Callable[[], Awaitable[str]]],
    check_type: CheckType,
) -> str:
    """Execute validation handler for given check type.

    Args:
        handlers: Dictionary of validation handlers
        check_type: Type of validation to perform

    Returns:
        JSON string with validation results
    """
    handler = handlers.get(check_type)
    return await handler() if handler else create_invalid_check_type_error(check_type)


def _get_typed_validation_managers(
    validation_managers: dict[str, object],
) -> ValidationManagers:
    """Get typed validation managers from dict[str, object].

    Args:
        validation_managers: Dictionary of validation managers as object

    Returns:
        Typed dictionary of validation managers
    """
    return cast(
        dict[
            str,
            FileSystemManager
            | MetadataIndex
            | SchemaValidator
            | DuplicationDetector
            | QualityMetrics
            | ValidationConfig,
        ],
        validation_managers,
    )


async def setup_validation_managers(
    root: Path,
) -> dict[
    str,
    FileSystemManager
    | MetadataIndex
    | SchemaValidator
    | DuplicationDetector
    | QualityMetrics
    | ValidationConfig,
]:
    """Setup validation managers.

    Args:
        root: Project root path

    Returns:
        Dictionary with all validation managers
    """
    mgrs = await get_managers(root)
    fs_manager = cast(FileSystemManager, mgrs["fs"])
    metadata_index = cast(MetadataIndex, mgrs["index"])

    schema_validator = await get_manager(mgrs, "schema_validator", SchemaValidator)
    duplication_detector = await get_manager(
        mgrs, "duplication_detector", DuplicationDetector
    )
    quality_metrics = await get_manager(mgrs, "quality_metrics", QualityMetrics)
    validation_config = await get_manager(mgrs, "validation_config", ValidationConfig)

    return {
        "fs_manager": fs_manager,
        "metadata_index": metadata_index,
        "schema_validator": schema_validator,
        "duplication_detector": duplication_detector,
        "quality_metrics": quality_metrics,
        "validation_config": validation_config,
    }


async def prepare_validation_managers(
    project_root: str | None,
) -> tuple[Path, dict[str, object]]:
    """Prepare validation managers and root path.

    Args:
        project_root: Project root path

    Returns:
        Tuple of (root path, validation managers)
    """
    root = get_project_root(project_root)
    validation_managers = await setup_validation_managers(root)
    return root, cast(dict[str, object], validation_managers)


async def call_dispatch_validation(
    check_type: CheckType,
    managers: dict[str, object],
    root: Path,
    file_name: str | None,
    similarity_threshold: float | None,
    suggest_fixes: bool,
    check_commit_ci_alignment: bool,
    check_code_quality_consistency: bool,
    check_documentation_consistency: bool,
    check_config_consistency: bool,
) -> str:
    """Call dispatch validation with parameters."""
    return await _dispatch_validation(
        check_type,
        managers,
        root,
        file_name,
        similarity_threshold,
        suggest_fixes,
        check_commit_ci_alignment,
        check_code_quality_consistency,
        check_documentation_consistency,
        check_config_consistency,
    )
