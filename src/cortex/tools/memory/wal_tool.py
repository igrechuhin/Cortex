"""MCP tool: read WAL, detect anomalies, snapshot/restore memory-bank."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from cortex.core.constants import MCP_TOOL_TIMEOUT_MEDIUM
from cortex.core.context_logging import MCPContext
from cortex.core.mcp_annotations import safe_write_annotations
from cortex.core.mcp_stability import ensure_usage_context, mcp_tool_wrapper
from cortex.core.pydantic_extra import EXTRA_FORBID
from cortex.core.usage_context import get_or_resolve_project_root
from cortex.memory.wal import (
    MemoryWAL,
    ToolInvocationEntry,
    ToolInvocationLog,
    WALEntry,
)
from cortex.memory.wal_content import WalAsOfResult, wal_as_of
from cortex.memory.wal_hooks import wal_agent_hint
from cortex.server import mcp


class MemoryWalToolOp(StrEnum):
    """Supported ``memory_wal`` operations."""

    READ = "read"
    ANOMALIES = "anomalies"
    SNAPSHOT = "snapshot"
    RESTORE = "restore"
    TOOL_INVOCATIONS = "tool_invocations"
    AS_OF = "as_of"


class MemoryWALInput(BaseModel):
    """Input for ``memory_wal`` MCP tool."""

    model_config = ConfigDict(extra=EXTRA_FORBID)

    operation: MemoryWalToolOp = Field(
        description="read | anomalies | snapshot | restore | tool_invocations | as_of"
    )
    since: str | None = Field(default=None, description="ISO lower bound for read")
    label: str | None = Field(
        default=None, description="Snapshot label (restore required)"
    )
    file: str | None = Field(
        default=None,
        description="Project-relative memory-bank path for as_of",
    )
    step_number: int | None = Field(
        default=None, ge=0, description="Experience-store step number for as_of"
    )


class MemoryWALResult(BaseModel):
    """Structured ``memory_wal`` response."""

    model_config = ConfigDict(extra=EXTRA_FORBID)

    operation: str
    entries: list[WALEntry] | None = None
    warnings: list[str] | None = None
    snapshot_path: str | None = None
    files_restored: int | None = None
    tool_invocations: list[ToolInvocationEntry] | None = None
    as_of: WalAsOfResult | None = None


def _default_snapshot_label() -> str:
    return datetime.now(UTC).strftime("pre-compact-%Y%m%dT%H%M%SZ")


def _as_of_result(project_root: Path, data: MemoryWALInput) -> WalAsOfResult:
    """Validate as_of inputs and reconstruct the requested historical view."""
    if not data.file or not data.file.strip():
        raise ValueError("as_of requires a non-empty file")
    if data.step_number is None:
        raise ValueError("as_of requires step_number")
    return wal_as_of(project_root, data.file.strip(), data.step_number)


def handle_memory_wal_sync(project_root: Path, data: MemoryWALInput) -> MemoryWALResult:
    wal_dir = project_root / ".cortex" / "wal"
    wal = MemoryWAL(wal_dir, project_root=project_root)
    op = data.operation
    if op == MemoryWalToolOp.READ:
        entries = wal.read(data.since)
        if data.since is None and len(entries) > 50:
            entries = entries[-50:]
        return MemoryWALResult(operation=op.value, entries=entries)
    if op == MemoryWalToolOp.ANOMALIES:
        return MemoryWALResult(operation=op.value, warnings=wal.detect_anomalies())
    if op == MemoryWalToolOp.SNAPSHOT:
        label = data.label or _default_snapshot_label()
        snap = wal.snapshot(label)
        return MemoryWALResult(operation=op.value, snapshot_path=str(snap))
    if op == MemoryWalToolOp.AS_OF:
        as_of = _as_of_result(project_root, data)
        return MemoryWALResult(operation=op.value, as_of=as_of)
    if op == MemoryWalToolOp.TOOL_INVOCATIONS:
        invocations = ToolInvocationLog(wal_dir).read(session_id=wal_agent_hint())
        return MemoryWALResult(operation=op.value, tool_invocations=invocations)
    assert op == MemoryWalToolOp.RESTORE
    if not data.label or not str(data.label).strip():
        raise ValueError("restore requires non-empty label")
    n = wal.restore(str(data.label).strip())
    return MemoryWALResult(operation=op.value, files_restored=n)


@mcp.tool(
    annotations=safe_write_annotations(
        "Memory bank write-ahead log (audit / rollback)"
    ),
    output_schema=None,
)
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def memory_wal(
    operation: str = "read",
    since: str | None = None,
    label: str | None = None,
    file: str | None = None,
    step_number: int | None = None,
    ctx: MCPContext | None = None,
) -> str:
    """Inspect or manage the memory-bank WAL (JSONL audit log and snapshots).

    USE WHEN: You need an audit trail of memory-bank writes, anomaly hints, or
    a filesystem snapshot/restore of ``.cortex/memory-bank/*.md`` (not a git
    substitute).

    DO NOT: Treat WAL as authoritative security auditing; it is best-effort and
    can be disabled by disk errors (writes still proceed).

    EXAMPLES:
    - memory_wal(operation="read") — last 50 WAL entries
    - memory_wal(operation="anomalies") — heuristic warnings
    - memory_wal(operation="snapshot", label="backup-2026-04-15")
    - memory_wal(operation="restore", label="backup-2026-04-15")
    - memory_wal(operation="as_of", file=".cortex/memory-bank/activeContext.md",
      step_number=7) - what that file said at experience step 7 (analyze
      pipeline evidence; hash-verified, raises when history was pruned).
    - memory_wal(operation="tool_invocations") — current session's redacted
      MCP tool-call sequence (tool name, arg key names, outcome; no argument
      values) for analyze-tools/analyze-session consolidation-candidate
      detection, additive to pipeline_handoff graph queries.

    Pre-compact automation: there is no bundled Claude ``PreCompact`` hook in
    this repo; run ``memory_wal(operation="snapshot", label="pre-compact-…")``
    manually before risky compaction if you want a rollback point.
    """
    root = await get_or_resolve_project_root(ctx)
    try:
        payload = MemoryWALInput.model_validate(
            {
                "operation": operation,
                "since": since,
                "label": label,
                "file": file,
                "step_number": step_number,
            }
        )
        result = handle_memory_wal_sync(root, payload)
        return result.model_dump_json(indent=2)
    except (ValueError, ValidationError) as e:
        return json.dumps({"status": "error", "error": str(e)}, indent=2)
