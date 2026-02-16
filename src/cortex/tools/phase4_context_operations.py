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
from cortex.core.models import JsonValue, ModelDict
from cortex.core.session_logger import log_load_context_call
from cortex.core.token_counter import TokenCounter
from cortex.managers.manager_utils import get_manager
from cortex.managers.types import ManagersDict
from cortex.optimization.context_optimizer import ContextOptimizer
from cortex.optimization.optimization_config import OptimizationConfig
from cortex.optimization.optimization_strategies import OptimizationResult
from cortex.tools.phase4_hybrid_metadata_helpers import (
    calculate_always_loaded_tokens,
    filter_metadata_excluding_always_loaded,
    load_always_load_sections,
)
from cortex.tools.phase4_metadata_helpers import (
    build_files_map_from_metadata,
    calculate_metadata_relevance_scores,
)

logger = logging.getLogger(__name__)


def _calculate_effective_budget(
    token_budget: int | None, optimization_config: OptimizationConfig
) -> int:
    """Calculate effective token budget with max and reserve applied.

    Args:
        token_budget: Requested budget or None for default
        optimization_config: Optimization configuration

    Returns:
        Effective budget after applying max_budget and reserve_for_response
    """
    if token_budget is None:
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
    depth: str,
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

    if depth == "summary":
        files_content = _summarize_files_content(files_content, files_metadata)

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
    depth: str,
    result: OptimizationResult,
    project_root: Path | None,
) -> str:
    """Load context result and format with logging.

    Args:
        task_description: Task description
        effective_budget: Effective token budget
        strategy: Strategy used
        depth: Content depth level
        result: Optimization result
        project_root: Project root for logging

    Returns:
        JSON string with formatted result
    """
    if project_root is not None:
        _log_context_call(
            project_root, task_description, effective_budget, strategy, result
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
    )


