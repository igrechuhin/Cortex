"""Unit tests for the synchronous pipeline_handoff file lock."""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path

from cortex.tools.session.pipeline_handoff_lock import pipeline_state_lock


def _expected_lock_path(target: Path) -> Path:
    """Mirror the module's private lock-path naming convention for assertions."""
    return target.with_suffix(f"{target.suffix}.lock")


class TestPipelineStateLock:
    def test_serializes_two_concurrent_critical_sections(self, tmp_path: Path) -> None:
        # Arrange
        target = tmp_path / "pipeline.json"
        order: list[str] = []
        holder_entered = threading.Event()

        def holder() -> None:
            with pipeline_state_lock(target):
                order.append("holder-enter")
                holder_entered.set()
                time.sleep(0.2)
                order.append("holder-exit")

        def waiter() -> None:
            assert holder_entered.wait(timeout=2)
            with pipeline_state_lock(target):
                order.append("waiter-enter")

        # Act
        t1 = threading.Thread(target=holder)
        t2 = threading.Thread(target=waiter)
        t1.start()
        t2.start()
        t1.join(timeout=3)
        t2.join(timeout=3)

        # Assert: the waiter never enters before the holder exits.
        assert order == ["holder-enter", "holder-exit", "waiter-enter"]

    def test_lock_file_removed_after_context_exits(self, tmp_path: Path) -> None:
        # Arrange
        target = tmp_path / "pipeline.json"

        # Act
        with pipeline_state_lock(target):
            assert _expected_lock_path(target).exists()

        # Assert
        assert not _expected_lock_path(target).exists()

    def test_stale_lock_is_cleared_and_acquired(self, tmp_path: Path) -> None:
        # Arrange: simulate a lock left behind by a crashed holder.
        target = tmp_path / "pipeline.json"
        lock_path = _expected_lock_path(target)
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.touch()
        old_time = time.time() - 300
        os.utime(lock_path, (old_time, old_time))

        # Act / Assert: acquiring should succeed promptly, not time out.
        start = time.monotonic()
        with pipeline_state_lock(target, timeout_seconds=5.0):
            pass
        assert (time.monotonic() - start) < 2.0

    def test_timeout_falls_through_to_unlocked_access_without_raising(
        self, tmp_path: Path
    ) -> None:
        # Arrange: a fresh (non-stale) lock file already held by "another process".
        target = tmp_path / "pipeline.json"
        lock_path = _expected_lock_path(target)
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.touch()

        # Act / Assert: never raises, even though the lock could not be acquired.
        with pipeline_state_lock(target, timeout_seconds=0.1):
            pass

        # The pre-existing lock file (not ours) is left in place since we
        # never acquired it and therefore must not delete someone else's lock.
        assert lock_path.exists()
