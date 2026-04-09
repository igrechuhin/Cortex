"""Tests for session registry functionality (Phase 58 Step 4)."""

import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from cortex.core.cache_json_access import read_cache_json, write_cache_json
from cortex.optimization.agent_roles import AgentRole
from cortex.tools.session.registry import (
    deregister_session,
    list_concurrent_sessions,
    register_session,
    session_deregister,
    session_register,
)


def _write_once_cleanup_settings(settings_path: Path) -> None:
    payload = {
        "hooks": {
            "PostToolUse": [
                {
                    "matcher": "Edit",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "python3 -m pytest tests/ -q",
                            "once": True,
                        },
                        {
                            "type": "command",
                            "command": "python3 -m pytest tests/unit -q",
                        },
                    ],
                }
            ]
        }
    }
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    _ = settings_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


class TestRegisterSession:
    """Tests for registering sessions."""

    @pytest.mark.asyncio
    async def test_register_session_success(self, tmp_path: Path) -> None:
        """Test successfully registering a session."""
        # Arrange
        task_title = "Phase 58: Multi-Agent Specialization"
        env_key = "CORTEX_SESSION_ID"
        original = os.environ.get(env_key)
        os.environ[env_key] = "test_session_123"

        try:
            # Act
            session_result = await register_session(tmp_path, task_title)

            # Assert
            assert session_result.task == task_title
            assert session_result.session_id == "test_session_123"
            assert session_result.agent_role is None  # No role specified
            assert session_result.started is not None

            # Verify session is persisted
            data = await read_cache_json(tmp_path, "sessions/active.json")
            assert data is not None
            assert isinstance(data, dict)
            assert "test_session_123" in data
            session_data = data["test_session_123"]
            assert isinstance(session_data, dict)
            assert session_data["task"] == task_title

        finally:
            if original is None:
                _ = os.environ.pop(env_key, None)
            else:
                os.environ[env_key] = original

    @pytest.mark.asyncio
    async def test_register_session_with_role(self, tmp_path: Path) -> None:
        """Test registering a session with agent role."""
        # Arrange
        task_title = "Fix lint errors"
        env_key = "CORTEX_SESSION_ID"
        original = os.environ.get(env_key)
        os.environ[env_key] = "test_session_456"

        try:
            # Act
            session_result = await register_session(
                tmp_path, task_title, agent_role=AgentRole.QUALITY
            )

            # Assert
            assert session_result.task == task_title
            assert session_result.session_id == "test_session_456"
            assert session_result.agent_role == "quality"

        finally:
            if original is None:
                _ = os.environ.pop(env_key, None)
            else:
                os.environ[env_key] = original

    @pytest.mark.asyncio
    async def test_register_multiple_sessions(self, tmp_path: Path) -> None:
        """Test registering multiple sessions."""
        # Arrange
        env_key = "CORTEX_SESSION_ID"
        original = os.environ.get(env_key)

        try:
            # Act - Register first session
            os.environ[env_key] = "session_1"
            session1 = await register_session(
                tmp_path, "Task 1", agent_role=AgentRole.FEATURE
            )

            # Register second session
            os.environ[env_key] = "session_2"
            session2 = await register_session(
                tmp_path, "Task 2", agent_role=AgentRole.QUALITY
            )

            # Assert
            assert session1.session_id == "session_1"
            assert session2.session_id == "session_2"

            # Verify both sessions are persisted
            data = await read_cache_json(tmp_path, "sessions/active.json")
            assert data is not None
            assert "session_1" in data
            assert "session_2" in data
            assert len(data) == 2

        finally:
            if original is None:
                _ = os.environ.pop(env_key, None)
            else:
                os.environ[env_key] = original


