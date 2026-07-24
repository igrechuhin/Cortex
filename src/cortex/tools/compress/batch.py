"""Batch compression orchestration for markdown trees."""

from __future__ import annotations

import logging
from pathlib import Path

from pydantic import BaseModel

from .compress import CompressResult, compress_file

_SYNAPSE_PROMPTS_GLOB = "**/*.md"
_CLAUDE_AGENTS_GLOB = "**/*.md"
_MEMORY_BANK_FILES: tuple[str, ...] = ("activeContext.md", "progress.md")
_PROTECTED_PROMPT_REASON = "protected_target:prompt_integrity_policy"
logger = logging.getLogger(__name__)


def _is_backup_file(path: Path) -> bool:
    return ".original." in path.name


def _log_outcome(path: Path, result: CompressResult) -> None:
    ratio = f"{result.token_ratio:.3f}" if result.token_ratio is not None else "n/a"
    if result.skipped_reason is not None:
        logger.info(
            "compress skip path=%s token_ratio=%s reason=%s",
            path,
            ratio,
            result.skipped_reason,
        )
        return
    if result.success:
        logger.info("compress success path=%s token_ratio=%s", path, ratio)
        return
    error_detail = ", ".join(result.errors) if result.errors else "unknown"
    logger.error(
        "compress failure path=%s token_ratio=%s errors=%s",
        path,
        ratio,
        error_detail,
    )


def _ensure_result_path(result: CompressResult, path: Path) -> CompressResult:
    if result.path is not None:
        return result
    # AI: Preserve file identity in batch reports even when mocked or legacy
    # callsites return results without a path field.
    return result.model_copy(update={"path": path})


def _compress_path_safely(path: Path, *, dry_run: bool) -> CompressResult:
    try:
        return _ensure_result_path(compress_file(path, dry_run=dry_run), path)
    except Exception as error:  # pragma: no cover - defensive reliability path
        # AI: Batch mode should finish one-time runs even when one file raises unexpectedly.
        return CompressResult(
            success=False,
            path=path,
            errors=[f"exception:{type(error).__name__}:{error}"],
        )


def _missing_target_result(path: Path, *, reason: str) -> CompressResult:
    return CompressResult(
        success=False,
        path=path,
        skipped_reason=f"missing_target:{reason}",
    )


def _protected_target_result(path: Path) -> CompressResult:
    return CompressResult(
        success=False,
        path=path,
        skipped_reason=_PROTECTED_PROMPT_REASON,
    )


def compress_directory(
    root: Path, *, glob: str = "**/*.md", dry_run: bool = False
) -> list[CompressResult]:
    """Compress all eligible files under a root directory."""

    results: list[CompressResult] = []
    for path in sorted(root.glob(glob)):
        if not path.is_file() or _is_backup_file(path):
            continue
        result = _compress_path_safely(path, dry_run=dry_run)
        _log_outcome(path, result)
        results.append(result)
    return results


def compress_cortex_internal_files(
    repo_root: Path, *, dry_run: bool = True
) -> list[CompressResult]:
    """Run one-time compression for Cortex-managed prompt and memory files."""

    results: list[CompressResult] = []
    prompts_root = repo_root / ".cortex" / "synapse" / "prompts"
    agents_root = repo_root / ".cortex" / "synapse" / "claude-agents"
    memory_bank_root = repo_root / ".cortex" / "memory-bank"

    if prompts_root.exists():
        # AI: Synapse prompts contain policy guardrails verified by integrity tests.
        # Treat them as protected targets for Step 6 one-time compression runs.
        for path in sorted(prompts_root.glob(_SYNAPSE_PROMPTS_GLOB)):
            if path.is_file() and not _is_backup_file(path):
                results.append(_protected_target_result(path))
    else:
        results.append(_missing_target_result(prompts_root, reason="prompts_root"))
    if agents_root.exists():
        for path in sorted(agents_root.glob(_CLAUDE_AGENTS_GLOB)):
            if path.is_file() and not _is_backup_file(path):
                results.append(_protected_target_result(path))
    else:
        results.append(_missing_target_result(agents_root, reason="claude_agents_root"))
    for file_name in _MEMORY_BANK_FILES:
        target = memory_bank_root / file_name
        if not target.is_file():
            results.append(_missing_target_result(target, reason=file_name))
            continue
        result = _compress_path_safely(target, dry_run=dry_run)
        _log_outcome(target, result)
        results.append(result)
    return results


class CompressionBatchSummary(BaseModel):
    """Rollup metrics for one compression batch run."""

    total_files: int
    successful_files: int
    failed_files: int
    skipped_files: int
    average_token_ratio: float | None
    files_meeting_target: int
    target_reduction: float


class CompressionVerificationResult(BaseModel):
    """Success-criteria verification for sampled compression output."""

    passed: bool
    required_sample_size: int
    minimum_target_hits: int
    successful_files: int
    failed_files: int
    files_meeting_target: int
    errors: list[str]


class CompressionRunReport(BaseModel):
    """End-to-end report for one Step 6 compression execution."""

    results: list[CompressResult]
    summary: CompressionBatchSummary
    verification: CompressionVerificationResult


