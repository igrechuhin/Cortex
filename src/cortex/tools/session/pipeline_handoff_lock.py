"""Synchronous file-based lock for pipeline.json read-modify-write sections.

# AI: pipeline_handoff operations run inside asyncio.to_thread worker
# threads (see pipeline_handoff._dispatch), so two overlapping MCP tool
# calls -- e.g. an orchestrator's op_mark_running racing a subagent's
# op_write_result on the same live pipeline -- can execute concurrently on
# real threads, not merely interleaved coroutines. Without serialization, a
# read-modify-write cycle in one thread can commit a state computed from a
# stale read, silently discarding phases written by the other thread in
# between (reproduced in tests/tools/test_pipeline_handoff_race.py). This
# mirrors the O_CREAT|O_EXCL advisory-lock pattern already used by
# cortex.core.cache_json_access and cortex.core.file_system, but
# synchronous (no event loop is available inside a to_thread worker).
"""

from __future__ import annotations

import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

_LOCK_TIMEOUT_SECONDS = 5.0
_LOCK_POLL_INTERVAL_SECONDS = 0.05
_STALE_LOCK_SECONDS = 180.0


def _lock_path_for(target_file: Path) -> Path:
    return target_file.with_suffix(f"{target_file.suffix}.lock")


def _try_acquire(lock_path: Path) -> bool:
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        return False
    os.close(fd)
    return True


def _clear_stale_lock(lock_path: Path) -> None:
    """Remove a lock file abandoned by a crashed/killed holder."""
    try:
        mtime = lock_path.stat().st_mtime
    except OSError:
        return
    if (time.time() - mtime) > _STALE_LOCK_SECONDS:
        try:
            lock_path.unlink()
        except OSError:
            pass


def _acquire_blocking(lock_path: Path, timeout_seconds: float) -> bool:
    """Poll for the lock until acquired or the timeout elapses."""
    start = time.monotonic()
    while True:
        if _try_acquire(lock_path):
            return True
        _clear_stale_lock(lock_path)
        if (time.monotonic() - start) > timeout_seconds:
            return False
        time.sleep(_LOCK_POLL_INTERVAL_SECONDS)


@contextmanager
def pipeline_state_lock(
    target_file: Path, timeout_seconds: float = _LOCK_TIMEOUT_SECONDS
) -> Iterator[None]:
    """Serialize read-modify-write access to ``target_file`` across threads.

    Best-effort: a lock-acquisition timeout falls through to unlocked access
    rather than raising, so a stuck/dead lock never blocks pipeline_handoff
    calls forever -- state-file writes must never crash the orchestrator.
    """
    lock_path = _lock_path_for(target_file)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    acquired = _acquire_blocking(lock_path, timeout_seconds)
    try:
        yield
    finally:
        if acquired:
            try:
                lock_path.unlink()
            except OSError:
                pass
