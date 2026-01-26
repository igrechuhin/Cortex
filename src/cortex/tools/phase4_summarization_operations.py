"""
Phase 4: Summarization Operations

This module contains the implementation logic for the summarize_content tool.
"""

import json

from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.managers.manager_utils import get_manager
from cortex.managers.types import ManagersDict
from cortex.optimization.models import SummarizationResultModel
from cortex.optimization.summarization_engine import SummarizationEngine


async def summarize_content_impl(
    mgrs: ManagersDict,
    file_name: str | None,
    target_reduction: float,
    strategy: str,
) -> str:
    """Implementation logic for summarize_content tool.

    Args:
        mgrs: Dictionary of managers
        file_name: File name to summarize (None for all)
        target_reduction: Target reduction percentage
        strategy: Summarization strategy

    Returns:
        JSON string with summarization results
    """
    validation_error = _validate_summarize_inputs(target_reduction, strategy)
    if validation_error:
        return validation_error

    summarization_engine = await get_manager(
        mgrs, "summarization_engine", SummarizationEngine
    )
    metadata_index: MetadataIndex = mgrs.index
    fs_manager: FileSystemManager = mgrs.fs

    files_to_summarize = await _get_files_to_summarize(file_name, metadata_index)
    results = await _summarize_files(
        files_to_summarize,
        summarization_engine,
        metadata_index,
        fs_manager,
        target_reduction,
        strategy,
    )

    return _build_summarize_response(results, strategy, target_reduction)


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
                "error": f"Invalid strategy: {strategy}. Use {', '.join(valid_strategies)}.",
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
