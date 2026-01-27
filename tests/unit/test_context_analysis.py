"""Tests for context analysis functionality."""

import json
import os
from pathlib import Path
from typing import cast

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.context_analysis_operations import (
    analyze_current_session,
    analyze_session_logs,
    get_context_statistics,
)
from cortex.tools.models import ContextUsageEntry


class TestAnalyzeSessionLogs:
    """Tests for session log analysis."""

    def test_returns_no_data_when_empty(self, tmp_path: Path) -> None:
        """Test that no_data status is returned when no logs exist."""
        # Act
        result = analyze_session_logs(tmp_path)

        # Assert
        assert result.status == "no_data"

    def test_analyzes_session_logs(self, tmp_path: Path) -> None:
        """Test that session logs are analyzed."""
        # Arrange
        session_dir = get_cortex_path(tmp_path, CortexResourceType.SESSION)
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
        assert result.status == "success"
        assert result.new_sessions_analyzed == 1
        assert result.new_entries_added == 1

    def test_skips_already_analyzed_sessions(self, tmp_path: Path) -> None:
        """Test that already analyzed sessions are skipped."""
        # Arrange
        session_dir = get_cortex_path(tmp_path, CortexResourceType.SESSION)
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
        assert result.new_sessions_analyzed == 0
        assert result.new_entries_added == 0

    def test_extracts_task_patterns(self, tmp_path: Path) -> None:
        """Test that task patterns are extracted correctly."""
        # Arrange
        session_dir = get_cortex_path(tmp_path, CortexResourceType.SESSION)
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
        assert result.status == "success"
        statistics_raw = result.statistics
        assert statistics_raw is not None
        statistics = cast(dict[str, object], statistics_raw.model_dump(mode="python"))
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
            assert result.status == "no_data"
            assert result.session_id == "current_test_empty"
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

        session_dir = get_cortex_path(tmp_path, CortexResourceType.SESSION)
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
            assert result.status == "success"
            assert result.session_id == "current_test_123"
            current_raw = result.current_session
            assert current_raw is not None
            current = cast(dict[str, object], current_raw.model_dump(mode="python"))
            assert current["calls_analyzed"] == 1
            assert result.global_statistics_updated is True
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

        session_dir = get_cortex_path(tmp_path, CortexResourceType.SESSION)
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
            assert result.status == "success"
            current_raw = result.current_session
            assert current_raw is not None
            current = cast(dict[str, object], current_raw.model_dump(mode="python"))
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
        assert result.status == "no_data"

    def test_returns_statistics(self, tmp_path: Path) -> None:
        """Test that statistics are returned."""
        # Arrange
        session_dir = get_cortex_path(tmp_path, CortexResourceType.SESSION)
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
        assert result.status == "success"
        assert result.total_sessions == 5
        assert result.total_calls == 10
        statistics_raw = result.statistics
        assert statistics_raw is not None
        statistics = cast(dict[str, object], statistics_raw.model_dump(mode="python"))
        assert statistics["avg_token_utilization"] == 0.65


