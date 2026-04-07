"""Best-effort hooks for appending memory-bank operations-log entries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from cortex.core.constants import MemoryBankFile
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.project_root_resolver import resolve_project_root_async
from cortex.tools.plans.operations_log import (
    OperationsLogType,
    append_operations_log_entry,
)


def parse_json_object(raw: str) -> dict[str, object] | None:
    """Parse JSON object payloads and return None for non-object responses."""
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return cast(dict[str, object], parsed) if isinstance(parsed, dict) else None


async def append_log_entry_best_effort(
    *,
    operation_type: OperationsLogType,
    title: str,
    summary: str | None,
    ctx: MCPContext | None,
    project_root: Path | None = None,
) -> None:
    """Append one operations-log entry and never raise on failure."""
    try:
        root = project_root or await resolve_project_root_async(None, ctx)
        log_path = (
            get_cortex_path(root, CortexResourceType.MEMORY_BANK) / MemoryBankFile.LOG
        )
        _ = append_operations_log_entry(
            log_path=log_path,
            operation_type=operation_type,
            title=title,
            summary=summary,
        )
    except Exception as exc:  # pragma: no cover - best-effort logging path
        await log_client(
            ctx,
            "warning",
            f"operations_log_append_failed: {exc}",
            logger_name=__name__,
        )
