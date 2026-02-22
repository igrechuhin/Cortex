"""
Phase 4: Context Loading Operations

This module contains the implementation logic for the load_context tool.
"""

import json
import logging
from pathlib import Path
from typing import cast

from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.models import ContextDepth, JsonValue, ModelDict
from cortex.core.session_logger import log_load_context_call
from cortex.core.token_counter import TokenCounter
from cortex.managers.manager_utils import get_manager
from cortex.managers.types import ManagersDict
from cortex.optimization.agent_roles import AgentRole
from cortex.optimization.context_optimizer import ContextOptimizer
from cortex.optimization.optimization_config import OptimizationConfig
from cortex.optimization.optimization_strategies import OptimizationResult
from cortex.tools.context_models import FileMapEntry
from cortex.tools.phase4_hybrid_metadata_helpers import (
    calculate_always_loaded_tokens,
    filter_metadata_excluding_always_loaded,
    load_always_load_sections,
)
from cortex.tools.phase4_metadata_helpers import (
    build_files_map_from_metadata,
    calculate_metadata_relevance_scores,
    log_metadata_context_call,
    summarize_files_content,
)

logger = logging.getLogger(__name__)


def _calculate_effective_budget(
    token_budget: int | None, optimization_config: OptimizationConfig
) -> int:
    """Calculate effective token budget with max and reserve applied.

    Args:
        token_budget: Requested budget, None for default, or 0 (treated as None).
        optimization_config: Optimization configuration

    Returns:
        Effective budget after applying max_budget and reserve_for_response
    """
    if token_budget is None or token_budget == 0:
        token_budget = optimization_config.get_token_budget()
    max_budget = optimization_config.get_max_token_budget()
    reserve = optimization_config.get_reserve_for_response()
    token_budget = min(token_budget, max_budget)
    return max(token_budget - reserve, 0)


async def _load_context_with_content(
    context_optimizer: ContextOptimizer,
    metadata_index: MetadataIndex,
    fs_manager: FileSystemManager,
    task_description: str,
    effective_budget: int,
    strategy: str,
    depth: ContextDepth,
) -> OptimizationResult:
    """Load context with file content (summary or full).

    Args:
        context_optimizer: Context optimizer instance
        metadata_index: Metadata index instance
        fs_manager: File system manager instance
        task_description: Task description
        effective_budget: Effective token budget
        strategy: Loading strategy
        depth: Content depth level (summary or full)

    Returns:
        Context optimization result
    """
    files_content, files_metadata = await _read_all_files_for_context_loading(
        metadata_index, fs_manager
    )

    if depth == ContextDepth.SUMMARY:
        files_content = summarize_files_content(files_content, files_metadata)

    return await context_optimizer.optimize_context(
        task_description=task_description,
        files_content=files_content,
        files_metadata=files_metadata,
        token_budget=effective_budget,
        strategy=strategy,
    )


async def _load_and_format_context_result(
    task_description: str,
    effective_budget: int,
    strategy: str,
    depth: ContextDepth,
    result: OptimizationResult,
    project_root: Path | None,
    agent_role: AgentRole | None = None,
) -> str:
    """Load context result and format with logging.

    Args:
        task_description: Task description
        effective_budget: Effective token budget
        strategy: Strategy used
        depth: Content depth level
        result: Optimization result
        project_root: Project root for logging
        agent_role: Optional agent role for role-aware logging

    Returns:
        JSON string with formatted result
    """
    if project_root is not None:
        _log_context_call(
            project_root,
            task_description,
            effective_budget,
            strategy,
            result,
            agent_role,
        )

    return _format_load_context_result(
        task_description, effective_budget, strategy, result, depth=depth
    )


async def _prepare_context_loading(
    mgrs: ManagersDict, token_budget: int | None
) -> tuple[int, OptimizationConfig, ContextOptimizer, MetadataIndex, FileSystemManager]:
    """Prepare managers and calculate effective budget.

    Args:
        mgrs: Dictionary of managers
        token_budget: Token budget (None for default)

    Returns:
        Tuple of (effective_budget, optimization_config, context_optimizer, metadata_index, fs_manager)
    """
    (
        optimization_config,
        context_optimizer,
        metadata_index,
        fs_manager,
    ) = await _setup_optimization_managers(mgrs)
    effective_budget = _calculate_effective_budget(token_budget, optimization_config)
    return (
        effective_budget,
        optimization_config,
        context_optimizer,
        metadata_index,
        fs_manager,
    )