class TestInsightGeneration:
    """Tests for insight generation functionality."""

    def _create_entry(
        self,
        task: str = "Fix bug",
        budget: int = 5000,
        tokens: int = 2000,
        files: list[str] | None = None,
        relevances: dict[str, float] | None = None,
    ) -> ContextUsageEntry:
        """Create a test entry."""
        if files is None:
            files = ["file1.md"]
        if relevances is None:
            relevances = {"file1.md": 0.8}
        return ContextUsageEntry(
            session_id="test",
            timestamp="2026-01-21T10:00",
            task_description=task,
            token_budget=budget,
            total_tokens=tokens,
            utilization=tokens / budget,
            files_selected=len(files),
            files_excluded=0,
            avg_relevance_score=sum(relevances.values()) / len(relevances),
            files_with_high_relevance=sum(1 for v in relevances.values() if v > 0.7),
            files_with_low_relevance=sum(1 for v in relevances.values() if v < 0.3),
            selected_file_names=files,
            relevance_by_file=relevances,
        )

    def test_task_notes_low_utilization_via_insights(self, tmp_path: Path) -> None:
        """Test notes for low utilization through insights."""
        # Arrange
        session_dir = get_cortex_path(tmp_path, CortexResourceType.SESSION)
        _ = session_dir.mkdir(parents=True)

        log_data: dict[str, object] = {
            "session_id": "low_util_test",
            "session_start": "2026-01-21T10:00",
            "load_context_calls": [
                {
                    "timestamp": "2026-01-21T10:05",
                    "task_description": "Fix bug",
                    "token_budget": 10000,
                    "strategy": "dependency_aware",
                    "selected_files": ["file1.md"],
                    "selected_sections": {},
                    "total_tokens": 2000,  # Low utilization (0.2)
                    "utilization": 0.2,
                    "excluded_files": [],
                    "relevance_scores": {"file1.md": 0.8},
                }
            ],
        }
        _ = (session_dir / "context-session-low_util_test.json").write_text(
            json.dumps(log_data)
        )

        # Act
        result = analyze_session_logs(tmp_path)

        # Assert
        assert result.status == "success"
        insights_raw = result.insights
        assert insights_raw is not None
        insights = cast(dict[str, object], insights_raw.model_dump(mode="python"))
        task_recs = cast(dict[str, object], insights["task_type_recommendations"])
        fix_debug = cast(dict[str, object], task_recs.get("fix/debug", {}))
        notes = cast(str, fix_debug.get("notes", ""))
        assert "Low utilization" in notes or "smaller token budgets" in notes.lower()

    def test_file_effectiveness_via_insights(self, tmp_path: Path) -> None:
        """Test file effectiveness through insights."""
        # Arrange
        session_dir = get_cortex_path(tmp_path, CortexResourceType.SESSION)
        _ = session_dir.mkdir(parents=True)

        log_data: dict[str, object] = {
            "session_id": "file_eff_test",
            "session_start": "2026-01-21T10:00",
            "load_context_calls": [
                {
                    "timestamp": "2026-01-21T10:05",
                    "task_description": "Fix bug",
                    "token_budget": 10000,
                    "strategy": "dependency_aware",
                    "selected_files": ["high_relevance.md", "low_relevance.md"],
                    "selected_sections": {},
                    "total_tokens": 5000,
                    "utilization": 0.5,
                    "excluded_files": [],
                    "relevance_scores": {
                        "high_relevance.md": 0.9,
                        "low_relevance.md": 0.3,
                    },
                },
                {
                    "timestamp": "2026-01-21T10:10",
                    "task_description": "Fix another bug",
                    "token_budget": 10000,
                    "strategy": "dependency_aware",
                    "selected_files": ["high_relevance.md"],
                    "selected_sections": {},
                    "total_tokens": 4000,
                    "utilization": 0.4,
                    "excluded_files": [],
                    "relevance_scores": {"high_relevance.md": 0.85},
                },
            ],
        }
        _ = (session_dir / "context-session-file_eff_test.json").write_text(
            json.dumps(log_data)
        )

        # Act
        result = analyze_session_logs(tmp_path)

        # Assert
        assert result.status == "success"
        insights_raw = result.insights
        assert insights_raw is not None
        insights = cast(dict[str, object], insights_raw.model_dump(mode="python"))
        file_eff = cast(dict[str, object], insights["file_effectiveness"])
        assert "high_relevance.md" in file_eff
        assert "low_relevance.md" in file_eff
        high_eff = cast(dict[str, object], file_eff["high_relevance.md"])
        low_eff = cast(dict[str, object], file_eff["low_relevance.md"])
        assert high_eff["times_selected"] == 2
        assert low_eff["times_selected"] == 1
        assert cast(float, high_eff["avg_relevance"]) > cast(
            float, low_eff["avg_relevance"]
        )

    def test_task_type_insights_via_statistics(self, tmp_path: Path) -> None:
        """Test task type insights through statistics."""
        # Arrange
        session_dir = get_cortex_path(tmp_path, CortexResourceType.SESSION)
        _ = session_dir.mkdir(parents=True)

        log_data: dict[str, object] = {
            "session_id": "task_type_test",
            "session_start": "2026-01-21T10:00",
            "load_context_calls": [
                {
                    "timestamp": "2026-01-21T10:05",
                    "task_description": "Fix bug",
                    "token_budget": 10000,
                    "strategy": "dependency_aware",
                    "selected_files": ["file1.md"],
                    "selected_sections": {},
                    "total_tokens": 3000,
                    "utilization": 0.3,
                    "excluded_files": [],
                    "relevance_scores": {"file1.md": 0.8},
                },
                {
                    "timestamp": "2026-01-21T10:10",
                    "task_description": "Fix another bug",
                    "token_budget": 10000,
                    "strategy": "dependency_aware",
                    "selected_files": ["file2.md"],
                    "selected_sections": {},
                    "total_tokens": 4000,
                    "utilization": 0.4,
                    "excluded_files": [],
                    "relevance_scores": {"file2.md": 0.7},
                },
                {
                    "timestamp": "2026-01-21T10:15",
                    "task_description": "Implement feature",
                    "token_budget": 20000,
                    "strategy": "dependency_aware",
                    "selected_files": ["file3.md"],
                    "selected_sections": {},
                    "total_tokens": 10000,
                    "utilization": 0.5,
                    "excluded_files": [],
                    "relevance_scores": {"file3.md": 0.9},
                },
            ],
        }
        _ = (session_dir / "context-session-task_type_test.json").write_text(
            json.dumps(log_data)
        )

        # Act
        _ = analyze_session_logs(tmp_path)
        result = get_context_statistics(tmp_path)

        # Assert
        assert result.status == "success"
        insights_raw = result.insights
        assert insights_raw is not None
        insights = cast(dict[str, object], insights_raw.model_dump(mode="python"))
        task_recs = cast(dict[str, object], insights["task_type_recommendations"])
        assert "fix/debug" in task_recs
        assert "implement/add" in task_recs
        fix_debug = cast(dict[str, object], task_recs["fix/debug"])
        implement_add = cast(dict[str, object], task_recs["implement/add"])
        assert cast(int, fix_debug["calls_count"]) == 2
        assert cast(int, implement_add["calls_count"]) == 1

    def test_learned_patterns_via_insights(self, tmp_path: Path) -> None:
        """Test learned patterns through insights."""
        # Arrange
        session_dir = get_cortex_path(tmp_path, CortexResourceType.SESSION)
        _ = session_dir.mkdir(parents=True)

        log_data: dict[str, object] = {
            "session_id": "patterns_test",
            "session_start": "2026-01-21T10:00",
            "load_context_calls": [
                {
                    "timestamp": "2026-01-21T10:05",
                    "task_description": "Fix bug 1",
                    "token_budget": 10000,
                    "strategy": "dependency_aware",
                    "selected_files": ["common_file.md"],
                    "selected_sections": {},
                    "total_tokens": 3000,
                    "utilization": 0.3,
                    "excluded_files": [],
                    "relevance_scores": {"common_file.md": 0.8},
                },
                {
                    "timestamp": "2026-01-21T10:10",
                    "task_description": "Fix bug 2",
                    "token_budget": 10000,
                    "strategy": "dependency_aware",
                    "selected_files": ["common_file.md"],
                    "selected_sections": {},
                    "total_tokens": 4000,
                    "utilization": 0.4,
                    "excluded_files": [],
                    "relevance_scores": {"common_file.md": 0.85},
                },
            ],
        }
        _ = (session_dir / "context-session-patterns_test.json").write_text(
            json.dumps(log_data)
        )

        # Act
        result = analyze_session_logs(tmp_path)

        # Assert
        assert result.status == "success"
        insights_raw = result.insights
        assert insights_raw is not None
        insights = cast(dict[str, object], insights_raw.model_dump(mode="python"))
        patterns = cast(list[str], insights["learned_patterns"])
        assert len(patterns) >= 1
        # Should mention utilization or frequently loaded file
        pattern_text = " ".join(patterns).lower()
        assert "utilization" in pattern_text or "common_file.md" in pattern_text

    def test_budget_recommendations_via_insights(self, tmp_path: Path) -> None:
        """Test budget recommendations through insights."""
        # Arrange
        session_dir = get_cortex_path(tmp_path, CortexResourceType.SESSION)
        _ = session_dir.mkdir(parents=True)

        log_data: dict[str, object] = {
            "session_id": "budget_test",
            "session_start": "2026-01-21T10:00",
            "load_context_calls": [
                {
                    "timestamp": "2026-01-21T10:05",
                    "task_description": "Fix bug",
                    "token_budget": 10000,
                    "strategy": "dependency_aware",
                    "selected_files": ["file1.md"],
                    "selected_sections": {},
                    "total_tokens": 5000,
                    "utilization": 0.5,
                    "excluded_files": [],
                    "relevance_scores": {"file1.md": 0.8},
                },
                {
                    "timestamp": "2026-01-21T10:10",
                    "task_description": "Implement feature",
                    "token_budget": 20000,
                    "strategy": "dependency_aware",
                    "selected_files": ["file2.md"],
                    "selected_sections": {},
                    "total_tokens": 15000,
                    "utilization": 0.75,
                    "excluded_files": [],
                    "relevance_scores": {"file2.md": 0.9},
                },
            ],
        }
        _ = (session_dir / "context-session-budget_test.json").write_text(
            json.dumps(log_data)
        )

        # Act
        result = analyze_session_logs(tmp_path)

        # Assert
        assert result.status == "success"
        insights_raw = result.insights
        assert insights_raw is not None
        insights = cast(dict[str, object], insights_raw.model_dump(mode="python"))
        budget_recs = cast(dict[str, int], insights["budget_recommendations"])
        assert "fix/debug" in budget_recs
        assert "implement/add" in budget_recs
        # Recommendations should be higher than actual usage
        assert budget_recs["fix/debug"] >= 5000
        assert budget_recs["implement/add"] >= 15000

    def test_insights_included_in_analysis_result(self, tmp_path: Path) -> None:
        """Test that insights are included in analysis results."""
        # Arrange
        session_dir = get_cortex_path(tmp_path, CortexResourceType.SESSION)
        _ = session_dir.mkdir(parents=True)

        log_data: dict[str, object] = {
            "session_id": "insights_test",
            "session_start": "2026-01-21T10:00",
            "load_context_calls": [
                {
                    "timestamp": "2026-01-21T10:05",
                    "task_description": "Fix bug",
                    "token_budget": 10000,
                    "strategy": "dependency_aware",
                    "selected_files": ["file1.md", "file2.md"],
                    "selected_sections": {},
                    "total_tokens": 3000,
                    "utilization": 0.3,
                    "excluded_files": [],
                    "relevance_scores": {"file1.md": 0.8, "file2.md": 0.6},
                }
            ],
        }
        _ = (session_dir / "context-session-insights_test.json").write_text(
            json.dumps(log_data)
        )

        # Act
        result = analyze_session_logs(tmp_path)

        # Assert
        assert result.status == "success"
        insights_raw = result.insights
        assert insights_raw is not None
        insights = cast(dict[str, object], insights_raw.model_dump(mode="python"))
        assert "task_type_recommendations" in insights
        assert "file_effectiveness" in insights
        assert "learned_patterns" in insights

    def test_insights_in_statistics(self, tmp_path: Path) -> None:
        """Test that insights are included in get_context_statistics."""
        # Arrange
        session_dir = get_cortex_path(tmp_path, CortexResourceType.SESSION)
        _ = session_dir.mkdir(parents=True)

        stats_data: dict[str, object] = {
            "last_updated": "2026-01-21T10:00",
            "total_sessions_analyzed": 1,
            "total_load_context_calls": 1,
            "avg_token_utilization": 0.3,
            "avg_files_selected": 2.0,
            "avg_relevance_score": 0.7,
            "common_task_patterns": {"fix/debug": 1},
            "insights": {
                "task_type_recommendations": {
                    "fix/debug": {
                        "calls_count": 1,
                        "recommended_budget": 10000,
                        "essential_files": ["file1.md"],
                        "avg_utilization": 0.3,
                        "avg_relevance": 0.7,
                        "notes": "Test notes",
                    }
                },
                "file_effectiveness": {
                    "file1.md": {
                        "times_selected": 1,
                        "avg_relevance": 0.8,
                        "task_types_used": ["fix/debug"],
                        "recommendation": "High value",
                    }
                },
                "learned_patterns": ["Test pattern"],
                "budget_recommendations": {"fix/debug": 10000},
            },
            "entries": [],
        }
        _ = (session_dir / "context-usage-statistics.json").write_text(
            json.dumps(stats_data)
        )

        # Act
        result = get_context_statistics(tmp_path)

        # Assert
        assert result.status == "success"
        insights_raw = result.insights
        assert insights_raw is not None
        insights = cast(dict[str, object], insights_raw.model_dump(mode="python"))
        assert "task_type_recommendations" in insights
        task_recs = cast(dict[str, object], insights["task_type_recommendations"])
        assert "fix/debug" in task_recs
