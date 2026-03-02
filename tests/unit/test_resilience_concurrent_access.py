"""Resilience tests for concurrent access and graceful degradation.

Covers plan-security-and-resilience Step 2: Resilience Testing for Concurrent Access.
Verifies semaphore exhaustion/recovery, file locking under contention, concurrent
tool calls, and chaos scenarios.
"""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from cortex.core.exceptions import FileLockTimeoutError
from cortex.core.file_system import FileSystemManager
from cortex.core.mcp_stability_config import TrackedSemaphore
from tests.helpers.path_helpers import ensure_test_cortex_structure


class TestTrackedSemaphoreExhaustionAndRecovery:
    """Test TrackedSemaphore exhaustion, recovery, and resource release."""

    @pytest.mark.asyncio
    async def test_semaphore_exhaustion_try_acquire_returns_false(self) -> None:
        """Exhausted semaphore returns False from try_acquire."""
        sem = TrackedSemaphore(2)
        async with sem:
            async with sem:
                ok = await sem.try_acquire(timeout=0.01)
                assert ok is False
                assert sem.available == 0

    @pytest.mark.asyncio
    async def test_semaphore_recovery_after_release(self) -> None:
        """Semaphore recovers after release; new acquire succeeds."""
        sem = TrackedSemaphore(1)
        async with sem:
            ok = await sem.try_acquire(timeout=0.01)
            assert ok is False
        # Released
        ok = await sem.try_acquire(timeout=0.5)
        assert ok is True
        sem.release()

    @pytest.mark.asyncio
    async def test_semaphore_context_manager_releases_on_exception(self) -> None:
        """Context manager releases semaphore when exception is raised."""
        sem = TrackedSemaphore(1)
        with pytest.raises(ValueError, match="intentional"):
            async with sem:
                raise ValueError("intentional")
        # Semaphore should be released (available == 1)
        ok = await sem.try_acquire(timeout=0.1)
        assert ok is True
        sem.release()


class TestConcurrentManageFileWrites:
    """Test multiple simultaneous manage_file writes to same file."""

    @pytest.mark.asyncio
    async def test_concurrent_manage_file_writes_to_same_file_serialize(
        self, tmp_path: Path
    ) -> None:
        """Concurrent manage_file writes to same file serialize via lock."""
        from cortex.tools.files.crud_operations import manage_file

        memory_bank_dir = ensure_test_cortex_structure(tmp_path)
        target_file = memory_bank_dir / "activeContext.md"
        _minimal = (
            "## Current Focus\n"
            "None. Placeholder to meet minimum length for schema validation.\n\n"
            "## Recent Changes\n"
            "None. Placeholder to meet minimum length for schema validation.\n\n"
            "## Next Steps\n"
            "See roadmap. Placeholder to meet minimum length for schema."
        )
        _ = target_file.write_text(_minimal)

        results: list[str] = []

        async def write_one(i: int) -> None:
            content = (
                "## Current Focus\n"
                f"Write {i}. Placeholder to meet minimum length for schema validation.\n\n"
                "## Recent Changes\n"
                f"Content {i}. Placeholder to meet minimum length for schema validation.\n\n"
                "## Next Steps\n"
                "See roadmap. Placeholder to meet minimum length for schema."
            )
            out = await manage_file(
                file_name="activeContext.md",
                operation="write",
                content=content,
            )
            results.append(out)

        with patch(
            "cortex.tools.files.manage_file_helpers.get_or_resolve_project_root",
            new_callable=AsyncMock,
            return_value=tmp_path,
        ):
            _ = await asyncio.gather(
                write_one(1),
                write_one(2),
                write_one(3),
            )

        # All three complete (no deadlock). Due to lock serialization and
        # conflict detection, one or more may succeed; others may get conflict.
        assert len(results) == 3
        success_count = sum(
            1 for r in results if json.loads(str(r))["status"] == "success"
        )
        assert success_count >= 1, "At least one write should succeed"
        final = target_file.read_text()
        assert "Current Focus" in final and "Recent" in final


