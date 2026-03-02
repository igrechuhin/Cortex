"""Tests for task locking functionality (Phase 58)."""

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from cortex.core.cache_json_access import read_cache_json, write_cache_json
from cortex.optimization.agent_roles import AgentRole
from cortex.tools.session.task_locking import (
    check_task_available,
    check_task_available_lock,
    claim_task,
    claim_task_lock,
    list_active_locks,
    list_active_tasks,
    release_task,
    release_task_lock,
)
from cortex.tools.session.task_locking_helpers import generate_task_id


class TestGenerateTaskId:
    """Tests for task ID generation."""

    def test_generates_stable_id(self) -> None:
        """Test that same task title generates same ID."""
        # Arrange
        task_title = "Phase 58: Multi-Agent Specialization"

        # Act
        task_id1 = generate_task_id(task_title)
        task_id2 = generate_task_id(task_title)

        # Assert
        assert task_id1 == task_id2
        assert len(task_id1) == 16  # SHA256 hex digest first 16 chars
        assert task_id1.isalnum()

    def test_normalizes_task_title(self) -> None:
        """Test that task title is normalized (case-insensitive)."""
        # Arrange
        task_title1 = "Phase 58: Multi-Agent Specialization"
        task_title2 = "phase 58: multi-agent specialization"

        # Act
        task_id1 = generate_task_id(task_title1)
        task_id2 = generate_task_id(task_title2)

        # Assert
        assert task_id1 == task_id2

    def test_strips_whitespace(self) -> None:
        """Test that whitespace is stripped."""
        # Arrange
        task_title1 = "Phase 58: Multi-Agent Specialization"
        task_title2 = "  Phase 58: Multi-Agent Specialization  "

        # Act
        task_id1 = generate_task_id(task_title1)
        task_id2 = generate_task_id(task_title2)

        # Assert
        assert task_id1 == task_id2

    def test_different_tasks_generate_different_ids(self) -> None:
        """Test that different task titles generate different IDs."""
        # Arrange
        task_title1 = "Phase 58: Multi-Agent Specialization"
        task_title2 = "Phase 59: Different Task"

        # Act
        task_id1 = generate_task_id(task_title1)
        task_id2 = generate_task_id(task_title2)

        # Assert
        assert task_id1 != task_id2


class TestClaimTask:
    """Tests for claiming task locks."""

    @pytest.mark.asyncio
    async def test_claim_task_success(self, tmp_path: Path) -> None:
        """Test successfully claiming a task lock."""
        # Arrange
        task_title = "Phase 58: Multi-Agent Specialization"
        env_key = "CORTEX_SESSION_ID"
        original = os.environ.get(env_key)
        os.environ[env_key] = "test_session_123"

        try:
            # Act
            lock = await claim_task(tmp_path, task_title)

            # Assert
            assert lock is not None
            assert lock.task_title == task_title
            assert lock.agent_session_id == "test_session_123"
            assert lock.task_id == generate_task_id(task_title)
            assert lock.agent_role is None  # No role specified

            # Verify lock is persisted
            locks = await read_cache_json(tmp_path, "locks/active.json")
            assert locks is not None
            assert isinstance(locks, dict)
            assert lock.task_id in locks
        finally:
            if original:
                os.environ[env_key] = original
            else:
                _ = os.environ.pop(env_key, None)

    @pytest.mark.asyncio
    async def test_claim_task_with_role(self, tmp_path: Path) -> None:
        """Test claiming a task lock with agent role."""
        # Arrange
        task_title = "Phase 58: Multi-Agent Specialization"
        agent_role = AgentRole.QUALITY
        env_key = "CORTEX_SESSION_ID"
        original = os.environ.get(env_key)
        os.environ[env_key] = "test_session_123"

        try:
            # Act
            lock = await claim_task(tmp_path, task_title, agent_role=agent_role)

            # Assert
            assert lock is not None
            assert lock.agent_role == agent_role.value
        finally:
            if original:
                os.environ[env_key] = original
            else:
                _ = os.environ.pop(env_key, None)

    @pytest.mark.asyncio
    async def test_claim_task_already_locked(self, tmp_path: Path) -> None:
        """Test that claiming an already locked task returns None."""
        # Arrange
        task_title = "Phase 58: Multi-Agent Specialization"
        env_key = "CORTEX_SESSION_ID"
        original = os.environ.get(env_key)
        os.environ[env_key] = "test_session_123"

        try:
            # Claim lock first time
            first_lock = await claim_task(tmp_path, task_title)
            assert first_lock is not None

            # Act - try to claim again (should fail)
            second_lock = await claim_task(tmp_path, task_title)

            # Assert
            assert second_lock is None
        finally:
            if original:
                os.environ[env_key] = original
            else:
                _ = os.environ.pop(env_key, None)

    @pytest.mark.asyncio
    async def test_claim_task_different_sessions(self, tmp_path: Path) -> None:
        """Test that different sessions cannot claim the same task."""
        # Arrange
        task_title = "Phase 58: Multi-Agent Specialization"
        env_key = "CORTEX_SESSION_ID"
        original = os.environ.get(env_key)
        os.environ[env_key] = "session_1"

        try:
            # First session claims lock
            lock1 = await claim_task(tmp_path, task_title)
            assert lock1 is not None

            # Switch to second session
            os.environ[env_key] = "session_2"

            # Act - second session tries to claim
            lock2 = await claim_task(tmp_path, task_title)

            # Assert
            assert lock2 is None
        finally:
            if original:
                os.environ[env_key] = original
            else:
                _ = os.environ.pop(env_key, None)


