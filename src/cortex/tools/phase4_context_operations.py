"""
Phase 4: Context Loading Operations

This module contains the implementation logic for the load_context tool.
"""

import json
from typing import cast

from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.managers.manager_utils import get_manager
from cortex.optimization.context_optimizer import ContextOptimizer
from cortex.optimization.optimization_config import OptimizationConfig
from cortex.optimization.optimization_strategies import OptimizationResult


async def load_context_impl(
    mgrs: dict[str, object],
    task_description: str,
    token_budget: int | None,
    strategy: str,
) -> str:
    """Implementation logic for load_context tool.

    Args:
        mgrs: Dictionary of managers
        task_description: Task description
        token_budget: Token budget (None for default)
        strategy: Loading strategy

    Returns:
        JSON string with loaded context results
    """
    (
        optimization_config,
        context_optimizer,
        metadata_index,
        fs_manager,
    ) = await _setup_optimization_managers(mgrs)

    if token_budget is None:
        token_budget = optimization_config.get_token_budget()

    files_content, files_metadata = await _read_all_files_for_context_loading(
        metadata_index, fs_manager
    )

    result = await context_optimizer.optimize_context(
        task_description=task_description,
        files_content=files_content,
        files_metadata=files_metadata,
        token_budget=token_budget,
        strategy=strategy,
    )

    return _format_load_context_result(task_description, token_budget, strategy, result)


async def _setup_optimization_managers(
    mgrs: dict[str, object],
) -> tuple[OptimizationConfig, ContextOptimizer, MetadataIndex, FileSystemManager]:
    """Setup managers for context optimization.

    Args:
        mgrs: Dictionary of managers

    Returns:
        Tuple of (optimization_config, context_optimizer, metadata_index, fs_manager)
    """
    optimization_config = await get_manager(
        mgrs, "optimization_config", OptimizationConfig
    )
    context_optimizer = await get_manager(mgrs, "context_optimizer", ContextOptimizer)
    metadata_index = cast(MetadataIndex, mgrs["index"])
    fs_manager = cast(FileSystemManager, mgrs["fs"])
    return optimization_config, context_optimizer, metadata_index, fs_manager


async def _read_all_files_for_context_loading(
    metadata_index: MetadataIndex,
    fs_manager: FileSystemManager,
) -> tuple[dict[str, str], dict[str, dict[str, object]]]:
    """Read all files and their metadata for context loading.

    Args:
        metadata_index: Metadata index manager
        fs_manager: File system manager

    Returns:
        Tuple of (files_content, files_metadata)
    """
    all_files = await metadata_index.list_all_files()
    files_content: dict[str, str] = {}
    files_metadata: dict[str, dict[str, object]] = {}

    for file_name in all_files:
        try:
            file_path = metadata_index.memory_bank_dir / file_name
            content, _ = await fs_manager.read_file(file_path)
            files_content[file_name] = content

            metadata = await metadata_index.get_file_metadata(file_name)
            if metadata:
                files_metadata[file_name] = metadata
        except FileNotFoundError:
            continue

    return files_content, files_metadata


def _format_load_context_result(
    task_description: str,
    token_budget: int,
    strategy: str,
    result: OptimizationResult,
) -> str:
    """Format load context result as JSON.

    Args:
        task_description: Task description
        token_budget: Token budget used
        strategy: Strategy used
        result: Context loading result

    Returns:
        JSON string with loaded context results
    """
    return json.dumps(
        {
            "status": "success",
            "task_description": task_description,
            "token_budget": token_budget,
            "strategy": strategy,
            "selected_files": result.selected_files,
            "selected_sections": result.selected_sections,
            "total_tokens": result.total_tokens,
            "utilization": round(result.utilization, 2),
            "excluded_files": result.excluded_files,
            "relevance_scores": result.metadata.get("relevance_scores", {}),
        },
        indent=2,
    )
