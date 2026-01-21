"""Tests for context analysis functionality."""

import json
import os
from pathlib import Path
from typing import cast

from cortex.tools.context_analysis_operations import (
    analyze_current_session,
    analyze_session_logs,
    get_context_statistics,
)


class TestAnalyzeSessionLogs:
    """Tests for session log analysis."""

    def test_returns_no_data_when_empty(self, tmp_path: Path) -> None:
        """Test that no_data status is returned when no logs exist."""
        # Act
        result = analyze_session_logs(tmp_path)

        # Assert
        assert result["status"] == "no_data"

    def test_analyzes_session_logs(self, tmp_path: Path) -> None:
        """Test that session logs are analyzed."""
        # Arrange
        session_dir = tmp_path / ".cortex" / ".session"
        _ = session_dir.mkdir(parents=True)

        log_data: dict[str, object] = {
            "session_id": "test_session",
            "session_start": "2026-01-21T10:00",
            "load_context_calls": [
                {
                    "timestamp": "2026-01-21T10:05",
                    "task_description": "Fix bug",
                    "token_budget": 5000,
                    "strategy": "dependency_aware",
                    "selected_files": ["file1.md"],
                    "selected_sections": {},
                    "total_tokens": 1000,
                    "utilization": 0.2,
                    "excluded_files": [],
                    "relevance_scores": {"file1.md": 0.8},
                }
            ],
        }
        _ = (session_dir / "context-session-test_session.json").write_text(
            json.dumps(log_data)
        )

        # Act
        result = analyze_session_logs(tmp_path)

        # Assert
        assert result["status"] == "success"
        assert result["new_sessions_analyzed"] == 1
        assert result["new_entries_added"] == 1

    def test_skips_already_analyzed_sessions(self, tmp_path: Path) -> None:
        """Test that already analyzed sessions are skipped."""
        # Arrange
        session_dir = tmp_path / ".cortex" / ".session"
        _ = session_dir.mkdir(parents=True)

        log_data: dict[str, object] = {
            "session_id": "existing_session",
            "session_start": "2026-01-21T10:00",
            "load_context_calls": [
                {
                    "timestamp": "2026-01-21T10:05",
                    "task_description": "Fix bug",
                    "token_budget": 5000,
                    "strategy": "dependency_aware",
                    "selected_files": ["file1.md"],
                    "selected_sections": {},
                    "total_tokens": 1000,
                    "utilization": 0.2,
                    "excluded_files": [],
                    "relevance_scores": {"file1.md": 0.8},
                }
            ],
        }
        _ = (session_dir / "context-session-existing_session.json").write_text(
            json.dumps(log_data)
        )

        # First analysis
        _ = analyze_session_logs(tmp_path)

        # Act - second analysis should skip
        result = analyze_session_logs(tmp_path)

        # Assert
        assert result["new_sessions_analyzed"] == 0
        assert result["new_entries_added"] == 0

    def test_extracts_task_patterns(self, tmp_path: Path) -> None:
        """Test that task patterns are extracted correctly."""
        # Arrange
        session_dir = tmp_path / ".cortex" / ".session"
        _ = session_dir.mkdir(parents=True)

        log_data: dict[str, object] = {
            "session_id": "pattern_test",
            "session_start": "2026-01-21T10:00",
            "load_context_calls": [
                {
                    "timestamp": "2026-01-21T10:05",
                    "task_description": "Fix security vulnerability",
                    "token_budget": 5000,
                    "strategy": "dependency_aware",
                    "selected_files": ["file1.md"],
                    "selected_sections": {},
                    "total_tokens": 1000,
                    "utilization": 0.2,
                    "excluded_files": [],
                    "relevance_scores": {"file1.md": 0.8},
                },
                {
                    "timestamp": "2026-01-21T10:10",
                    "task_description": "Implement new feature",
                    "token_budget": 5000,
                    "strategy": "dependency_aware",
                    "selected_files": ["file2.md"],
                    "selected_sections": {},
                    "total_tokens": 1500,
                    "utilization": 0.3,
                    "excluded_files": [],
                    "relevance_scores": {"file2.md": 0.7},
                },
            ],
        }
        _ = (session_dir / "context-session-pattern_test.json").write_text(
            json.dumps(log_data)
        )

        # Act
        result = analyze_session_logs(tmp_path)

        # Assert
        assert result["status"] == "success"
        statistics = cast(dict[str, object], result["statistics"])
        patterns = cast(dict[str, int], statistics["common_task_patterns"])
        assert "security" in patterns
        assert "implement/add" in patterns


