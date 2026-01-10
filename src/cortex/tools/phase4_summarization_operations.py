"""
Phase 4: Summarization Operations

This module contains the implementation logic for the summarize_content tool.
"""

import json
from typing import cast

from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.managers.manager_utils import get_manager
from cortex.optimization.summarization_engine import SummarizationEngine


async def summarize_content_impl(
    mgrs: dict[str, object],
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
    metadata_index = cast(MetadataIndex, mgrs["index"])
    fs_manager = cast(FileSystemManager, mgrs["fs"])

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
) -> list[dict[str, object]]:
    """Summarize all files and return results."""
    results: list[dict[str, object]] = []

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

            result_item = _extract_summary_result(fname, summary_result)
            results.append(result_item)

        except FileNotFoundError:
            continue

    return results


def _extract_summary_result(
    fname: str, summary_result: dict[str, object]
) -> dict[str, object]:
    """Extract and normalize summary result data."""
    original_tokens = _safe_int(summary_result.get("original_tokens", 0))
    summarized_tokens = _safe_int(summary_result.get("summarized_tokens", 0))
    reduction = _safe_float(summary_result.get("reduction", 0.0))
    cached = bool(summary_result.get("cached", False))
    summary = str(summary_result.get("summary", ""))

    return {
        "file_name": fname,
        "original_tokens": original_tokens,
        "summarized_tokens": summarized_tokens,
        "reduction": round(reduction, 2),
        "cached": cached,
        "summary": summary,
    }


def _safe_int(value: object) -> int:
    """Safely convert value to int."""
    return int(value) if isinstance(value, (int, float)) else 0


def _safe_float(value: object) -> float:
    """Safely convert value to float."""
    return float(value) if isinstance(value, (int, float)) else 0.0


def _build_summarize_response(
    results: list[dict[str, object]], strategy: str, target_reduction: float
) -> str:
    """Build final JSON response with totals."""
    total_original = sum(_safe_int(r.get("original_tokens")) for r in results)
    total_summarized = sum(_safe_int(r.get("summarized_tokens")) for r in results)
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
            "results": results,
        },
        indent=2,
    )
