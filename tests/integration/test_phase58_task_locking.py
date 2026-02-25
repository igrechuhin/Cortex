"""
Integration tests for Phase 58 multi-agent task locking.

Verifies end-to-end behavior when multiple simulated agent sessions
claim and release task locks.
"""

import os
from pathlib import Path

import pytest

from cortex.tools.task_locking import (
    check_task_available,
    claim_task,
    list_active_locks,
    release_task,
)


@pytest.mark.integration
class TestPhase58TwoSessionsClaimDifferentTasks:
    """Integration: two sessions claiming different tasks succeed independently."""

    @pytest.mark.asyncio
    async def test_two_sessions_claim_different_tasks(
        self, temp_project_root: Path
    ) -> None:
        """Session A claims Task 1, Session B claims Task 2; both succeed."""
        env_key = "CORTEX_SESSION_ID"
        original = os.environ.get(env_key)

        try:
            # Arrange: Session A claims Task 1
            os.environ[env_key] = "session_a_123"
            lock_a = await claim_task(temp_project_root, "Phase 58: Multi-Agent")
            assert lock_a is not None
            assert lock_a.agent_session_id == "session_a_123"
            assert lock_a.task_title == "Phase 58: Multi-Agent"

            # Arrange: Session B claims Task 2 (different task)
            os.environ[env_key] = "session_b_456"
            lock_b = await claim_task(temp_project_root, "Phase 59: Tool Consolidation")
            assert lock_b is not None
            assert lock_b.agent_session_id == "session_b_456"
            assert lock_b.task_title == "Phase 59: Tool Consolidation"

            # Assert: both locks are active
            locks = await list_active_locks(temp_project_root)
            assert len(locks) == 2
            task_titles = {lock.task_title for lock in locks}
            assert "Phase 58: Multi-Agent" in task_titles
            assert "Phase 59: Tool Consolidation" in task_titles

            # Assert: each session can release only its own lock
            os.environ[env_key] = "session_a_123"
            released_a = await release_task(temp_project_root, "Phase 58: Multi-Agent")
            assert released_a is True

            os.environ[env_key] = "session_b_456"
            released_b = await release_task(
                temp_project_root, "Phase 59: Tool Consolidation"
            )
            assert released_b is True

            locks_after = await list_active_locks(temp_project_root)
            assert len(locks_after) == 0
        finally:
            if original:
                os.environ[env_key] = original
            else:
                _ = os.environ.pop(env_key, None)


@pytest.mark.integration
class TestPhase58LockConflictResolution:
    """Integration: second session picks different task when first is locked."""

    @pytest.mark.asyncio
    async def test_lock_conflict_second_session_picks_different_task(
        self, temp_project_root: Path
    ) -> None:
        """Session A locks Task 1; Session B fails on Task 1, then claims Task 2."""
        env_key = "CORTEX_SESSION_ID"
        original = os.environ.get(env_key)

        try:
            # Arrange: Session A claims Task 1
            os.environ[env_key] = "session_alpha"
            lock_a = await claim_task(temp_project_root, "Phase 58 Step 1")
            assert lock_a is not None

            # Act: Session B tries to claim Task 1 (should fail)
            os.environ[env_key] = "session_beta"
            lock_b_task1 = await claim_task(temp_project_root, "Phase 58 Step 1")
            assert lock_b_task1 is None

            # Act: Session B checks availability and claims Task 2
            available_task1 = await check_task_available(
                temp_project_root, "Phase 58 Step 1"
            )
            assert available_task1 is False

            available_task2 = await check_task_available(
                temp_project_root, "Phase 58 Step 2"
            )
            assert available_task2 is True

            lock_b_task2 = await claim_task(temp_project_root, "Phase 58 Step 2")
            assert lock_b_task2 is not None
            assert lock_b_task2.agent_session_id == "session_beta"

            # Assert: two locks, one per session
            locks = await list_active_locks(temp_project_root)
            assert len(locks) == 2
            assert {lock.task_title for lock in locks} == {
                "Phase 58 Step 1",
                "Phase 58 Step 2",
            }
        finally:
            if original:
                os.environ[env_key] = original
            else:
                _ = os.environ.pop(env_key, None)
