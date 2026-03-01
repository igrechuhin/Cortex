"""
Phase 4: Summarization Operations

This module contains the implementation logic for the summarize_content tool.
"""

import json

from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.managers.manager_utils import get_manager
from cortex.managers.types import ManagersDict
from cortex.optimization.config import OptimizationConfig
from cortex.optimization.models import SummarizationResultModel
from cortex.optimization.summarization_engine import SummarizationEngine


async def _check_summarization_enabled(
    optimization_config: OptimizationConfig,
) -> str | None:
    """Check if summarization is enabled. Returns error JSON or None."""
    if not optimization_config.is_summarization_enabled():
        return json.dumps(
            {
                "status": "error",
                "error": "Summarization is disabled in optimization configuration",
            },
            indent=2,
        )
    return None


def _resolve_summarization_defaults(
    optimization_config: OptimizationConfig,
    target_reduction: float | None,
    strategy: str | None,
) -> tuple[float, str]:
    """Resolve summarization defaults from config when args are None."""
    effective_target_reduction = (
        target_reduction
        if target_reduction is not None
        else optimization_config.get_summarization_target_reduction()
    )
    effective_strategy = (
        strategy
        if strategy is not None
        else optimization_config.get_summarization_strategy()
    )
    return effective_target_reduction, effective_strategy


async def _get_summarization_managers(
    mgrs: ManagersDict,
) -> tuple[SummarizationEngine, MetadataIndex, FileSystemManager]:
    """Get summarization-related managers."""
    summarization_engine = await get_manager(
        mgrs, "summarization_engine", SummarizationEngine
    )
    metadata_index: MetadataIndex = mgrs.index
    fs_manager: FileSystemManager = mgrs.fs
    return summarization_engine, metadata_index, fs_manager


async def _execute_summarization(
    mgrs: ManagersDict,
    file_name: str | None,
    effective_target_reduction: float,
    effective_strategy: str,
) -> str:
    """Execute summarization with resolved parameters."""
    (
        summarization_engine,
        metadata_index,
        fs_manager,
    ) = await _get_summarization_managers(mgrs)

    files_to_summarize = await _get_files_to_summarize(file_name, metadata_index)
    results = await _summarize_files(
        files_to_summarize,
        summarization_engine,
        metadata_index,
        fs_manager,
        effective_target_reduction,
        effective_strategy,
    )

    return _build_summarize_response(
        results, effective_strategy, effective_target_reduction
    )


async def summarize_content_impl(
    mgrs: ManagersDict,
    file_name: str | None,
    target_reduction: float | None,
    strategy: str | None,
) -> str:
    """Implementation logic for summarize_content tool.

    Args:
        mgrs: Dictionary of managers
        file_name: File name to summarize (None for all)
        target_reduction: Target reduction percentage (None to use config default)
        strategy: Summarization strategy (None to use config default)

    Returns:
        JSON string with summarization results
    """
    optimization_config = await get_manager(
        mgrs, "optimization_config", OptimizationConfig
    )

    enabled_error = await _check_summarization_enabled(optimization_config)
    if enabled_error:
        return enabled_error

    effective_target_reduction, effective_strategy = _resolve_summarization_defaults(
        optimization_config, target_reduction, strategy
    )

    validation_error = _validate_summarize_inputs(
        effective_target_reduction, effective_strategy
    )
    if validation_error:
        return validation_error

    return await _execute_summarization(
        mgrs, file_name, effective_target_reduction, effective_strategy
    )


def _validate_summarize_inputs(target_reduction: float, strategy: str) -> str | None:
    """Validate summarize_content inputs. Returns error JSON string or None."""
    if not 0 < target_reduction < 1:
        return json.dumps(
            {
                "status": "error",
                "error": "target_reduction must be between 0 and 1",
            },
            indent=2,
        )

    valid_strategies = ["extract_key_sections", "compress_verbose", "headers_only"]
    if strategy not in valid_strategies:
        return json.dumps(
            {
                "status": "error",
                "error": (
                    f"Invalid strategy: {strategy}. Use {', '.join(valid_strategies)}."
                ),
            },
            indent=2,
        )

    return None


async def _get_files_to_summarize(
    file_name: str | None, metadata_index: MetadataIndex
) -> list[str]:
    """Get list of files to summarize."""
    if file_name:
        return [file_name]
    return await metadata_index.list_all_files()


async def _summarize_files(
    files_to_summarize: list[str],
    summarization_engine: SummarizationEngine,
    metadata_index: MetadataIndex,
    fs_manager: FileSystemManager,
    target_reduction: float,
    strategy: str,
) -> list[SummarizationResultModel]:
    """Summarize all files and return results."""
    results: list[SummarizationResultModel] = []

    for fname in files_to_summarize:
        try:
            file_path = metadata_index.memory_bank_dir / fname
            content, _ = await fs_manager.read_file(file_path)

            summary_result = await summarization_engine.summarize_file(
                file_name=fname,
                content=content,
                target_reduction=target_reduction,
                strategy=strategy,
            )

            results.append(SummarizationResultModel.model_validate(summary_result))

        except FileNotFoundError:
            continue

    return results


def _build_summarize_response(
    results: list[SummarizationResultModel], strategy: str, target_reduction: float
) -> str:
    """Build final JSON response with totals."""
    total_original = sum(r.original_tokens for r in results)
    total_summarized = sum(r.summary_tokens for r in results)
    total_reduction = (
        (total_original - total_summarized) / total_original
        if total_original > 0
        else 0.0
    )

    return json.dumps(
        {
            "status": "success",
            "strategy": strategy,
            "target_reduction": target_reduction,
            "files_summarized": len(results),
            "total_original_tokens": total_original,
            "total_summarized_tokens": total_summarized,
            "total_reduction": round(total_reduction, 2),
            "results": [r.model_dump() for r in results],
        },
        indent=2,
    )