async def _handle_full_or_summary_depth(
    context_optimizer: ContextOptimizer,
    metadata_index: MetadataIndex,
    fs_manager: FileSystemManager,
    task_description: str,
    effective_budget: int,
    strategy: str,
    depth: str,
    project_root: Path | None,
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

    Returns:
        JSON string with loaded context results
    """
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
        task_description, effective_budget, strategy, depth, result, project_root
    )


async def _dispatch_load_context_by_depth(
    context_optimizer: ContextOptimizer,
    metadata_index: MetadataIndex,
    fs_manager: FileSystemManager,
    task_description: str,
    effective_budget: int,
    strategy: str,
    depth: str,
    project_root: Path | None,
    optimization_config: OptimizationConfig,
) -> str:
    """Dispatch load_context based on depth parameter."""
    if depth == "metadata_only":
        return await _handle_metadata_only_depth(
            metadata_index,
            task_description,
            effective_budget,
            strategy,
            project_root,
            optimization_config,
            fs_manager,
        )
    return await _handle_full_or_summary_depth(
        context_optimizer,
        metadata_index,
        fs_manager,
        task_description,
        effective_budget,
        strategy,
        depth,
        project_root,
    )


async def load_context_impl(
    mgrs: ManagersDict,
    task_description: str,
    token_budget: int | None,
    strategy: str,
    depth: str = "full",
    project_root: Path | None = None,
) -> str:
    """Implementation logic for load_context tool."""
    (
        effective_budget,
        optimization_config,
        context_optimizer,
        metadata_index,
        fs_manager,
    ) = await _prepare_context_loading(mgrs, token_budget)
    return await _dispatch_load_context_by_depth(
        context_optimizer,
        metadata_index,
        fs_manager,
        task_description,
        effective_budget,
        strategy,
        depth,
        project_root,
        optimization_config,
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
) -> None:
    """Log load_context call for effectiveness analysis.

    Args:
        project_root: Project root path
        task_description: Task description
        token_budget: Token budget used
        strategy: Strategy used
        result: Context loading result
    """
    raw_scores: JsonValue = result.metadata.get("relevance_scores", {})
    # Ensure relevance_scores is dict[str, float]
    scores: dict[str, float] = {}
    if isinstance(raw_scores, dict):
        typed_scores = cast(ModelDict, raw_scores)
        for file_name, score_value in typed_scores.items():
            if isinstance(score_value, (int, float)):
                scores[file_name] = float(score_value)

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
    files_map: list[dict[str, object]],
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

    def get_tokens_for_sum(x: dict[str, object]) -> int:
        tokens_raw = x.get("total_tokens", 0)
        return int(tokens_raw) if isinstance(tokens_raw, (int, str)) else 0

    metadata_tokens = sum(get_tokens_for_sum(f) for f in files_map[:10])
    total_tokens = metadata_tokens + always_loaded_tokens

    response_data = {
        "status": "success",
        "task_description": task_description,
        "token_budget": token_budget,
        "strategy": strategy,
        "depth": "metadata_only",
        "files": files_map,
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
) -> tuple[dict[str, ModelDict], dict[str, float]]:
    """Prepare files metadata and calculate relevance scores."""
    files_metadata = await _collect_files_metadata(metadata_index)
    relevance_scores = calculate_metadata_relevance_scores(
        task_description, files_metadata
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
) -> tuple[list[dict[str, object]], int]:
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
) -> tuple[dict[str, str], int, dict[str, ModelDict], dict[str, float]]:
    """Load always-loaded content and prepare metadata."""
    always_loaded_content, always_loaded_tokens = (
        await _load_and_calculate_always_loaded(
            always_load_sections, metadata_index, fs_manager
        )
    )
    files_metadata, relevance_scores = await _prepare_metadata_and_relevance(
        metadata_index, task_description
    )
    return always_loaded_content, always_loaded_tokens, files_metadata, relevance_scores


async def _prepare_hybrid_metadata_context(
    metadata_index: MetadataIndex,
    task_description: str,
    always_load_sections: dict[str, list[str]],
    fs_manager: FileSystemManager,
) -> tuple[
    dict[str, str],
    int,
    dict[str, ModelDict],
    dict[str, float],
    list[dict[str, object]],
    int,
]:
    """Prepare hybrid metadata context."""
    always_loaded_content, always_loaded_tokens, files_metadata, relevance_scores = (
        await _load_always_loaded_and_metadata(
            always_load_sections, metadata_index, fs_manager, task_description
        )
    )
    files_map, total_tokens_available = _build_filtered_files_map(
        files_metadata, relevance_scores, always_load_sections
    )
    return _build_hybrid_context_result(
        always_loaded_content,
        always_loaded_tokens,
        files_metadata,
        relevance_scores,
        files_map,
        total_tokens_available,
    )


def _build_hybrid_context_result(
    always_loaded_content: dict[str, str],
    always_loaded_tokens: int,
    files_metadata: dict[str, ModelDict],
    relevance_scores: dict[str, float],
    files_map: list[dict[str, object]],
    total_tokens_available: int,
) -> tuple[
    dict[str, str],
    int,
    dict[str, ModelDict],
    dict[str, float],
    list[dict[str, object]],
    int,
]:
    """Build hybrid context result tuple."""
    return (
        always_loaded_content,
        always_loaded_tokens,
        files_metadata,
        relevance_scores,
        files_map,
        total_tokens_available,
    )


async def _load_context_metadata_only(
    metadata_index: MetadataIndex,
    task_description: str,
    token_budget: int,
    strategy: str,
    project_root: Path | None,
    optimization_config: OptimizationConfig,
    fs_manager: FileSystemManager,
) -> str:
    """Load context map with hybrid retrieval (always-load sections + metadata).

    Args:
        metadata_index: Metadata index manager
        task_description: Task description
        token_budget: Token budget (used for logging)
        strategy: Strategy used
        project_root: Project root for logging
        optimization_config: Optimization configuration
        fs_manager: File system manager

    Returns:
        JSON string with context map (metadata only) plus always-loaded sections
    """
    always_load_sections = optimization_config.get_always_load_sections()
    (
        always_loaded_content,
        always_loaded_tokens,
        _,
        _,
        files_map,
        total_tokens_available,
    ) = await _prepare_hybrid_metadata_context(
        metadata_index, task_description, always_load_sections, fs_manager
    )
    return _build_hybrid_metadata_response(
        task_description,
        token_budget,
        strategy,
        files_map,
        total_tokens_available,
        always_loaded_content,
        always_loaded_tokens,
    )


def _summarize_files_content(
    files_content: dict[str, str], files_metadata: dict[str, ModelDict]
) -> dict[str, str]:
    """Summarize file contents to first paragraph + section headings.

    Args:
        files_content: Full file contents
        files_metadata: File metadata including sections

    Returns:
        Dictionary with summarized content (first paragraph + headings)
    """
    summarized: dict[str, str] = {}

    for file_name, content in files_content.items():
        lines = content.split("\n")
        summary_parts: list[str] = []

        # Extract first paragraph (until first empty line or heading)
        first_paragraph_lines: list[str] = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                if first_paragraph_lines:
                    break
                continue
            if stripped.startswith("#"):
                break
            first_paragraph_lines.append(line)

        if first_paragraph_lines:
            summary_parts.append("\n".join(first_paragraph_lines))

        # Add section headings
        metadata = files_metadata.get(file_name, {})
        sections_list = metadata.get("sections", [])
        if isinstance(sections_list, list) and sections_list:
            summary_parts.append("\n\n## Sections:")
            for section in sections_list[:10]:  # Limit to first 10 sections
                if isinstance(section, dict):
                    heading = str(section.get("heading", ""))
                    if heading:
                        summary_parts.append(heading)

        summarized[file_name] = "\n".join(summary_parts) if summary_parts else content

    return summarized


def _format_load_context_result(
    task_description: str,
    token_budget: int,
    strategy: str,
    result: OptimizationResult,
    depth: str = "full",
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
    response_data = {
        "status": "success",
        "task_description": task_description,
        "token_budget": token_budget,
        "strategy": strategy,
        "depth": depth,
        "selected_files": result.selected_files,
        "selected_sections": result.selected_sections,
        "total_tokens": result.total_tokens,
        "utilization": round(result.utilization, 2),
        "excluded_files": result.excluded_files,
        "relevance_scores": result.metadata.get("relevance_scores", {}),
    }

    # For metadata_only, include files map if available
    if depth == "metadata_only" and "files" in result.metadata:
        response_data["files"] = result.metadata["files"]

    return json.dumps(response_data, indent=2)
