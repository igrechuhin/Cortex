"""
Phase 4: Progressive Loading Operations

This module contains the implementation logic for the load_progressive_context tool.
"""

import json
from typing import cast

from cortex.managers.manager_utils import get_manager
from cortex.optimization.optimization_config import OptimizationConfig
from cortex.optimization.progressive_loader import (
    LoadedContent,
    ProgressiveLoader,
)


async def load_progressive_context_impl(
    mgrs: dict[str, object],
    task_description: str,
    token_budget: int | None,
    loading_strategy: str,
) -> str:
    """Implementation logic for load_progressive_context tool.

    Args:
        mgrs: Dictionary of managers
        task_description: Task description
        token_budget: Token budget (None for default)
        loading_strategy: Loading strategy

    Returns:
        JSON string with progressive loading results
    """
    optimization_config, progressive_loader = await _get_progressive_managers(mgrs)

    if token_budget is None:
        token_budget = optimization_config.get_token_budget()

    loaded = await _load_by_strategy(
        progressive_loader,
        optimization_config,
        loading_strategy,
        task_description,
        token_budget,
    )
    if isinstance(loaded, str):
        return loaded

    loaded_data = _convert_loaded_items_to_dict(loaded)
    return _build_progressive_context_response(
        task_description, loading_strategy, token_budget, loaded_data
    )


async def _get_progressive_managers(
    mgrs: dict[str, object],
) -> tuple[OptimizationConfig, ProgressiveLoader]:
    """Get optimization config and progressive loader managers."""
    optimization_config = await get_manager(
        mgrs, "optimization_config", OptimizationConfig
    )
    progressive_loader = await get_manager(
        mgrs, "progressive_loader", ProgressiveLoader
    )
    return optimization_config, progressive_loader


async def _load_by_strategy(
    progressive_loader: ProgressiveLoader,
    optimization_config: OptimizationConfig,
    loading_strategy: str,
    task_description: str,
    token_budget: int,
) -> list[object] | str:
    """Load context using specified strategy.

    Args:
        progressive_loader: Progressive loader instance
        optimization_config: Optimization config
        loading_strategy: Loading strategy name
        task_description: Task description
        token_budget: Token budget

    Returns:
        Loaded items or error JSON string
    """
    if loading_strategy == "by_priority":
        return await _load_by_priority_strategy(
            progressive_loader, optimization_config, task_description, token_budget
        )
    elif loading_strategy == "by_dependencies":
        return await _load_by_dependencies_strategy(
            progressive_loader, optimization_config, token_budget
        )
    elif loading_strategy == "by_relevance":
        return await _load_by_relevance_strategy(
            progressive_loader, task_description, token_budget
        )
    else:
        return _build_invalid_strategy_error(loading_strategy)


async def _load_by_priority_strategy(
    progressive_loader: ProgressiveLoader,
    optimization_config: OptimizationConfig,
    task_description: str,
    token_budget: int,
) -> list[object]:
    """Load by priority strategy."""
    priority_order = optimization_config.get_priority_order()
    result = await progressive_loader.load_by_priority(
        task_description=task_description,
        token_budget=token_budget,
        priority_order=priority_order,
    )
    return cast(list[object], result)


async def _load_by_dependencies_strategy(
    progressive_loader: ProgressiveLoader,
    optimization_config: OptimizationConfig,
    token_budget: int,
) -> list[object]:
    """Load by dependencies strategy."""
    mandatory_files = optimization_config.get_mandatory_files()
    result = await progressive_loader.load_by_dependencies(
        entry_files=mandatory_files, token_budget=token_budget
    )
    return cast(list[object], result)


async def _load_by_relevance_strategy(
    progressive_loader: ProgressiveLoader,
    task_description: str,
    token_budget: int,
) -> list[object]:
    """Load by relevance strategy."""
    result = await progressive_loader.load_by_relevance(
        task_description=task_description, token_budget=token_budget
    )
    return cast(list[object], result)


def _build_invalid_strategy_error(loading_strategy: str) -> str:
    """Build error response for invalid strategy."""
    return json.dumps(
        {
            "status": "error",
            "error": (
                f"Invalid loading_strategy: {loading_strategy}. "
                "Use 'by_priority', 'by_dependencies', or 'by_relevance'."
            ),
        },
        indent=2,
    )


def _convert_loaded_items_to_dict(loaded: list[object]) -> list[dict[str, object]]:
    """Convert loaded items to dictionary format.

    Args:
        loaded: List of loaded items

    Returns:
        List of dictionaries
    """
    loaded_data: list[dict[str, object]] = []
    for item in loaded:
        # Cast item to LoadedContent to access attributes
        loaded_item = cast(LoadedContent, item)
        loaded_data.append(
            {
                "file_name": loaded_item.file_name,
                "tokens": loaded_item.tokens,
                "cumulative_tokens": loaded_item.cumulative_tokens,
                "priority": loaded_item.priority,
                "relevance_score": round(loaded_item.relevance_score, 3),
                "more_available": loaded_item.more_available,
            }
        )
    return loaded_data


def _build_progressive_context_response(
    task_description: str,
    loading_strategy: str,
    token_budget: int,
    loaded_data: list[dict[str, object]],
) -> str:
    """Build progressive context response.

    Args:
        task_description: Task description
        loading_strategy: Loading strategy
        token_budget: Token budget
        loaded_data: Loaded data

    Returns:
        JSON response string
    """
    return json.dumps(
        {
            "status": "success",
            "task_description": task_description,
            "loading_strategy": loading_strategy,
            "token_budget": token_budget,
            "files_loaded": len(loaded_data),
            "total_tokens": (
                loaded_data[-1]["cumulative_tokens"] if loaded_data else 0
            ),
            "loaded_files": loaded_data,
        },
        indent=2,
    )