class TestAnalyzeCurrentSession:
    """Tests for current session analysis."""

    def test_returns_no_data_when_no_calls(self, tmp_path: Path) -> None:
        """Test that no_data status is returned when no calls in session."""
        # Arrange
        env_key = "CORTEX_SESSION_ID"
        original = os.environ.get(env_key)
        os.environ[env_key] = "current_test_empty"

        try:
            # Act
            result = analyze_current_session(tmp_path)

            # Assert
            assert result["status"] == "no_data"
            assert result["session_id"] == "current_test_empty"
        finally:
            if original:
                os.environ[env_key] = original
            else:
                _ = os.environ.pop(env_key, None)

    def test_analyzes_current_session(self, tmp_path: Path) -> None:
        """Test that current session is analyzed correctly."""
        # Arrange
        env_key = "CORTEX_SESSION_ID"
        original = os.environ.get(env_key)
        os.environ[env_key] = "current_test_123"

        session_dir = tmp_path / ".cortex" / ".session"
        _ = session_dir.mkdir(parents=True)

        log_data: dict[str, object] = {
            "session_id": "current_test_123",
            "session_start": "2026-01-21T10:00",
            "load_context_calls": [
                {
                    "timestamp": "2026-01-21T10:05",
                    "task_description": "Fix bug",
                    "token_budget": 5000,
                    "strategy": "dependency_aware",
                    "selected_files": ["file1.md", "file2.md"],
                    "selected_sections": {},
                    "total_tokens": 2000,
                    "utilization": 0.4,
                    "excluded_files": [],
                    "relevance_scores": {"file1.md": 0.8, "file2.md": 0.6},
                }
            ],
        }
        _ = (session_dir / "context-session-current_test_123.json").write_text(
            json.dumps(log_data)
        )

        try:
            # Act
            result = analyze_current_session(tmp_path)

            # Assert
            assert result["status"] == "success"
            assert result["session_id"] == "current_test_123"
            current = cast(dict[str, object], result["current_session"])
            assert current["calls_analyzed"] == 1
            assert result["global_statistics_updated"] is True
        finally:
            if original:
                os.environ[env_key] = original
            else:
                _ = os.environ.pop(env_key, None)

    def test_calculates_session_statistics(self, tmp_path: Path) -> None:
        """Test that session statistics are calculated correctly."""
        # Arrange
        env_key = "CORTEX_SESSION_ID"
        original = os.environ.get(env_key)
        os.environ[env_key] = "stats_test_123"

        session_dir = tmp_path / ".cortex" / ".session"
        _ = session_dir.mkdir(parents=True)

        log_data: dict[str, object] = {
            "session_id": "stats_test_123",
            "session_start": "2026-01-21T10:00",
            "load_context_calls": [
                {
                    "timestamp": "2026-01-21T10:05",
                    "task_description": "Fix bug",
                    "token_budget": 5000,
                    "strategy": "dependency_aware",
                    "selected_files": ["file1.md", "file2.md"],
                    "selected_sections": {},
                    "total_tokens": 2000,
                    "utilization": 0.4,
                    "excluded_files": ["file3.md"],
                    "relevance_scores": {"file1.md": 0.8, "file2.md": 0.6},
                },
                {
                    "timestamp": "2026-01-21T10:10",
                    "task_description": "Add feature",
                    "token_budget": 10000,
                    "strategy": "dependency_aware",
                    "selected_files": ["file1.md"],
                    "selected_sections": {},
                    "total_tokens": 6000,
                    "utilization": 0.6,
                    "excluded_files": [],
                    "relevance_scores": {"file1.md": 0.9},
                },
            ],
        }
        _ = (session_dir / "context-session-stats_test_123.json").write_text(
            json.dumps(log_data)
        )

        try:
            # Act
            result = analyze_current_session(tmp_path)

            # Assert
            assert result["status"] == "success"
            current = cast(dict[str, object], result["current_session"])
            stats = cast(dict[str, object], current["statistics"])
            assert stats["calls_count"] == 2
            assert stats["avg_token_utilization"] == 0.5  # (0.4 + 0.6) / 2
            assert stats["avg_files_selected"] == 1.5  # (2 + 1) / 2
        finally:
            if original:
                os.environ[env_key] = original
            else:
                _ = os.environ.pop(env_key, None)


class TestGetContextStatistics:
    """Tests for getting context statistics."""

    def test_returns_no_data_when_empty(self, tmp_path: Path) -> None:
        """Test that no_data status is returned when no stats exist."""
        # Act
        result = get_context_statistics(tmp_path)

        # Assert
        assert result["status"] == "no_data"

    def test_returns_statistics(self, tmp_path: Path) -> None:
        """Test that statistics are returned."""
        # Arrange
        session_dir = tmp_path / ".cortex" / ".session"
        _ = session_dir.mkdir(parents=True)

        stats_data: dict[str, object] = {
            "last_updated": "2026-01-21T10:00",
            "total_sessions_analyzed": 5,
            "total_load_context_calls": 10,
            "avg_token_utilization": 0.65,
            "avg_files_selected": 3.5,
            "avg_relevance_score": 0.72,
            "common_task_patterns": {"fix/debug": 5, "implement/add": 3},
            "entries": [],
        }
        _ = (session_dir / "context-usage-statistics.json").write_text(
            json.dumps(stats_data)
        )

        # Act
        result = get_context_statistics(tmp_path)

        # Assert
        assert result["status"] == "success"
        assert result["total_sessions"] == 5
        assert result["total_calls"] == 10
        statistics = cast(dict[str, object], result["statistics"])
        assert statistics["avg_token_utilization"] == 0.65