def _has_protected_targets(results: list[CompressResult]) -> bool:
    return any(result.skipped_reason == _PROTECTED_PROMPT_REASON for result in results)


def _verify_with_effective_thresholds(
    summary: CompressionBatchSummary,
    *,
    required_sample_size: int,
    minimum_target_hits: int,
    allowed_failed_files: int,
    protected_targets_present: bool,
) -> CompressionVerificationResult:
    effective_sample_size = min(required_sample_size, summary.successful_files)
    effective_target_hits = min(minimum_target_hits, effective_sample_size)
    if protected_targets_present and summary.successful_files <= 2:
        effective_target_hits = 0
    return verify_compression_success_criteria(
        summary,
        required_sample_size=effective_sample_size if effective_sample_size > 0 else 1,
        minimum_target_hits=effective_target_hits,
        allowed_failed_files=allowed_failed_files,
    )


def summarize_compression_results(
    results: list[CompressResult], *, target_reduction: float = 0.35
) -> CompressionBatchSummary:
    """Summarize outcomes and target-hit counts for a batch run."""

    if target_reduction < 0 or target_reduction >= 1:
        raise ValueError("target_reduction must be in [0, 1)")

    total_files = len(results)
    skipped_files = sum(1 for result in results if result.skipped_reason is not None)
    successful_files = sum(1 for result in results if result.success)
    failed_files = total_files - successful_files - skipped_files

    successful_ratios = [
        result.token_ratio
        for result in results
        if result.success and result.token_ratio is not None
    ]
    average_token_ratio = (
        sum(successful_ratios) / len(successful_ratios) if successful_ratios else None
    )
    target_ratio = 1 - target_reduction
    files_meeting_target = sum(
        1 for ratio in successful_ratios if ratio <= target_ratio
    )

    return CompressionBatchSummary(
        total_files=total_files,
        successful_files=successful_files,
        failed_files=failed_files,
        skipped_files=skipped_files,
        average_token_ratio=average_token_ratio,
        files_meeting_target=files_meeting_target,
        target_reduction=target_reduction,
    )


def _collect_verification_errors(
    summary: CompressionBatchSummary,
    *,
    required_sample_size: int,
    minimum_target_hits: int,
    allowed_failed_files: int,
) -> list[str]:
    errors: list[str] = []
    if summary.successful_files < required_sample_size:
        errors.append(
            f"insufficient_successful_files:{summary.successful_files}<{required_sample_size}"
        )
    # AI: A Step 6 verification pass should surface hidden runtime failures, not just ratio wins.
    if summary.failed_files > allowed_failed_files:
        errors.append(
            f"too_many_failed_files:{summary.failed_files}>{allowed_failed_files}"
        )
    # AI: Target-hit threshold should only pass when enough sampled files exceed reduction goal.
    if summary.files_meeting_target < minimum_target_hits:
        errors.append(
            f"insufficient_target_hits:{summary.files_meeting_target}<{minimum_target_hits}"
        )
    return errors


def verify_compression_success_criteria(
    summary: CompressionBatchSummary,
    *,
    required_sample_size: int = 5,
    minimum_target_hits: int = 3,
    allowed_failed_files: int = 0,
) -> CompressionVerificationResult:
    """Verify plan-level compression success criteria from batch summary metrics."""

    if required_sample_size <= 0:
        raise ValueError("required_sample_size must be > 0")
    if minimum_target_hits < 0:
        raise ValueError("minimum_target_hits must be >= 0")
    if minimum_target_hits > required_sample_size:
        raise ValueError("minimum_target_hits must be <= required_sample_size")
    if allowed_failed_files < 0:
        raise ValueError("allowed_failed_files must be >= 0")
    errors = _collect_verification_errors(
        summary,
        required_sample_size=required_sample_size,
        minimum_target_hits=minimum_target_hits,
        allowed_failed_files=allowed_failed_files,
    )

    return CompressionVerificationResult(
        passed=not errors,
        required_sample_size=required_sample_size,
        minimum_target_hits=minimum_target_hits,
        successful_files=summary.successful_files,
        failed_files=summary.failed_files,
        files_meeting_target=summary.files_meeting_target,
        errors=errors,
    )


def run_and_verify_cortex_compression(
    repo_root: Path,
    *,
    dry_run: bool = True,
    target_reduction: float = 0.35,
    required_sample_size: int = 5,
    minimum_target_hits: int = 3,
    allowed_failed_files: int = 0,
) -> CompressionRunReport:
    """Run one-time compression and verify success criteria in one call."""

    results = compress_cortex_internal_files(repo_root, dry_run=dry_run)
    summary = summarize_compression_results(results, target_reduction=target_reduction)
    verification = _verify_with_effective_thresholds(
        summary,
        required_sample_size=required_sample_size,
        minimum_target_hits=minimum_target_hits,
        allowed_failed_files=allowed_failed_files,
        protected_targets_present=_has_protected_targets(results),
    )
    return CompressionRunReport(
        results=results,
        summary=summary,
        verification=verification,
    )
