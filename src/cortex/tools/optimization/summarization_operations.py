"""
Phase 4: Summarization Operations

This module contains the implementation logic for the summarize_content tool.
"""

import json

from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.models import ModelDict, OperationStatus
from cortex.managers.types import ManagersDict
from cortex.managers.utils import get_manager
from cortex.optimization.config import OptimizationConfig
from cortex.optimization.models import SummarizationResultModel
from cortex.optimization.summarization_engine import SummarizationEngine

# AI: a summary within 5 percentage points of target_reduction is treated as
# meeting it — token counts are estimates, so a hair-thin miss reflects
# counting noise rather than a genuinely ineffective summarization strategy.
_TARGET_TOLERANCE: float = 0.05

# AI: a supermajority of attempted files must clear the target, so a batch
# tolerates a few stubborn files without letting a mostly-failed run report
# success. A single-file call gates hard as a consequence: 0/1 = 0.0 fails,
# 1/1 = 1.0 passes.
#
# Deliberately NOT tools/compress/batch.py's policy. That verifier caps its
# thresholds absolutely (_verify_with_effective_thresholds: sample =
# min(5, successful), hits = min(3, sample)), because it samples a one-time
# repo-wide sweep to decide whether an approach works at all. Applied here it
# would pass a 50-file request on 3 good summaries. A per-request tool gate
# has to scale with the request, hence a ratio rather than a capped count.
_MIN_TARGET_HIT_RATIO: float = 0.6


async def _check_summarization_enabled(
    optimization_config: OptimizationConfig,
) -> str | None:
    """Check if summarization is enabled. Returns error JSON or None."""
    if not optimization_config.is_summarization_enabled():
        return json.dumps(
            {
                "status": OperationStatus.ERROR.value,
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
                "status": OperationStatus.ERROR.value,
                "error": "target_reduction must be between 0 and 1",
            },
            indent=2,
        )

    valid_strategies = ["extract_key_sections", "compress_verbose", "headers_only"]
    if strategy not in valid_strategies:
        return json.dumps(
            {
                "status": OperationStatus.ERROR.value,
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
    """Summarize all files, recording a skip reason instead of dropping any."""
    results: list[SummarizationResultModel] = []

    for fname in files_to_summarize:
        try:
            file_path = metadata_index.memory_bank_dir / fname
            content, _ = await fs_manager.read_file(file_path)
        except FileNotFoundError:
            results.append(_build_skip_result(strategy, fname))
            continue

        summary_result = await summarization_engine.summarize_file(
            file_name=fname,
            content=content,
            target_reduction=target_reduction,
            strategy=strategy,
        )
        results.append(
            _finalize_summary_result(summary_result, fname, target_reduction)
        )

    return results


def _build_skip_result(strategy: str, fname: str) -> SummarizationResultModel:
    """Record a file that could not be read instead of silently dropping it."""
    return SummarizationResultModel(
        original_tokens=0,
        summary_tokens=0,
        reduction=0.0,
        summary="",
        strategy=strategy,
        file_name=fname,
        skipped_reason="file not found",
    )


def _finalize_summary_result(
    summary_result: ModelDict, fname: str, target_reduction: float
) -> SummarizationResultModel:
    """Attach file identity/verdict, and reject the artifact if it missed target.

    The engine returns a legacy dict shape (with extra keys such as
    ``summarized_tokens``/``cached`` kept for direct callers); only fields
    known to `SummarizationResultModel` are kept before validating it here.
    A below-target summary is not just flagged, it is withheld: a caller
    that ignores `status` must not be able to consume rejected text.
    """
    known_fields = set(SummarizationResultModel.model_fields)
    filtered = {
        key: value for key, value in summary_result.items() if key in known_fields
    }
    result = SummarizationResultModel.model_validate(filtered)
    result.file_name = fname
    result.met_target = result.reduction >= target_reduction - _TARGET_TOLERANCE
    if not result.met_target:
        result.rejected_reason = (
            f"reduction {result.reduction:.0%} missed the "
            f"{target_reduction:.0%} target; summary withheld"
        )
        result.summary = ""
    return result


def _build_summarize_response(
    results: list[SummarizationResultModel], strategy: str, target_reduction: float
) -> str:
    """Build final JSON response with totals and a target-compliance gate."""
    attempted = [r for r in results if r.skipped_reason is None]
    skipped = [r for r in results if r.skipped_reason is not None]
    total_original = sum(r.original_tokens for r in attempted)
    total_summarized = sum(r.summary_tokens for r in attempted)
    files_meeting_target = sum(1 for r in attempted if r.met_target)
    status, error = _resolve_summarize_status(
        attempted, skipped, files_meeting_target, target_reduction
    )

    payload: ModelDict = {
        "status": status.value,
        "strategy": strategy,
        "target_reduction": target_reduction,
        "files_summarized": len(attempted),
        "files_meeting_target": files_meeting_target,
        "files_below_target": [
            r.file_name or "" for r in attempted if not r.met_target
        ],
        "files_skipped": [r.file_name or "" for r in skipped],
        "total_original_tokens": total_original,
        "total_summarized_tokens": total_summarized,
        "total_reduction": _ratio(total_original, total_summarized),
        "results": [r.model_dump() for r in results],
    }
    if error is not None:
        payload["error"] = error
    return json.dumps(payload, indent=2)


def _ratio(total_original: int, total_summarized: int) -> float:
    """Aggregate reduction across a batch, unfloored like the per-file value.

    # AI: `calculate_reduction` deliberately reports genuine growth as a
    # negative ratio rather than zero. Clamping the batch total to zero here
    # hid exactly that, and reported a batch that grew as one that merely
    # achieved nothing -- while the per-file rows alongside it said otherwise.
    """
    if total_original <= 0:
        return 0.0
    return round((total_original - total_summarized) / total_original, 2)


def _meets_target_hit_ratio(files_meeting_target: int, attempted: int) -> bool:
    """Whether enough of an attempted batch cleared the reduction target."""
    if attempted <= 0:
        return False
    return files_meeting_target / attempted >= _MIN_TARGET_HIT_RATIO


def _resolve_summarize_status(
    attempted: list[SummarizationResultModel],
    skipped: list[SummarizationResultModel],
    files_meeting_target: int,
    target_reduction: float,
) -> tuple[OperationStatus, str | None]:
    """Gate the call on target compliance: ERROR when the hit ratio is low."""
    if not attempted:
        # AI: nothing was summarized. Reporting success here would reproduce the
        # silent-skip defect one level up: a caller naming a missing file, or a
        # memory bank whose every file was unreadable, would read `success` with
        # an empty result set and never learn why.
        if skipped:
            names = ", ".join(r.file_name or "?" for r in skipped)
            return OperationStatus.ERROR, f"No files could be summarized: {names}."
        return OperationStatus.ERROR, "No files matched the request."
    if _meets_target_hit_ratio(files_meeting_target, len(attempted)):
        return OperationStatus.SUCCESS, None
    best_reduction = max(r.reduction for r in attempted)
    error = (
        f"Only {files_meeting_target}/{len(attempted)} summarized files reached "
        f"the {target_reduction:.0%} reduction target (need "
        f"{_MIN_TARGET_HIT_RATIO:.0%} of attempts); best achieved reduction "
        f"was {best_reduction:.0%}."
    )
    return OperationStatus.ERROR, error