class TestDeregisterSession:
    """Tests for deregistering sessions."""

    @pytest.mark.asyncio
    async def test_deregister_session_success(self, tmp_path: Path) -> None:
        """Test successfully deregistering a session."""
        # Arrange
        task_title = "Phase 58: Multi-Agent Specialization"
        env_key = "CORTEX_SESSION_ID"
        original = os.environ.get(env_key)
        os.environ[env_key] = "test_session_789"

        try:
            # Register session first
            _ = await register_session(tmp_path, task_title)

            # Act
            result = await deregister_session(tmp_path)

            # Assert
            assert result is True

            # Verify session is removed
            data = await read_cache_json(tmp_path, "sessions/active.json")
            assert data is None or "test_session_789" not in data

        finally:
            if original is None:
                _ = os.environ.pop(env_key, None)
            else:
                os.environ[env_key] = original

    @pytest.mark.asyncio
    async def test_deregister_nonexistent_session(self, tmp_path: Path) -> None:
        """Test deregistering a session that doesn't exist."""
        # Arrange
        env_key = "CORTEX_SESSION_ID"
        original = os.environ.get(env_key)
        os.environ[env_key] = "nonexistent_session"

        try:
            # Act
            result = await deregister_session(tmp_path)

            # Assert
            assert result is False

        finally:
            if original is None:
                _ = os.environ.pop(env_key, None)
            else:
                os.environ[env_key] = original

    @pytest.mark.asyncio
    async def test_deregister_only_current_session(self, tmp_path: Path) -> None:
        """Test that deregistering only removes current session."""
        # Arrange
        env_key = "CORTEX_SESSION_ID"
        original = os.environ.get(env_key)

        try:
            # Register two sessions
            os.environ[env_key] = "session_a"
            _ = await register_session(tmp_path, "Task A")

            os.environ[env_key] = "session_b"
            _ = await register_session(tmp_path, "Task B")

            # Act - Deregister session_b
            result = await deregister_session(tmp_path)

            # Assert
            assert result is True

            # Verify session_b is removed but session_a remains
            data = await read_cache_json(tmp_path, "sessions/active.json")
            assert data is not None
            assert "session_a" in data
            assert "session_b" not in data

        finally:
            if original is None:
                _ = os.environ.pop(env_key, None)
            else:
                os.environ[env_key] = original


class TestLoadSessionsRegistryEdgeCases:
    """Tests for _load_sessions_registry behavior with malformed cache data."""

    @pytest.mark.asyncio
    async def test_list_sessions_when_cache_is_not_dict(self, tmp_path: Path) -> None:
        """When cache contains non-dict (e.g. list), sessions are treated as empty."""
        await write_cache_json(tmp_path, "sessions/active.json", [])
        sessions = await list_concurrent_sessions(tmp_path)
        assert sessions == []

    @pytest.mark.asyncio
    async def test_load_sessions_registry_skips_non_dict_entry(
        self, tmp_path: Path
    ) -> None:
        """When cache has session_id mapping to non-dict value, that entry is skipped."""
        await write_cache_json(
            tmp_path,
            "sessions/active.json",
            {"session_1": "not-a-dict"},
        )
        sessions = await list_concurrent_sessions(tmp_path)
        assert sessions == []

    @pytest.mark.asyncio
    async def test_load_sessions_registry_skips_invalid_session_data(
        self, tmp_path: Path
    ) -> None:
        """When cache has entry that fails ConcurrentSession validation, that entry is skipped."""
        await write_cache_json(
            tmp_path,
            "sessions/active.json",
            {"bad_id": {"session_id": "bad_id"}},  # missing required fields
        )
        sessions = await list_concurrent_sessions(tmp_path)
        assert sessions == []


