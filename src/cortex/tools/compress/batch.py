"""Batch compression orchestration for markdown trees."""

from __future__ import annotations

import logging
from pathlib import Path

from .compress import CompressResult, compress_file

_SYNAPSE_PROMPTS_GLOB = "**/*.md"
_CURSOR_AGENTS_GLOB = "**/*.md"
_MEMORY_BANK_FILES: tuple[str, ...] = ("activeContext.md", "progress.md")
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


def compress_directory(
    root: Path, *, glob: str = "**/*.md", dry_run: bool = False
) -> list[CompressResult]:
    """Compress all eligible files under a root directory."""

    results: list[CompressResult] = []
    for path in sorted(root.glob(glob)):
        if not path.is_file() or _is_backup_file(path):
            continue
        result = compress_file(path, dry_run=dry_run)
        _log_outcome(path, result)
        results.append(result)
    return results


def compress_cortex_internal_files(
    repo_root: Path, *, dry_run: bool = True
) -> list[CompressResult]:
    """Run one-time compression for Cortex-managed prompt and memory files."""

    results: list[CompressResult] = []
    prompts_root = repo_root / ".cortex" / "synapse" / "prompts"
    agents_root = repo_root / ".cortex" / "synapse" / "cursor-agents"
    memory_bank_root = repo_root / ".cortex" / "memory-bank"

    if prompts_root.exists():
        results.extend(
            compress_directory(
                prompts_root, glob=_SYNAPSE_PROMPTS_GLOB, dry_run=dry_run
            )
        )
    if agents_root.exists():
        results.extend(
            compress_directory(agents_root, glob=_CURSOR_AGENTS_GLOB, dry_run=dry_run)
        )
    for file_name in _MEMORY_BANK_FILES:
        target = memory_bank_root / file_name
        if not target.is_file():
            continue
        results.append(compress_file(target, dry_run=dry_run))
    return results
