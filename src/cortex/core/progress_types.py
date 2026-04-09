"""Structured MCP progress models and reporting helper."""

from __future__ import annotations

import logging
from typing import Literal, cast

from pydantic import BaseModel, Field


class BaseProgress(BaseModel):
    """Shared fields for all structured progress payloads."""

    tool: Literal[
        "quality_gate",
        "commit",
        "pipeline",
        "session",
        "docs_gate",
    ] = Field(frozen=True)
    phase: str
    message: str


class QualityGateProgress(BaseProgress):
    """Progress payload for quality-gate style checks."""

    checks_completed: int
    checks_total: int
    current_check: str
    errors_found: int = 0


class CommitProgress(BaseProgress):
    """Progress payload for commit pipeline phases."""

    phase_label: str
    step: int
    total_steps: int


class PipelineProgress(BaseProgress):
    """Progress payload for generic pipeline operations."""

    pipeline: str
    operation: str


class SessionProgress(BaseProgress):
    """Progress payload for session lifecycle operations."""

    operation: str


class DocsGateProgress(BaseProgress):
    """Progress payload for docs gate operations."""

    files_checked: int
    issues_found: int


AnyProgress = (
    QualityGateProgress
    | CommitProgress
    | PipelineProgress
    | SessionProgress
    | DocsGateProgress
)


async def report_structured_progress(
    ctx: object | None,
    progress: AnyProgress,
    current: int,
    total: int,
) -> None:
    """Send structured progress JSON to MCP when context is available."""
    if ctx is not None:
        from cortex.core.context_logging import MCPContext, report_progress_safe

        # AI: Keep machine-readable JSON in `message` so MCP clients can parse
        # richer per-tool progress details while preserving current/total bars.
        progress_json = progress.model_dump_json()
        typed_ctx = cast(MCPContext, ctx)
        await report_progress_safe(
            typed_ctx,
            float(current),
            float(total),
            message=progress_json,
        )
        return
    logging.getLogger(__name__).debug("[progress] %s", progress.message)
