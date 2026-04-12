"""MCP tool: compress attached-project memory files (CLAUDE.md, memory-bank)."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from cortex.core.constants import MCP_TOOL_TIMEOUT_COMPLEX
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_annotations import safe_write_annotations
from cortex.core.mcp_stability import ensure_usage_context, mcp_tool_wrapper
from cortex.core.models import OperationStatus
from cortex.core.project_root_resolver import resolve_project_root_async
from cortex.server import mcp
from cortex.tools.analysis.token_budget import iter_memory_bank_text_paths
from cortex.tools.compress.compress import compress_file


class FileCompressResult(BaseModel):
    """Per-file outcome for compress_memory_bank."""

    path: str
    success: bool
    token_ratio: float
    errors: list[str] = Field(default_factory=list)
    skipped_reason: str | None = None


class CompressMemoryBankResult(BaseModel):
    """Aggregate result for compress_memory_bank MCP tool."""

    files_processed: int
    files_compressed: int
    files_skipped: int
    files_failed: int
    results: list[FileCompressResult]
    average_token_ratio: float
    total_words_saved: int


def _word_count_file(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").split())


def _original_word_count(path: Path) -> int:
    if not path.is_file():
        return 0
    try:
        return _word_count_file(path)
    except OSError:
        return 0


def _process_one_memory_path(
    project_root: Path, path: Path
) -> tuple[FileCompressResult, str, float, int]:
    """One file through compress_file; returns result kind, ratio credit, words saved."""
    original_words = _original_word_count(path)
    cr = compress_file(path, dry_run=False)
    rel = str(path.relative_to(project_root)).replace("\\", "/")
    tr = cr.token_ratio if cr.token_ratio is not None else 1.0
    errs = list(cr.errors)
    base = FileCompressResult(
        path=rel,
        success=bool(cr.success),
        token_ratio=tr,
        errors=errs,
        skipped_reason=cr.skipped_reason,
    )
    if cr.skipped_reason is not None:
        return base, "skipped", 0.0, 0
    if cr.success:
        saved = 0
        if original_words > 0 and cr.token_ratio is not None:
            cw = int(round(original_words * cr.token_ratio))
            saved = max(0, original_words - cw)
        return base, "compressed", tr, saved
    return (
        FileCompressResult(
            path=rel, success=False, token_ratio=tr, errors=errs, skipped_reason=None
        ),
        "failed",
        0.0,
        0,
    )


def _compress_all_memory_paths(project_root: Path) -> CompressMemoryBankResult:
    """Run compress_file over iter_memory_bank_text_paths and aggregate."""
    results: list[FileCompressResult] = []
    files_compressed = files_skipped = files_failed = 0
    ratio_sum = 0.0
    ratio_count = 0
    total_words_saved = 0
    for path in iter_memory_bank_text_paths(project_root):
        fr, kind, ratio_credit, wsaved = _process_one_memory_path(project_root, path)
        results.append(fr)
        if kind == "skipped":
            files_skipped += 1
        elif kind == "compressed":
            files_compressed += 1
            ratio_sum += ratio_credit
            ratio_count += 1
            total_words_saved += wsaved
        else:
            files_failed += 1
    avg = (ratio_sum / ratio_count) if ratio_count else 1.0
    return CompressMemoryBankResult(
        files_processed=len(results),
        files_compressed=files_compressed,
        files_skipped=files_skipped,
        files_failed=files_failed,
        results=results,
        average_token_ratio=avg,
        total_words_saved=total_words_saved,
    )


def run_compress_memory_bank(project_root: Path) -> CompressMemoryBankResult:
    """Compress all target memory files; core logic for MCP tool and tests."""
    return _compress_all_memory_paths(project_root)


@mcp.tool(
    annotations=safe_write_annotations(
        "Compress Memory Bank (CLAUDE.md, .cortex/memory-bank/*.md)"
    )
)
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_COMPLEX)
async def compress_memory_bank(
    project_root: str | None = None,
    ctx: MCPContext | None = None,
) -> str:
    """Compress project memory files (CLAUDE.md, .cortex/memory-bank/*.md) to
    reduce session token cost. Creates .original backups; validates structural
    integrity before overwriting. Returns per-file compression ratios.

    USE WHEN: Attached projects need shorter CLAUDE.md / memory-bank prose after
    cortex://analysis flags compression candidates, or before long sessions.

    DO NOT: Run on source code, tests, or user-facing docs outside memory paths.

    EXAMPLES:
    - compress_memory_bank() — zero-arg uses MCP workspace root
    - compress_memory_bank(project_root="/path/to/project")

    RETURNS: JSON with ``status`` and ``result`` (``CompressMemoryBankResult`` fields).
    """
    await log_client(
        ctx, "info", "compress_memory_bank: starting", logger_name=__name__
    )
    if project_root is not None and project_root.strip():
        root = Path(project_root).expanduser().resolve()
    else:
        root = await resolve_project_root_async(None, ctx)

    payload = run_compress_memory_bank(root)
    await log_client(
        ctx,
        "info",
        f"compress_memory_bank: done processed={payload.files_processed}",
        logger_name=__name__,
    )
    return json.dumps(
        {
            "status": OperationStatus.SUCCESS.value,
            "result": payload.model_dump(mode="json"),
        },
        indent=2,
    )