class TestConcurrentSessionStart:
    """Test concurrent session_start calls."""

    @pytest.mark.asyncio
    async def test_concurrent_session_start_calls_all_succeed(
        self, tmp_path: Path
    ) -> None:
        """Multiple concurrent session_start calls complete successfully."""
        from cortex.tools.session.start_tools import session_start

        memory_bank_dir = ensure_test_cortex_structure(tmp_path)
        _ = (memory_bank_dir / "roadmap.md").write_text("# Roadmap")
        _ = (memory_bank_dir / "activeContext.md").write_text("# Active")

        with patch(
            "cortex.tools.session.start_tools.get_or_resolve_project_root",
            new_callable=AsyncMock,
            return_value=tmp_path,
        ):
            gathered: tuple[str, str, str] = await asyncio.gather(
                session_start(task_description=None),
                session_start(task_description=None),
                session_start(task_description=None),
            )

        for r in gathered:
            parsed = json.loads(r)
            assert parsed["status"] == "success"
            assert "brief" in parsed or "mcp_healthy" in str(parsed).lower()


class TestLockTimeoutAndResourceRelease:
    """Test lock timeout handling and resource release on error."""

    @pytest.mark.asyncio
    async def test_file_lock_timeout_releases_polling_resources(
        self, tmp_path: Path
    ) -> None:
        """When lock times out, no lock file is left by the waiter."""
        memory_bank_dir = ensure_test_cortex_structure(tmp_path)
        file_path = memory_bank_dir / "test.md"
        lock_path = file_path.with_suffix(file_path.suffix + ".lock")
        _ = file_path.write_text("# Test")
        lock_path.touch()

        manager = FileSystemManager(tmp_path)
        manager.lock_timeout = 1

        with pytest.raises(FileLockTimeoutError):
            await manager.acquire_lock(lock_path)

        # Lock file should still exist (held by "other"); we didn't create a second
        assert lock_path.exists()
        lock_path.unlink()


class TestChaosScenarios:
    """Chaos tests: random delays and simulated failures."""

    @pytest.mark.asyncio
    async def test_async_operation_with_random_delay_completes(self) -> None:
        """Operation with random delay still completes (no deadlock)."""
        import random

        sem = TrackedSemaphore(2)
        delays = [random.uniform(0.01, 0.05) for _ in range(4)]

        async def delayed_acquire(i: int) -> bool:
            await asyncio.sleep(delays[i])
            return await sem.try_acquire(timeout=1.0)

        acquired: tuple[bool, ...] = await asyncio.gather(
            delayed_acquire(0),
            delayed_acquire(1),
            delayed_acquire(2),
            delayed_acquire(3),
        )
        # First two succeed immediately (after delay); others may wait
        n_acquired = sum(acquired)
        assert n_acquired >= 2
        for _ in range(n_acquired):
            sem.release()

    @pytest.mark.asyncio
    async def test_permission_denied_during_write_returns_error(
        self, tmp_path: Path
    ) -> None:
        """Simulated PermissionError during write returns error response."""
        from cortex.tools.files.crud_operations import manage_file

        memory_bank_dir = ensure_test_cortex_structure(tmp_path)
        target = memory_bank_dir / "activeContext.md"
        _ = target.write_text("# Start")

        with patch(
            "cortex.tools.files.manage_file_helpers.get_or_resolve_project_root",
            new_callable=AsyncMock,
            return_value=tmp_path,
        ):
            with patch(
                "cortex.tools.files.crud_flow.write_file_with_hash_check",
                new_callable=AsyncMock,
                side_effect=PermissionError("Simulated permission denied"),
            ):
                result_str = await manage_file(
                    file_name="activeContext.md",
                    operation="write",
                    content="# Updated",
                )

        parsed = json.loads(result_str)
        assert parsed["status"] == "error"
        assert (
            "permission" in parsed["error"].lower()
            or "error" in parsed["error"].lower()
        )