class TestReleaseTask:
    """Tests for releasing task locks."""

    @pytest.mark.asyncio
    async def test_release_task_success(self, tmp_path: Path) -> None:
        """Test successfully releasing a task lock."""
        # Arrange
        task_title = "Phase 58: Multi-Agent Specialization"
        env_key = "CORTEX_SESSION_ID"
        original = os.environ.get(env_key)
        os.environ[env_key] = "test_session_123"

        try:
            # Claim lock first
            lock = await claim_task(tmp_path, task_title)
            assert lock is not None

            # Act
            released = await release_task(tmp_path, task_title)

            # Assert
            assert released is True

            # Verify lock is removed
            locks = await read_cache_json(tmp_path, "locks/active.json")
            assert locks is None or lock.task_id not in locks
        finally:
            if original:
                os.environ[env_key] = original
            else:
                _ = os.environ.pop(env_key, None)

    @pytest.mark.asyncio
    async def test_release_task_not_found(self, tmp_path: Path) -> None:
        """Test releasing a lock that doesn't exist."""
        # Arrange
        task_title = "Phase 58: Multi-Agent Specialization"
        env_key = "CORTEX_SESSION_ID"
        original = os.environ.get(env_key)
        os.environ[env_key] = "test_session_123"

        try:
            # Act
            released = await release_task(tmp_path, task_title)

            # Assert
            assert released is False
        finally:
            if original:
                os.environ[env_key] = original
            else:
                _ = os.environ.pop(env_key, None)

    @pytest.mark.asyncio
    async def test_release_task_different_session(self, tmp_path: Path) -> None:
        """Test that a different session cannot release a lock."""
        # Arrange
        task_title = "Phase 58: Multi-Agent Specialization"
        env_key = "CORTEX_SESSION_ID"
        original = os.environ.get(env_key)
        os.environ[env_key] = "session_1"

        try:
            # First session claims lock
            lock = await claim_task(tmp_path, task_title)
            assert lock is not None

            # Switch to second session
            os.environ[env_key] = "session_2"

            # Act - second session tries to release
            released = await release_task(tmp_path, task_title)

            # Assert
            assert released is False

            # Verify lock still exists
            locks = await read_cache_json(tmp_path, "locks/active.json")
            assert locks is not None
            assert lock.task_id in locks
        finally:
            if original:
                os.environ[env_key] = original
            else:
                _ = os.environ.pop(env_key, None)