class TestListConcurrentSessions:
    """Tests for listing concurrent sessions."""

    @pytest.mark.asyncio
    async def test_list_empty_registry(self, tmp_path: Path) -> None:
        """Test listing sessions when registry is empty."""
        # Act
        sessions = await list_concurrent_sessions(tmp_path)

        # Assert
        assert sessions == []

    @pytest.mark.asyncio
    async def test_list_excludes_current_session(self, tmp_path: Path) -> None:
        """Test that current session is excluded from results."""
        # Arrange
        env_key = "CORTEX_SESSION_ID"
        original = os.environ.get(env_key)

        try:
            # Register current session
            os.environ[env_key] = "current_session"
            _ = await register_session(tmp_path, "Current Task")

            # Register another session
            os.environ[env_key] = "other_session"
            _ = await register_session(tmp_path, "Other Task")

            # Act - List from current_session perspective
            os.environ[env_key] = "current_session"
            sessions = await list_concurrent_sessions(tmp_path, exclude_current=True)

            # Assert
            assert len(sessions) == 1
            assert sessions[0].session_id == "other_session"
            assert sessions[0].task == "Other Task"

        finally:
            if original is None:
                _ = os.environ.pop(env_key, None)
            else:
                os.environ[env_key] = original

    @pytest.mark.asyncio
    async def test_list_includes_current_session_when_requested(
        self, tmp_path: Path
    ) -> None:
        """Test that current session is included when exclude_current=False."""
        # Arrange
        env_key = "CORTEX_SESSION_ID"
        original = os.environ.get(env_key)

        try:
            # Register current session
            os.environ[env_key] = "current_session"
            _ = await register_session(tmp_path, "Current Task")

            # Act
            sessions = await list_concurrent_sessions(tmp_path, exclude_current=False)

            # Assert
            assert len(sessions) == 1
            assert sessions[0].session_id == "current_session"

        finally:
            if original is None:
                _ = os.environ.pop(env_key, None)
            else:
                os.environ[env_key] = original

    @pytest.mark.asyncio
    async def test_list_multiple_sessions(self, tmp_path: Path) -> None:
        """Test listing multiple concurrent sessions."""
        # Arrange
        env_key = "CORTEX_SESSION_ID"
        original = os.environ.get(env_key)

        try:
            # Register multiple sessions
            os.environ[env_key] = "session_1"
            _ = await register_session(tmp_path, "Task 1", agent_role=AgentRole.FEATURE)

            os.environ[env_key] = "session_2"
            _ = await register_session(tmp_path, "Task 2", agent_role=AgentRole.QUALITY)

            os.environ[env_key] = "session_3"
            _ = await register_session(tmp_path, "Task 3", agent_role=AgentRole.TESTING)

            # Act - List from session_1 perspective
            os.environ[env_key] = "session_1"
            sessions = await list_concurrent_sessions(tmp_path, exclude_current=True)

            # Assert
            assert len(sessions) == 2
            session_ids = {s.session_id for s in sessions}
            assert session_ids == {"session_2", "session_3"}

        finally:
            if original is None:
                _ = os.environ.pop(env_key, None)
            else:
                os.environ[env_key] = original


class TestSessionRegistryMCPExceptionPaths:
    """Tests for MCP tool exception handling when resolve_project_root_async raises."""

    @pytest.mark.asyncio
    async def test_session_register_returns_error_on_resolve_failure(self) -> None:
        """session_register returns JSON error when project root resolution fails."""
        with patch(
            "cortex.tools.session.registry.resolve_project_root_async",
            new_callable=AsyncMock,
            side_effect=RuntimeError("No project root"),
        ):
            result_str = await session_register(
                task_title="Some Task",
                role=None,
                ctx=None,
            )
        result = json.loads(result_str)
        assert result.get("status") == "error"
        assert "error" in result

    @pytest.mark.asyncio
    async def test_session_deregister_returns_error_on_resolve_failure(self) -> None:
        """session_deregister returns JSON error when project root resolution fails."""
        with patch(
            "cortex.tools.session.registry.resolve_project_root_async",
            new_callable=AsyncMock,
            side_effect=RuntimeError("No project root"),
        ):
            result_str = await session_deregister(ctx=None)
        result = json.loads(result_str)
        assert result.get("status") == "error"
        assert "error" in result

    @pytest.mark.asyncio
    async def test_session_deregister_cleans_once_hooks(self, tmp_path: Path) -> None:
        """session_deregister removes leftover once hooks from .claude/settings.json."""
        settings_path = tmp_path / ".claude" / "settings.json"
        _write_once_cleanup_settings(settings_path)
        env_key = "CORTEX_SESSION_ID"
        original = os.environ.get(env_key)
        os.environ[env_key] = "cleanup_session"

        try:
            _ = await register_session(tmp_path, "cleanup task")
            with patch(
                "cortex.tools.session.registry.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=tmp_path,
            ):
                result_str = await session_deregister(ctx=None)
            result = json.loads(result_str)
            assert result.get("status") == "success"
            cleaned = json.loads(settings_path.read_text(encoding="utf-8"))
            hooks = cleaned["hooks"]["PostToolUse"][0]["hooks"]
            assert hooks == [
                {"type": "command", "command": "python3 -m pytest tests/unit -q"}
            ]
        finally:
            if original is None:
                _ = os.environ.pop(env_key, None)
            else:
                os.environ[env_key] = original
