"""Best-effort WAL logging around memory-bank text writes and tool calls."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from pathlib import Path

from cortex.core.session_config import read_session_config
from cortex.core.session_logger import get_session_id
from cortex.memory.wal import (
    MemoryWAL,
    ToolInvocationLog,
    WALEntry,
    WalOperation,
    WalStatus,
    wal_build_entry,
    wal_build_tool_invocation_entry,
)
from cortex.memory.wal_content import wal_content_fields

logger = logging.getLogger(__name__)

# AI: Framework/internal kwargs never worth surfacing as consolidation-candidate
# evidence (they are identical across almost every tool call and add noise).
_TOOL_INVOCATION_EXCLUDED_ARG_KEYS = frozenset(
    {"ctx", "timeout", "stability_timeout", "kind", "project_root", "enable_progress"}
)


def wal_agent_hint() -> str:
    """Session id from logger, else trace_id from session config, else ``unknown``."""
    sid = get_session_id()
    if sid:
        return sid
    cfg = read_session_config()
    tid = cfg.trace_id
    if isinstance(tid, str) and tid.strip():
        return tid.strip()
    return "unknown"


def wal_relative_file(project_root: Path, file_path: Path) -> str:
    """Path relative to project root using POSIX separators."""
    return file_path.resolve().relative_to(project_root.resolve()).as_posix()


def _build_text_mutation_entry(
    project_root: Path,
    relative_file: str,
    operation: WalOperation,
    before_exists: bool,
    before_text: str,
    after_text: str,
    status: WalStatus,
    error_detail: str | None,
) -> WALEntry:
    """Assemble the WAL entry (audit fields plus AS-OF content fields)."""
    hint = wal_agent_hint()
    return wal_build_entry(
        operation=operation,
        relative_file=relative_file,
        agent_hint=hint,
        before_exists=before_exists,
        before_text=before_text,
        after_text=after_text,
        status=status,
        error=error_detail,
        content_fields=wal_content_fields(
            project_root=project_root,
            relative_file=relative_file,
            agent_hint=hint,
            before_exists=before_exists,
            before_text=before_text,
        ),
    )


def try_wal_record_text_mutation(
    project_root: Path | None,
    file_path: Path,
    operation: WalOperation,
    before_exists: bool,
    before_text: str,
    after_text: str,
    status_ok: bool,
    error_detail: str | None,
) -> None:
    """Append WAL entry; swallow errors (WAL is advisory)."""
    if project_root is None:
        return
    try:
        rel = wal_relative_file(project_root, file_path)
        entry = _build_text_mutation_entry(
            project_root,
            rel,
            operation,
            before_exists,
            before_text,
            after_text,
            WalStatus.OK if status_ok else WalStatus.ERROR,
            error_detail,
        )
        wal_dir = project_root / ".cortex" / "wal"
        MemoryWAL(wal_dir, project_root=project_root).log(entry)
    except OSError as exc:
        logger.warning("WAL log skipped for %s: %s", file_path, exc)
    except Exception as exc:
        logger.warning("WAL log skipped for %s: %s", file_path, exc)


def wal_arg_keys_from_kwargs(kwargs: Mapping[str, object]) -> list[str]:
    """Return sorted arg key names for a tool call, excluding framework keys.

    Never inspects or returns argument *values* -- key names only.
    """
    return sorted(k for k in kwargs if k not in _TOOL_INVOCATION_EXCLUDED_ARG_KEYS)


def try_wal_record_tool_invocation(
    project_root: Path | None,
    tool_name: str,
    arg_keys: list[str],
    status_ok: bool,
    error_type: str | None,
) -> None:
    """Append a redacted tool-invocation telemetry entry; swallow errors (advisory).

    Session-scoped evidence source for analyze-tools/analyze-session
    consolidation-candidate detection, additive to existing
    pipeline_handoff graph queries.
    """
    if project_root is None:
        return
    try:
        wal_dir = project_root / ".cortex" / "wal"
        entry = wal_build_tool_invocation_entry(
            session_id=wal_agent_hint(),
            tool_name=tool_name,
            arg_keys=arg_keys,
            status=WalStatus.OK if status_ok else WalStatus.ERROR,
            error_type=error_type,
        )
        ToolInvocationLog(wal_dir).log(entry)
    except OSError as exc:
        logger.warning("Tool-invocation telemetry skipped for %s: %s", tool_name, exc)
    except Exception as exc:
        logger.warning("Tool-invocation telemetry skipped for %s: %s", tool_name, exc)