class TestListActiveLocks:
    """Tests for listing active locks."""

    @pytest.mark.asyncio
    async def test_list_active_locks_empty(self, tmp_path: Path) -> None:
        """Test listing locks when none exist."""
        # Arrange
        env_key = "CORTEX_SESSION_ID"
        original = os.environ.get(env_key)
        os.environ[env_key] = "test_session_123"

        try:
            # Act
            locks = await list_active_locks(tmp_path)

            # Assert
            assert locks == []
        finally:
            if original:
                os.environ[env_key] = original
            else:
                _ = os.environ.pop(env_key, None)

    @pytest.mark.asyncio
    async def test_list_active_locks_multiple(self, tmp_path: Path) -> None:
        """Test listing multiple active locks."""
        # Arrange
        task_title1 = "Phase 58: Multi-Agent Specialization"
        task_title2 = "Phase 59: Different Task"
        env_key = "CORTEX_SESSION_ID"
        original = os.environ.get(env_key)
        os.environ[env_key] = "test_session_123"

        try:
            # Claim two locks
            lock1 = await claim_task(tmp_path, task_title1)
            lock2 = await claim_task(tmp_path, task_title2)
            assert lock1 is not None
            assert lock2 is not None

            # Act
            locks = await list_active_locks(tmp_path)

            # Assert
            assert len(locks) == 2
            task_ids = {lock.task_id for lock in locks}
            assert lock1.task_id in task_ids
            assert lock2.task_id in task_ids
        finally:
            if original:
                os.environ[env_key] = original
            else:
                _ = os.environ.pop(env_key, None)

    @pytest.mark.asyncio
    async def test_list_active_locks_excludes_expired(self, tmp_path: Path) -> None:
        """Test that expired locks are excluded from list."""
        # Arrange
        task_title = "Phase 58: Multi-Agent Specialization"
        env_key = "CORTEX_SESSION_ID"
        original = os.environ.get(env_key)
        os.environ[env_key] = "test_session_123"

        try:
            # Create an expired lock manually
            task_id = generate_task_id(task_title)
            expired_lock = {
                "task_id": task_id,
                "task_title": task_title,
                "agent_session_id": "old_session",
                "locked_at": (datetime.now(UTC) - timedelta(hours=3)).isoformat(),
                "expires_at": (datetime.now(UTC) - timedelta(hours=1)).isoformat(),
                "agent_role": None,
            }
            await write_cache_json(
                tmp_path, "locks/active.json", {task_id: expired_lock}
            )

            # Act
            locks = await list_active_locks(tmp_path)

            # Assert
            assert len(locks) == 0
        finally:
            if original:
                os.environ[env_key] = original
            else:
                _ = os.environ.pop(env_key, None)


class TestCheckTaskAvailable:
    """Tests for checking task availability."""

    @pytest.mark.asyncio
    async def test_check_task_available_unlocked(self, tmp_path: Path) -> None:
        """Test checking availability of unlocked task."""
        # Arrange
        task_title = "Phase 58: Multi-Agent Specialization"
        env_key = "CORTEX_SESSION_ID"
        original = os.environ.get(env_key)
        os.environ[env_key] = "test_session_123"

        try:
            # Act
            available = await check_task_available(tmp_path, task_title)

            # Assert
            assert available is True
        finally:
            if original:
                os.environ[env_key] = original
            else:
                _ = os.environ.pop(env_key, None)

    @pytest.mark.asyncio
    async def test_check_task_available_locked(self, tmp_path: Path) -> None:
        """Test checking availability of locked task."""
        # Arrange
        task_title = "Phase 58: Multi-Agent Specialization"
        env_key = "CORTEX_SESSION_ID"
        original = os.environ.get(env_key)
        os.environ[env_key] = "test_session_123"

        try:
            # Claim lock first
            lock = await claim_task(tmp_path, task_title)
            assert lock is not None

            # Act
            available = await check_task_available(tmp_path, task_title)

            # Assert
            assert available is False
        finally:
            if original:
                os.environ[env_key] = original
            else:
                _ = os.environ.pop(env_key, None)

    @pytest.mark.asyncio
    async def test_check_task_available_expired(self, tmp_path: Path) -> None:
        """Test that expired locks are treated as available."""
        # Arrange
        task_title = "Phase 58: Multi-Agent Specialization"
        env_key = "CORTEX_SESSION_ID"
        original = os.environ.get(env_key)
        os.environ[env_key] = "test_session_123"

        try:
            # Create an expired lock manually
            task_id = generate_task_id(task_title)
            expired_lock = {
                "task_id": task_id,
                "task_title": task_title,
                "agent_session_id": "old_session",
                "locked_at": (datetime.now(UTC) - timedelta(hours=3)).isoformat(),
                "expires_at": (datetime.now(UTC) - timedelta(hours=1)).isoformat(),
                "agent_role": None,
            }
            await write_cache_json(
                tmp_path, "locks/active.json", {task_id: expired_lock}
            )

            # Act
            available = await check_task_available(tmp_path, task_title)

            # Assert
            assert available is True
        finally:
            if original:
                os.environ[env_key] = original
            else:
                _ = os.environ.pop(env_key, None)