async def _handle_metadata_only_depth(
    metadata_index: MetadataIndex,
    task_description: str,
    effective_budget: int,
    strategy: str,
    project_root: Path | None,
    optimization_config: OptimizationConfig,
    fs_manager: FileSystemManager,
    agent_role: AgentRole | None = None,
) -> str:
    """Handle metadata_only depth with hybrid retrieval strategy.

    Args:
        metadata_index: Metadata index manager
        task_description: Task description
        effective_budget: Effective token budget
        strategy: Loading strategy
        project_root: Project root for logging
        optimization_config: Optimization configuration
        fs_manager: File system manager
        agent_role: Optional agent role for role-based context selection

    Returns:
        JSON string with metadata-only context map
    """
    return await _load_context_metadata_only(
        metadata_index,
        task_description,
        effective_budget,
        strategy,
        project_root,
        optimization_config,
        fs_manager,
        agent_role,
    )


async def _handle_full_or_summary_depth(
    context_optimizer: ContextOptimizer,
    metadata_index: MetadataIndex,
    fs_manager: FileSystemManager,
    task_description: str,
    effective_budget: int,
    strategy: str,
    depth: ContextDepth,
    project_root: Path | None,
    agent_role: AgentRole | None = None,
) -> str:
    """Handle full or summary depth loading.

    Args:
        context_optimizer: Context optimizer instance
        metadata_index: Metadata index instance
        fs_manager: File system manager instance
        task_description: Task description
        effective_budget: Effective token budget
        strategy: Loading strategy
        depth: Content depth level (summary or full)
        project_root: Project root for logging
        agent_role: Optional agent role for role-based context selection

    Returns:
        JSON string with loaded context results
    """
    # Note: agent_role is accepted here for API consistency but not yet
    # used in full/summary depth loading. Role-based selection is currently
    # only implemented for metadata_only depth.
    result = await _load_context_with_content(
        context_optimizer,
        metadata_index,
        fs_manager,
        task_description,
        effective_budget,
        strategy,
        depth,
    )
    return await _load_and_format_context_result(
        task_description,
        effective_budget,
        strategy,
        depth,
        result,
        project_root,
        agent_role,
    )


async def load_context_impl(
    mgrs: ManagersDict,
    task_description: str,
    token_budget: int | None,
    strategy: str,
    depth: ContextDepth | str = ContextDepth.FULL,
    project_root: Path | None = None,
    agent_role: AgentRole | None = None,
) -> str:
    """Implementation logic for load_context tool.

    Args:
        mgrs: Dictionary of managers
        task_description: Task description
        token_budget: Token budget
        strategy: Loading strategy
        depth: Content depth level (ContextDepth enum or string for backward compatibility)
        project_root: Project root path
        agent_role: Optional agent role for role-based context selection

    Returns:
        JSON string with loaded context
    """
    # Normalize string input to ContextDepth enum for backward compatibility
    if not isinstance(depth, ContextDepth):
        try:
            depth = ContextDepth(depth)
        except ValueError:
            # Invalid string value, default to FULL
            depth = ContextDepth.FULL

    loading_data = await _prepare_context_loading(mgrs, token_budget)
    return await _dispatch_by_depth(
        loading_data, task_description, strategy, depth, project_root, agent_role
    )


async def _dispatch_by_depth(
    loading_data: tuple[
        int, OptimizationConfig, ContextOptimizer, MetadataIndex, FileSystemManager
    ],
    task_description: str,
    strategy: str,
    depth: ContextDepth,
    project_root: Path | None,
    agent_role: AgentRole | None,
) -> str:
    """Dispatch context loading based on depth parameter."""
    components = _unpack_loading_data(loading_data)
    if depth == ContextDepth.METADATA_ONLY:
        return await _dispatch_metadata_only_loading(
            components, task_description, strategy, project_root, agent_role
        )
    return await _dispatch_full_or_summary_loading(
        components, task_description, strategy, depth, project_root, agent_role
    )


def _unpack_loading_data(
    loading_data: tuple[
        int, OptimizationConfig, ContextOptimizer, MetadataIndex, FileSystemManager
    ],
) -> tuple[int, OptimizationConfig, ContextOptimizer, MetadataIndex, FileSystemManager]:
    """Unpack loading data tuple."""
    return loading_data


