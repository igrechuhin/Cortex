"""Best-effort WAL logging around memory-bank text writes."""

from __future__ import annotations

import logging
from pathlib import Path

from cortex.core.session_config import read_session_config
from cortex.core.session_logger import get_session_id
from cortex.memory.wal import MemoryWAL, WalOperation, WalStatus, wal_build_entry

logger = logging.getLogger(__name__)


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
        wal_dir = project_root / ".cortex" / "wal"
        entry = wal_build_entry(
            operation=operation,
            relative_file=rel,
            agent_hint=wal_agent_hint(),
            before_exists=before_exists,
            before_text=before_text,
            after_text=after_text,
            status=WalStatus.OK if status_ok else WalStatus.ERROR,
            error=error_detail,
        )
        MemoryWAL(wal_dir, project_root=project_root).log(entry)
    except OSError as exc:
        logger.warning("WAL log skipped for %s: %s", file_path, exc)
    except Exception as exc:
        logger.warning("WAL log skipped for %s: %s", file_path, exc)