class TestLoadLocksRegistryEdgeCases:
    """Tests for _load_locks_registry behavior with malformed cache data."""

    @pytest.mark.asyncio
    async def test_list_active_locks_when_cache_is_not_dict(
        self, tmp_path: Path
    ) -> None:
        """When cache contains non-dict (e.g. list), locks are treated as empty."""
        await write_cache_json(tmp_path, "locks/active.json", [])
        env_key = "CORTEX_SESSION_ID"
        original = os.environ.get(env_key)
        os.environ[env_key] = "test_session_123"
        try:
            locks = await list_active_locks(tmp_path)
            assert locks == []
        finally:
            if original:
                os.environ[env_key] = original
            else:
                _ = os.environ.pop(env_key, None)

    @pytest.mark.asyncio
    async def test_load_locks_registry_skips_non_dict_entry(
        self, tmp_path: Path
    ) -> None:
        """When cache has task_id mapping to non-dict value, that entry is skipped."""
        task_id = generate_task_id("Some Task")
        await write_cache_json(
            tmp_path,
            "locks/active.json",
            {task_id: "not-a-dict"},
        )
        env_key = "CORTEX_SESSION_ID"
        original = os.environ.get(env_key)
        os.environ[env_key] = "test_session_123"
        try:
            locks = await list_active_locks(tmp_path)
            assert locks == []
        finally:
            if original:
                os.environ[env_key] = original
            else:
                _ = os.environ.pop(env_key, None)

    @pytest.mark.asyncio
    async def test_load_locks_registry_skips_invalid_lock_data(
        self, tmp_path: Path
    ) -> None:
        """When cache has entry that fails TaskLock validation, that entry is skipped."""
        await write_cache_json(
            tmp_path,
            "locks/active.json",
            {"bad_id": {"task_id": "bad_id"}},  # missing required fields
        )
        env_key = "CORTEX_SESSION_ID"
        original = os.environ.get(env_key)
        os.environ[env_key] = "test_session_123"
        try:
            locks = await list_active_locks(tmp_path)
            assert locks == []
        finally:
            if original:
                os.environ[env_key] = original
            else:
                _ = os.environ.pop(env_key, None)

    @pytest.mark.asyncio
    async def test_cleanup_expired_locks_skips_invalid_expires_at(
        self, tmp_path: Path
    ) -> None:
        """Locks with invalid expires_at are skipped during cleanup."""
        task_title = "Phase 58: Multi-Agent Specialization"
        task_id = generate_task_id(task_title)
        invalid_expires_lock = {
            "task_id": task_id,
            "task_title": task_title,
            "agent_session_id": "old_session",
            "locked_at": (datetime.now(UTC) - timedelta(hours=1)).isoformat(),
            "expires_at": "not-a-valid-datetime",
            "agent_role": None,
        }
        await write_cache_json(
            tmp_path,
            "locks/active.json",
            {task_id: invalid_expires_lock},
        )
        env_key = "CORTEX_SESSION_ID"
        original = os.environ.get(env_key)
        os.environ[env_key] = "test_session_123"
        try:
            locks = await list_active_locks(tmp_path)
            assert len(locks) == 0
        finally:
            if original:
                os.environ[env_key] = original
            else:
                _ = os.environ.pop(env_key, None)