async def _dispatch_metadata_only_loading(
    components: tuple[
        int, OptimizationConfig, ContextOptimizer, MetadataIndex, FileSystemManager
    ],
    task_description: str,
    strategy: str,
    project_root: Path | None,
    agent_role: AgentRole | None,
) -> str:
    """Dispatch metadata_only depth loading."""
    effective_budget, optimization_config, _, metadata_index, fs_manager = components
    return await _handle_metadata_only_depth(
        metadata_index,
        task_description,
        effective_budget,
        strategy,
        project_root,
        optimization_config,
        fs_manager,
        agent_role,
    )


async def _dispatch_full_or_summary_loading(
    components: tuple[
        int, OptimizationConfig, ContextOptimizer, MetadataIndex, FileSystemManager
    ],
    task_description: str,
    strategy: str,
    depth: ContextDepth,
    project_root: Path | None,
    agent_role: AgentRole | None,
) -> str:
    """Dispatch full or summary depth loading."""
    effective_budget, _, context_optimizer, metadata_index, fs_manager = components
    return await _handle_full_or_summary_depth(
        context_optimizer,
        metadata_index,
        fs_manager,
        task_description,
        effective_budget,
        strategy,
        depth,
        project_root,
        agent_role,
    )


async def _setup_optimization_managers(
    mgrs: ManagersDict,
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
    metadata_index: MetadataIndex = mgrs.index
    fs_manager: FileSystemManager = mgrs.fs
    return optimization_config, context_optimizer, metadata_index, fs_manager


async def _read_all_files_for_context_loading(
    metadata_index: MetadataIndex,
    fs_manager: FileSystemManager,
) -> tuple[dict[str, str], dict[str, ModelDict]]:
    """Read all files and their metadata for context loading.

    Args:
        metadata_index: Metadata index manager
        fs_manager: File system manager

    Returns:
        Tuple of (files_content, files_metadata)
    """
    all_files = await metadata_index.list_all_files()
    files_content: dict[str, str] = {}
    files_metadata: dict[str, ModelDict] = {}

    for file_name in all_files:
        file_path = metadata_index.memory_bank_dir / file_name
        if not file_path.exists():
            logger.warning("Skipping stale index entry: %s", file_name)
            continue
        try:
            content, _ = await fs_manager.read_file(file_path)
            files_content[file_name] = content

            metadata_raw = await metadata_index.get_file_metadata(file_name)
            if metadata_raw:
                files_metadata[file_name] = cast(ModelDict, metadata_raw)
        except FileNotFoundError:
            continue

    return files_content, files_metadata


def _log_context_call(
    project_root: Path,
    task_description: str,
    token_budget: int,
    strategy: str,
    result: OptimizationResult,
    agent_role: AgentRole | None = None,
) -> None:
    """Log load_context call for effectiveness analysis.

    Args:
        project_root: Project root path
        task_description: Task description
        token_budget: Token budget used
        strategy: Strategy used
        result: Context loading result
        agent_role: Optional agent role for role-aware logging
    """
    raw_scores: JsonValue = result.metadata.get("relevance_scores", {})
    # Ensure relevance_scores is dict[str, float]
    scores: dict[str, float] = {}
    if isinstance(raw_scores, dict):
        typed_scores = cast(ModelDict, raw_scores)
        for file_name, score_value in typed_scores.items():
            if isinstance(score_value, (int, float)):
                scores[file_name] = float(score_value)

    # Convert AgentRole enum to string value for logging
    role_str: str | None = None
    if agent_role is not None:
        role_str = agent_role.value

    log_load_context_call(
        project_root=project_root,
        task_description=task_description,
        token_budget=token_budget,
        strategy=strategy,
        selected_files=result.selected_files,
        selected_sections=result.selected_sections,
        total_tokens=result.total_tokens,
        utilization=result.utilization,
        excluded_files=result.excluded_files,
        relevance_scores=scores,
        role=role_str,
    )


async def _collect_files_metadata(
    metadata_index: MetadataIndex,
) -> dict[str, ModelDict]:
    """Collect metadata for all files.

    Args:
        metadata_index: Metadata index manager

    Returns:
        Dictionary mapping file names to metadata
    """
    all_files = await metadata_index.list_all_files()
    files_metadata: dict[str, ModelDict] = {}

    for file_name in all_files:
        metadata_raw = await metadata_index.get_file_metadata(file_name)
        if metadata_raw:
            files_metadata[file_name] = cast(ModelDict, metadata_raw)

    return files_metadata


def _build_hybrid_metadata_response(
    task_description: str,
    token_budget: int,
    strategy: str,
    files_map: list[FileMapEntry],
    total_tokens_available: int,
    always_loaded_content: dict[str, str],
    always_loaded_tokens: int,
) -> str:
    """Build hybrid metadata response with always-loaded sections.

    Args:
        task_description: Task description
        token_budget: Token budget used
        strategy: Strategy used
        files_map: Files map with metadata (excluding always-loaded files)
        total_tokens_available: Total tokens available
        always_loaded_content: Always-loaded file content (full or sections)
        always_loaded_tokens: Token count for always-loaded content

    Returns:
        JSON string with hybrid response (metadata + always-loaded sections)
    """
    metadata_tokens = sum(f.total_tokens for f in files_map[:10])
    total_tokens = metadata_tokens + always_loaded_tokens

    response_data = {
        "status": "success",
        "task_description": task_description,
        "token_budget": token_budget,
        "strategy": strategy,
        "depth": ContextDepth.METADATA_ONLY.value,
        "files": [e.model_dump() for e in files_map],
        "total_files": len(files_map),
        "total_tokens_available": total_tokens_available,
        "always_loaded": always_loaded_content,
        "always_loaded_tokens": always_loaded_tokens,
        "total_tokens": total_tokens,
        "utilization": (
            round(total_tokens / token_budget, 2) if token_budget > 0 else 0.0
        ),
    }

    return json.dumps(response_data, indent=2)


async def _prepare_metadata_and_relevance(
    metadata_index: MetadataIndex,
    task_description: str,
    agent_role: AgentRole | None = None,
) -> tuple[dict[str, ModelDict], dict[str, float]]:
    """Prepare files metadata and calculate relevance scores.

    Args:
        metadata_index: Metadata index
        task_description: Task description
        agent_role: Optional agent role for role-based scoring

    Returns:
        Tuple of files metadata and relevance scores
    """
    files_metadata = await _collect_files_metadata(metadata_index)
    relevance_scores = calculate_metadata_relevance_scores(
        task_description, files_metadata, agent_role
    )
    return files_metadata, relevance_scores


async def _load_and_calculate_always_loaded(
    always_load_sections: dict[str, list[str]],
    metadata_index: MetadataIndex,
    fs_manager: FileSystemManager,
) -> tuple[dict[str, str], int]:
    """Load always-loaded sections and calculate tokens."""
    token_counter = TokenCounter()
    always_loaded_content = await load_always_load_sections(
        always_load_sections, metadata_index, fs_manager, token_counter
    )
    always_loaded_tokens = calculate_always_loaded_tokens(
        always_loaded_content, token_counter
    )
    return always_loaded_content, always_loaded_tokens


def _build_filtered_files_map(
    files_metadata: dict[str, ModelDict],
    relevance_scores: dict[str, float],
    always_load_sections: dict[str, list[str]],
) -> tuple[list[FileMapEntry], int]:
    """Build files map from filtered metadata."""
    filtered_metadata = filter_metadata_excluding_always_loaded(
        files_metadata, always_load_sections
    )
    return build_files_map_from_metadata(filtered_metadata, relevance_scores)


async def _load_always_loaded_and_metadata(
    always_load_sections: dict[str, list[str]],
    metadata_index: MetadataIndex,
    fs_manager: FileSystemManager,
    task_description: str,
    agent_role: AgentRole | None = None,
) -> tuple[dict[str, str], int, dict[str, ModelDict], dict[str, float]]:
    """Load always-loaded content and prepare metadata with role-based scoring."""
    (
        always_loaded_content,
        always_loaded_tokens,
    ) = await _load_and_calculate_always_loaded(
        always_load_sections, metadata_index, fs_manager
    )
    files_metadata, relevance_scores = await _prepare_metadata_and_relevance(
        metadata_index, task_description, agent_role
    )
    return always_loaded_content, always_loaded_tokens, files_metadata, relevance_scores


async def _prepare_hybrid_metadata_context(
    metadata_index: MetadataIndex,
    task_description: str,
    always_load_sections: dict[str, list[str]],
    fs_manager: FileSystemManager,
    agent_role: AgentRole | None = None,
) -> tuple[
    dict[str, str],
    int,
    dict[str, ModelDict],
    dict[str, float],
    list[FileMapEntry],
    int,
]:
    """Prepare hybrid metadata context with role-based scoring."""
    loaded_data = await _load_always_loaded_and_metadata(
        always_load_sections, metadata_index, fs_manager, task_description, agent_role
    )
    return _finalize_hybrid_metadata_context(loaded_data, always_load_sections)


def _finalize_hybrid_metadata_context(
    loaded_data: tuple[dict[str, str], int, dict[str, ModelDict], dict[str, float]],
    always_load_sections: dict[str, list[str]],
) -> tuple[
    dict[str, str],
    int,
    dict[str, ModelDict],
    dict[str, float],
    list[FileMapEntry],
    int,
]:
    """Finalize hybrid metadata context from loaded data."""
    always_loaded_content, always_loaded_tokens, files_metadata, relevance_scores = (
        loaded_data
    )
    files_map, total_tokens_available = _build_filtered_files_map(
        files_metadata, relevance_scores, always_load_sections
    )
    return (
        always_loaded_content,
        always_loaded_tokens,
        files_metadata,
        relevance_scores,
        files_map,
        total_tokens_available,
    )


def _emit_metadata_only_log(
    project_root: Path,
    task_description: str,
    token_budget: int,
    strategy: str,
    files_map: list[FileMapEntry],
    always_loaded_content: dict[str, str],
    always_load_sections: dict[str, list[str]],
    files_metadata: dict[str, ModelDict],
    always_loaded_tokens: int,
    relevance_scores: dict[str, float],
    agent_role: AgentRole | None,
) -> None:
    """Emit metadata-only context load log."""
    log_metadata_context_call(
        project_root,
        task_description,
        token_budget,
        strategy,
        files_map,
        always_loaded_content,
        always_load_sections,
        files_metadata,
        always_loaded_tokens,
        relevance_scores,
        agent_role,
    )


async def _load_context_metadata_only(
    metadata_index: MetadataIndex,
    task_description: str,
    token_budget: int,
    strategy: str,
    project_root: Path | None,
    optimization_config: OptimizationConfig,
    fs_manager: FileSystemManager,
    agent_role: AgentRole | None = None,
) -> str:
    """Load context map with hybrid retrieval and role-based scoring."""
    always_load_sections = optimization_config.get_always_load_sections()
    (
        always_loaded_content,
        always_loaded_tokens,
        files_metadata,
        relevance_scores,
        files_map,
        total_tokens_available,
    ) = await _prepare_hybrid_metadata_context(
        metadata_index, task_description, always_load_sections, fs_manager, agent_role
    )
    if project_root is not None:
        # fmt: off
        _emit_metadata_only_log(project_root, task_description, token_budget, strategy, files_map, always_loaded_content, always_load_sections, files_metadata, always_loaded_tokens, relevance_scores, agent_role)
        # fmt: on
    # fmt: off
    return _build_hybrid_metadata_response(task_description, token_budget, strategy, files_map, total_tokens_available, always_loaded_content, always_loaded_tokens)


def _format_load_context_result(
    task_description: str,
    token_budget: int,
    strategy: str,
    result: OptimizationResult,
    depth: ContextDepth = ContextDepth.FULL,
) -> str:
    """Format load context result as JSON.

    Args:
        task_description: Task description
        token_budget: Token budget used
        strategy: Strategy used
        result: Context loading result
        depth: Content depth level used

    Returns:
        JSON string with loaded context results
    """
    # Serialize enum to string value for JSON output
    depth_str = depth.value
    response_data = {
        "status": "success",
        "task_description": task_description,
        "token_budget": token_budget,
        "strategy": strategy,
        "depth": depth_str,
        "selected_files": result.selected_files,
        "selected_sections": result.selected_sections,
        "total_tokens": result.total_tokens,
        "utilization": round(result.utilization, 2),
        "excluded_files": result.excluded_files,
        "relevance_scores": result.metadata.get("relevance_scores", {}),
    }

    # For metadata_only, include files map if available
    if depth == ContextDepth.METADATA_ONLY and "files" in result.metadata:
        response_data["files"] = result.metadata["files"]

    return json.dumps(response_data, indent=2)
