"""Tests for session logging functionality."""

import json
import os
from pathlib import Path

from cortex.core.session_logger import (
    get_session_id,
    get_session_log_path,
    list_session_logs,
    log_load_context_call,
    read_session_log,
)


class TestGetSessionId:
    """Tests for session ID generation."""

    def test_generates_session_id(self) -> None:
        """Test that a session ID is generated when not set."""
        # Arrange - ensure env var is not set
        env_key = "CORTEX_SESSION_ID"
        original = os.environ.pop(env_key, None)

        try:
            # Act
            session_id = get_session_id()

            # Assert
            assert session_id is not None
            assert len(session_id) == 12  # UUID hex[:12]
            assert session_id.isalnum()
        finally:
            # Cleanup
            if original:
                os.environ[env_key] = original
            else:
                _ = os.environ.pop(env_key, None)

    def test_returns_existing_session_id(self) -> None:
        """Test that existing session ID is returned."""
        # Arrange
        env_key = "CORTEX_SESSION_ID"
        original = os.environ.get(env_key)
        os.environ[env_key] = "test_session_123"

        try:
            # Act
            session_id = get_session_id()

            # Assert
            assert session_id == "test_session_123"
        finally:
            # Cleanup
            if original:
                os.environ[env_key] = original
            else:
                _ = os.environ.pop(env_key, None)

    def test_persists_across_calls(self) -> None:
        """Test that session ID persists across multiple calls."""
        # Arrange - ensure env var is not set
        env_key = "CORTEX_SESSION_ID"
        original = os.environ.pop(env_key, None)

        try:
            # Act
            first_id = get_session_id()
            second_id = get_session_id()

            # Assert - same ID returned
            assert first_id == second_id
        finally:
            # Cleanup
            if original:
                os.environ[env_key] = original
            else:
                _ = os.environ.pop(env_key, None)


class TestGetSessionLogPath:
    """Tests for session log path generation."""

    def test_returns_correct_path(self, tmp_path: Path) -> None:
        """Test that correct log path is returned."""
        # Arrange
        env_key = "CORTEX_SESSION_ID"
        original = os.environ.get(env_key)
        os.environ[env_key] = "path_test_123"

        try:
            # Act
            log_path = get_session_log_path(tmp_path)

            # Assert
            expected = (
                tmp_path / ".cortex" / ".session" / "context-session-path_test_123.json"
            )
            assert log_path == expected
        finally:
            # Cleanup
            if original:
                os.environ[env_key] = original
            else:
                _ = os.environ.pop(env_key, None)

    def test_path_uses_current_session_id(self, tmp_path: Path) -> None:
        """Test that path uses the current session ID."""
        # Arrange
        env_key = "CORTEX_SESSION_ID"
        original = os.environ.get(env_key)
        os.environ[env_key] = "session_abc"

        try:
            # Act
            session_id = get_session_id()
            log_path = get_session_log_path(tmp_path)

            # Assert - path contains the session ID
            assert session_id in log_path.name
        finally:
            # Cleanup
            if original:
                os.environ[env_key] = original
            else:
                _ = os.environ.pop(env_key, None)


class TestLogLoadContextCall:
    """Tests for logging load_context calls."""

    def test_creates_session_log(self, tmp_path: Path) -> None:
        """Test that session log is created."""
        # Arrange
        env_key = "CORTEX_SESSION_ID"
        original = os.environ.get(env_key)
        os.environ[env_key] = "log_test_123"

        try:
            # Act
            log_load_context_call(
                project_root=tmp_path,
                task_description="Test task",
                token_budget=5000,
                strategy="dependency_aware",
                selected_files=["file1.md", "file2.md"],
                selected_sections={},
                total_tokens=1000,
                utilization=0.2,
                excluded_files=["file3.md"],
                relevance_scores={"file1.md": 0.8, "file2.md": 0.6},
            )

            # Assert - use public API to get path
            log_path = get_session_log_path(tmp_path)
            assert log_path.exists()

            with open(log_path) as f:
                log_data = json.load(f)

            assert log_data["session_id"] == "log_test_123"
            assert len(log_data["load_context_calls"]) == 1
            assert log_data["load_context_calls"][0]["task_description"] == "Test task"
        finally:
            # Cleanup
            if original:
                os.environ[env_key] = original
            else:
                _ = os.environ.pop(env_key, None)

    def test_appends_to_existing_log(self, tmp_path: Path) -> None:
        """Test that multiple calls append to same log."""
        # Arrange
        env_key = "CORTEX_SESSION_ID"
        original = os.environ.get(env_key)
        os.environ[env_key] = "append_test_123"

        try:
            # Act - first call
            log_load_context_call(
                project_root=tmp_path,
                task_description="First task",
                token_budget=5000,
                strategy="priority",
                selected_files=["file1.md"],
                selected_sections={},
                total_tokens=500,
                utilization=0.1,
                excluded_files=[],
                relevance_scores={"file1.md": 0.9},
            )

            # Act - second call
            log_load_context_call(
                project_root=tmp_path,
                task_description="Second task",
                token_budget=10000,
                strategy="hybrid",
                selected_files=["file2.md"],
                selected_sections={},
                total_tokens=2000,
                utilization=0.2,
                excluded_files=["file1.md"],
                relevance_scores={"file2.md": 0.7},
            )

            # Assert - use public API to get path
            log_path = get_session_log_path(tmp_path)
            with open(log_path) as f:
                log_data = json.load(f)

            assert len(log_data["load_context_calls"]) == 2
            assert log_data["load_context_calls"][0]["task_description"] == "First task"
            assert (
                log_data["load_context_calls"][1]["task_description"] == "Second task"
            )
        finally:
            # Cleanup
            if original:
                os.environ[env_key] = original
            else:
                _ = os.environ.pop(env_key, None)


class TestListSessionLogs:
    """Tests for listing session logs."""

    def test_returns_empty_when_no_logs(self, tmp_path: Path) -> None:
        """Test that empty list is returned when no logs exist."""
        # Act
        logs = list_session_logs(tmp_path)

        # Assert
        assert logs == []

    def test_returns_log_files(self, tmp_path: Path) -> None:
        """Test that log files are returned."""
        # Arrange
        session_dir = tmp_path / ".cortex" / ".session"
        _ = session_dir.mkdir(parents=True)
        _ = (session_dir / "context-session-abc123.json").write_text("{}")
        _ = (session_dir / "context-session-def456.json").write_text("{}")

        # Act
        logs = list_session_logs(tmp_path)

        # Assert
        assert len(logs) == 2
        assert all(p.name.startswith("context-session-") for p in logs)


class TestReadSessionLog:
    """Tests for reading session logs."""

    def test_returns_none_for_nonexistent(self, tmp_path: Path) -> None:
        """Test that None is returned for non-existent file."""
        # Arrange
        log_path = tmp_path / "nonexistent.json"

        # Act
        result = read_session_log(log_path)

        # Assert
        assert result is None

    def test_reads_session_log(self, tmp_path: Path) -> None:
        """Test that session log is read correctly."""
        # Arrange
        log_path = tmp_path / "test-log.json"
        log_data: dict[str, str | list[object]] = {
            "session_id": "read_test",
            "session_start": "2026-01-21T10:00",
            "load_context_calls": [],
        }
        _ = log_path.write_text(json.dumps(log_data))

        # Act
        result = read_session_log(log_path)

        # Assert
        assert result is not None
        assert result["session_id"] == "read_test"
