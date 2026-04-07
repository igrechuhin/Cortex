"""Shared Phase 4 optimization test runners (keeps test methods under length limits)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from cortex.managers.types import ManagersDict
from cortex.tools.optimization import get_relevance_scores, summarize_content
from cortex.tools.optimization.handlers import load_context_impl as _load_context_impl


async def run_concise_load_context_with_payload(
    mock_project_root: Path,
    mock_managers: object,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Run load_context_impl with concise format and a fixed JSON payload from the inner load."""
    mock_inner = AsyncMock(return_value=json.dumps(payload, indent=2))
    with (
        patch(
            "cortex.tools.optimization.handlers.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=mock_project_root,
        ),
        patch(
            "cortex.tools.optimization.get_managers",
            return_value=mock_managers,
        ),
        patch(
            "cortex.tools.optimization.handlers_load.load_context_impl",
            new=mock_inner,
        ),
    ):
        result_str = await _load_context_impl(
            task_description="Test task",
            token_budget=50000,
            response_format="concise",
        )
    return json.loads(result_str)


@contextmanager
def _full_workflow_patches(
    mock_project_root: Path,
    mock_managers: object,
    get_manager_helper: Any,
) -> Iterator[None]:
    with (
        patch(
            "cortex.tools.optimization.handlers.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=mock_project_root,
        ),
        patch(
            "cortex.tools.optimization.get_managers",
            return_value=mock_managers,
        ),
        patch(
            "cortex.tools.context.load_operations.get_manager",
            side_effect=get_manager_helper,
        ),
        patch(
            "cortex.tools.optimization.relevance_operations.get_manager",
            side_effect=get_manager_helper,
        ),
        patch(
            "cortex.tools.optimization.summarization_operations.get_manager",
            side_effect=get_manager_helper,
        ),
    ):
        yield


async def run_full_context_score_summarize_workflow(
    mock_project_root: Path,
    mock_managers: object,
    get_manager_helper: Any,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """load_context → get_relevance_scores → summarize_content with shared patches."""
    with _full_workflow_patches(mock_project_root, mock_managers, get_manager_helper):
        opt_data = json.loads(
            await _load_context_impl(task_description="Test task", token_budget=50000)
        )
        scores_data = json.loads(
            await get_relevance_scores(task_description="Test task")
        )
        summary_data = json.loads(await summarize_content())
    return opt_data, scores_data, summary_data


def _log_levels_from_mock(mock_log: AsyncMock) -> list[tuple[str, str]]:
    args_list = [c[0] for c in mock_log.call_args_list]
    return [(a[1], a[2]) for a in args_list]


@contextmanager
def _log_client_patches(mock_log: AsyncMock) -> Iterator[None]:
    with (
        patch("cortex.tools.optimization.handlers.log_client", mock_log),
        patch("cortex.core.context_logging.log_client", mock_log),
    ):
        yield


@contextmanager
def _load_context_root_managers_patches(
    mock_project_root: Path,
    mock_managers: object,
    get_manager_helper: Any,
) -> Iterator[None]:
    with (
        patch(
            "cortex.tools.optimization.handlers.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=mock_project_root,
        ),
        patch(
            "cortex.tools.optimization.get_managers",
            new=AsyncMock(return_value=mock_managers),
        ),
        patch(
            "cortex.tools.context.load_operations.get_manager",
            side_effect=get_manager_helper,
        ),
    ):
        yield


async def run_load_context_with_log_client_patched(
    mock_project_root: Path,
    mock_managers: object,
    mock_ctx: AsyncMock,
    mock_log: AsyncMock,
    get_manager_helper: Any,
) -> tuple[dict[str, Any], list[tuple[str, str]]]:
    """Run load_context_impl with ctx and return result + (level, message) pairs from log_client."""
    with (
        _log_client_patches(mock_log),
        _load_context_root_managers_patches(
            mock_project_root, mock_managers, get_manager_helper
        ),
    ):
        result_str = await _load_context_impl(
            task_description="Test task",
            token_budget=5000,
            ctx=mock_ctx,
        )
    result = json.loads(result_str)
    return result, _log_levels_from_mock(mock_log)


async def run_summarize_with_config_overrides(
    mock_project_root: Path,
    mock_managers: object,
    mock_optimization_config: MagicMock,
    base_get_manager: Any,
) -> dict[str, Any]:
    """summarize_content with optimization_config overrides from a MagicMock."""

    def get_manager_helper(mgrs: ManagersDict, key: str, _: object) -> object:
        if key == "optimization_config":
            return mock_optimization_config
        return base_get_manager(mgrs, key, _)

    with (
        patch(
            "cortex.tools.optimization.handlers.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=mock_project_root,
        ),
        patch(
            "cortex.tools.optimization.get_managers",
            return_value=mock_managers,
        ),
        patch(
            "cortex.tools.optimization.summarization_operations.get_manager",
            side_effect=get_manager_helper,
        ),
    ):
        result_str = await summarize_content(
            file_name="file1.md", target_reduction=None, strategy=None
        )
    return json.loads(result_str)


async def run_load_context_impl_with_zero_files_handling_mock(
    mock_project_root: Path,
    mock_managers: object,
    mock_result_json: str,
) -> dict[str, Any]:
    """load_context_impl when inner workflow returns JSON with zero files."""
    with (
        patch(
            "cortex.tools.optimization.handlers.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=mock_project_root,
        ),
        patch(
            "cortex.tools.optimization.get_managers",
            return_value=mock_managers,
        ),
        patch(
            "cortex.tools.optimization.handlers_load.load_context_with_error_handling",
            new_callable=AsyncMock,
            return_value=mock_result_json,
        ),
    ):
        result_str = await _load_context_impl(
            task_description="Implement a new feature",
            token_budget=10000,
        )
    return json.loads(result_str)