class TestLockExpiry:
    """Tests for lock expiry functionality."""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_lock_expires_after_timeout(self, tmp_path: Path) -> None:
        """Test that locks expire after timeout."""
        # Arrange
        task_title = "Phase 58: Multi-Agent Specialization"
        env_key = "CORTEX_SESSION_ID"
        original = os.environ.get(env_key)
        os.environ[env_key] = "test_session_123"

        try:
            # Claim lock with very short timeout (1 second = 1/3600 hours)
            lock = await claim_task(
                tmp_path, task_title, lock_timeout_hours=1.0 / 3600.0
            )
            assert lock is not None

            # Verify lock exists
            available = await check_task_available(tmp_path, task_title)
            assert available is False

            # Wait for expiry (using a mock would be better, but this tests real behavior)
            # Note: This test may be flaky in CI, consider mocking time
            import asyncio

            await asyncio.sleep(1.1)  # Wait slightly longer than timeout

            # Act - check availability after expiry
            available_after = await check_task_available(tmp_path, task_title)

            # Assert - lock should be expired and task available
            # Note: This depends on cleanup_expired_locks being called
            # In practice, cleanup happens on every operation
            locks = await list_active_locks(tmp_path)
            # Lock should be cleaned up
            assert len(locks) == 0 or available_after is True
        finally:
            if original:
                os.environ[env_key] = original
            else:
                _ = os.environ.pop(env_key, None)


class TestTaskLockingMCPExceptionPaths:
    """Tests for MCP tool exception handling when resolve_project_root_async raises."""

    @pytest.mark.asyncio
    async def test_claim_task_lock_returns_error_on_resolve_failure(self) -> None:
        """claim_task_lock returns JSON error when project root resolution fails."""
        with patch(
            "cortex.tools.session.task_locking_handlers.resolve_project_root_async",
            new_callable=AsyncMock,
            side_effect=RuntimeError("No project root"),
        ):
            result_str = await claim_task_lock(
                task_title="Some Task",
                role=None,
                ctx=None,
            )
        result = json.loads(result_str)
        assert "error" in result or "status" in result
        assert result.get("status") == "error" or "error" in result

    @pytest.mark.asyncio
    async def test_release_task_lock_returns_error_on_resolve_failure(self) -> None:
        """release_task_lock returns JSON error when project root resolution fails."""
        with patch(
            "cortex.tools.session.task_locking_handlers.resolve_project_root_async",
            new_callable=AsyncMock,
            side_effect=RuntimeError("No project root"),
        ):
            result_str = await release_task_lock(task_title="Some Task", ctx=None)
        result = json.loads(result_str)
        assert result.get("status") == "error"
        assert result.get("released") is False

    @pytest.mark.asyncio
    async def test_list_active_tasks_returns_empty_on_resolve_failure(self) -> None:
        """list_active_tasks returns JSON with empty locks when resolution fails."""
        with patch(
            "cortex.tools.session.task_locking_handlers.resolve_project_root_async",
            new_callable=AsyncMock,
            side_effect=RuntimeError("No project root"),
        ):
            result_str = await list_active_tasks(ctx=None)
        result = json.loads(result_str)
        assert result.get("status") == "success"
        assert result.get("locks", []) == []
        assert result.get("count", 0) == 0

    @pytest.mark.asyncio
    async def test_check_task_available_lock_returns_available_on_resolve_failure(
        self,
    ) -> None:
        """check_task_available_lock treats task as available when resolution fails."""
        with patch(
            "cortex.tools.session.task_locking_handlers.resolve_project_root_async",
            new_callable=AsyncMock,
            side_effect=RuntimeError("No project root"),
        ):
            result_str = await check_task_available_lock(
                task_title="Some Task",
                ctx=None,
            )
        result = json.loads(result_str)
        assert result.get("status") == "success"
        assert result.get("available") is True
        assert result.get("lock") is None
