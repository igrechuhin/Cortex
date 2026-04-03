"""Tests for context analysis response truncation (MCP resource size bounds)."""

import json
import os
from pathlib import Path
from typing import cast

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.context.effectiveness_models import (
    ContextTelemetryRecordQuality,
    ContextUsageEntry,
    ContextUsageStatistics,
)
from cortex.tools.context.effectiveness_operations import (
    analyze_current_session,
    get_context_statistics,
)
from cortex.tools.context.effectiveness_operations_io import (
    create_empty_insights,
    get_statistics_path,
    save_statistics,
)


def _five_sample_usage_entries() -> list[ContextUsageEntry]:
    """Minimal persisted rows for statistics truncation tests."""
    return [
        ContextUsageEntry(
            session_id=f"s{i}",
            timestamp=f"2026-01-{20 + i:02d}T10:00",
            task_description="task",
            token_budget=1000,
            total_tokens=100,
            utilization=0.1,
            files_selected=1,
            files_excluded=0,
            avg_relevance_score=0.5,
            files_with_high_relevance=0,
            files_with_low_relevance=0,
            selected_file_names=["a.md"],
            relevance_by_file={"a.md": 0.5},
            record_quality=ContextTelemetryRecordQuality.PRODUCTION,
        )
        for i in range(5)
    ]


def _write_twelve_call_session_log(tmp_path: Path, session_id: str) -> None:
    """Create a session log with 12 synthetic load_context rows."""
    session_dir = get_cortex_path(tmp_path, CortexResourceType.SESSION)
    _ = session_dir.mkdir(parents=True)
    base: dict[str, object] = {
        "task_description": "Task",
        "token_budget": 5000,
        "strategy": "dependency_aware",
        "selected_files": ["a.md"],
        "selected_sections": {},
        "total_tokens": 1000,
        "utilization": 0.2,
        "excluded_files": [],
        "relevance_scores": {"a.md": 0.8},
    }
    calls = [{**base, "timestamp": f"2026-01-21T10:{i:02d}"} for i in range(12)]
    log_data: dict[str, object] = {
        "session_id": session_id,
        "session_start": "2026-01-21T10:00",
        "load_context_calls": calls,
    }
    _ = (session_dir / f"context-session-{session_id}.json").write_text(
        json.dumps(log_data)
    )


def test_truncates_entries_when_max_response_calls_set(tmp_path: Path) -> None:
    """Response entries are capped while calls_analyzed reflects the full session."""
    env_key = "CORTEX_SESSION_ID"
    original = os.environ.get(env_key)
    os.environ[env_key] = "truncate_test_sess"
    _write_twelve_call_session_log(tmp_path, "truncate_test_sess")
    try:
        result = analyze_current_session(tmp_path, max_response_calls=10)
        assert result.status == "success"
        assert result.truncated is True
        assert result.total_calls_in_session == 12
        assert result.calls_in_response == 10
        current_raw = result.current_session
        assert current_raw is not None
        current = cast(dict[str, object], current_raw.model_dump(mode="python"))
        assert current["calls_analyzed"] == 12
        assert len(cast(list[object], current["entries"])) == 10
    finally:
        if original:
            os.environ[env_key] = original
        else:
            _ = os.environ.pop(env_key, None)


def test_context_statistics_marks_truncated_when_tail_capped(tmp_path: Path) -> None:
    """Statistics JSON omits older rows when max_recent_entries is smaller than history."""
    stats = ContextUsageStatistics(
        last_updated="2026-01-25T10:00",
        total_sessions_analyzed=5,
        total_load_context_calls=5,
        avg_token_utilization=0.1,
        avg_files_selected=1.0,
        avg_relevance_score=0.5,
        common_task_patterns={},
        insights=create_empty_insights(),
        entries=_five_sample_usage_entries(),
    )
    save_statistics(get_statistics_path(tmp_path), stats)
    result = get_context_statistics(tmp_path, max_recent_entries=3)
    assert result.status == "success"
    assert result.truncated is True
    assert result.recent_entries is not None
    assert len(result.recent_entries) == 3
