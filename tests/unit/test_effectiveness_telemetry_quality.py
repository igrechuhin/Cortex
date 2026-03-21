"""Tests for context telemetry classification and optimization rollups."""

from __future__ import annotations

# pyright: reportPrivateUsage=false, reportUnusedFunction=false
import json
from collections.abc import Generator
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock, patch

import pytest

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.session_logger import LoadContextLogEntry
from cortex.tools.context.effectiveness_models import (
    ContextTelemetryExclusionBreakdown,
    ContextTelemetryRecordQuality,
    ContextUsageEntry,
    ContextUsageStatistics,
)
from cortex.tools.context.effectiveness_operations import (
    _analyze_log_entry,
    _calculate_session_stats,
    _update_aggregates,
    analyze_session_logs,
    get_context_statistics,
)
from cortex.tools.context.effectiveness_operations_io import (
    create_empty_insights,
    get_statistics_path,
    load_statistics,
)
from cortex.tools.context.effectiveness_telemetry_quality import (
    classify_context_telemetry_log_entry,
    is_synthetic_telemetry_task,
    log_and_classify_context_telemetry_entry,
    log_telemetry_rollup_exclusion,
    reset_context_telemetry_exclusion_counters,
    snapshot_context_telemetry_exclusion_counters,
)


def _enable_usage_writable(project_root: Path) -> None:
    cortex_dir = project_root / ".cortex"
    cortex_dir.mkdir(parents=True, exist_ok=True)
    synapse_dir = cortex_dir / "synapse"
    synapse_dir.mkdir(parents=True, exist_ok=True)
    _ = (synapse_dir / "config.json").write_text(
        '{"usage_writable": true}', encoding="utf-8"
    )


def _log_entry(**overrides: object) -> LoadContextLogEntry:
    data: dict[str, object] = {
        "timestamp": "2026-01-21T10:00",
        "task_description": "Fix bug",
        "token_budget": 10_000,
        "strategy": "dependency_aware",
        "selected_files": ["a.md"],
        "selected_sections": {},
        "total_tokens": 1000,
        "utilization": 0.1,
        "excluded_files": [],
        "relevance_scores": {"a.md": 0.8},
    }
    data.update(overrides)
    return LoadContextLogEntry.model_validate(data)


def _usage_entry(
    *,
    task: str = "Fix bug",
    budget: int = 10_000,
    quality: ContextTelemetryRecordQuality = ContextTelemetryRecordQuality.PRODUCTION,
    files: list[str] | None = None,
    note: str | None = None,
) -> ContextUsageEntry:
    selected = files or ["a.md"]
    relevance = {name: 0.8 for name in selected}
    scores = list(relevance.values())
    return ContextUsageEntry(
        session_id="sess",
        timestamp="2026-01-21T10:00",
        task_description=task,
        token_budget=budget,
        total_tokens=1000,
        utilization=0.1,
        files_selected=len(selected),
        files_excluded=0,
        avg_relevance_score=round(sum(scores) / len(scores), 3),
        files_with_high_relevance=sum(1 for s in scores if s > 0.7),
        files_with_low_relevance=sum(1 for s in scores if s < 0.3),
        selected_file_names=selected,
        relevance_by_file=relevance,
        record_quality=quality,
        telemetry_quality_note=note,
    )


@pytest.mark.parametrize(
    ("task", "expected"),
    [
        ("Test task", True),
        ("test task", True),
        ("  TEST TASK  ", True),
        ("test_foo_bar", True),
        ("test_registration_flow", True),
        ("Run pytest for module", True),
        ("unittest suite", True),
        ("Implement real feature", False),
        ("contest the results", False),
    ],
)
def test_is_synthetic_telemetry_task(task: str, expected: bool) -> None:
    assert is_synthetic_telemetry_task(task) is expected


def test_classify_synthetic_before_invalid_budget() -> None:
    entry = _log_entry(
        task_description="Test task",
        token_budget=0,
        selected_files=["a.md"],
        total_tokens=500,
    )
    quality, note = classify_context_telemetry_log_entry(entry)
    assert quality == ContextTelemetryRecordQuality.SYNTHETIC
    assert note == "synthetic_or_test_task_marker"


def test_classify_invalid_zero_budget_with_payload() -> None:
    entry = _log_entry(
        task_description="Implement payment flow",
        token_budget=0,
        selected_files=["pay.py"],
        total_tokens=900,
    )
    quality, note = classify_context_telemetry_log_entry(entry)
    assert quality == ContextTelemetryRecordQuality.INVALID_DATA
    assert note == "zero_token_budget_with_context_payload"


def test_classify_production() -> None:
    entry = _log_entry()
    quality, note = classify_context_telemetry_log_entry(entry)
    assert quality == ContextTelemetryRecordQuality.PRODUCTION
    assert note is None


def test_classify_positive_tokens_without_selected_files() -> None:
    entry = _log_entry(
        task_description="Real feature work",
        selected_files=[],
        relevance_scores={},
        total_tokens=500,
        token_budget=8000,
        utilization=0.05,
    )
    quality, note = classify_context_telemetry_log_entry(entry)
    assert quality == ContextTelemetryRecordQuality.INVALID_DATA
    assert note == "positive_tokens_without_selected_files"


def test_classify_relevance_without_selected_files() -> None:
    entry = _log_entry(
        task_description="Real feature work",
        selected_files=[],
        relevance_scores={"ghost.py": 0.5},
        total_tokens=0,
        token_budget=8000,
        utilization=0.0,
    )
    quality, note = classify_context_telemetry_log_entry(entry)
    assert quality == ContextTelemetryRecordQuality.INVALID_DATA
    assert note == "relevance_scores_without_selected_files"


def test_load_statistics_backfills_legacy_production_synthetic(tmp_path: Path) -> None:
    _enable_usage_writable(tmp_path)
    stats_path = get_statistics_path(tmp_path)
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_json = (
        '{"last_updated":"2026-01-21T10:00","total_sessions_analyzed":1,'
        '"total_load_context_calls":1,"avg_token_utilization":0.2,'
        '"avg_files_selected":1.0,"avg_relevance_score":0.8,'
        '"common_task_patterns":{"test":1},'
        '"insights":{"task_type_recommendations":{},"file_effectiveness":{},'
        '"learned_patterns":[],"budget_recommendations":{},'
        '"role_recommendations":{},"role_budget_recommendations":{}},'
        '"entries":[{"session_id":"s1","timestamp":"2026-01-21T10:00",'
        '"task_description":"Test task","token_budget":5000,"total_tokens":100,'
        '"utilization":0.02,"files_selected":1,"files_excluded":0,'
        '"avg_relevance_score":0.8,"files_with_high_relevance":1,'
        '"files_with_low_relevance":0,"selected_file_names":["a.md"],'
        '"relevance_by_file":{"a.md":0.8}}]}'
    )
    _ = stats_path.write_text(legacy_json, encoding="utf-8")
    stats = load_statistics(stats_path)
    assert stats.entries[0].record_quality == ContextTelemetryRecordQuality.SYNTHETIC
    # Persisted backfill rewrites file when usage_writable
    round_trip = json.loads(stats_path.read_text(encoding="utf-8"))
    assert round_trip["entries"][0]["record_quality"] == "synthetic"
    assert round_trip["total_load_context_calls"] == 0


@pytest.fixture(autouse=True)
def reset_telemetry_exclusion_counters_autouse() -> Generator[None]:
    reset_context_telemetry_exclusion_counters()
    yield None
    reset_context_telemetry_exclusion_counters()


def test_snapshot_context_telemetry_exclusion_counters_empty() -> None:
    snap = snapshot_context_telemetry_exclusion_counters()
    assert snap.breakdown == []
    assert snap.total_excluded == 0


def test_snapshot_context_telemetry_exclusion_counters_tracks_reasons() -> None:
    log_telemetry_rollup_exclusion(
        session_id="a",
        task_description="Test task",
        quality=ContextTelemetryRecordQuality.SYNTHETIC,
        reason="synthetic_or_test_task_marker",
    )
    log_telemetry_rollup_exclusion(
        session_id="b",
        task_description="x",
        quality=ContextTelemetryRecordQuality.INVALID_DATA,
        reason="zero_token_budget_with_context_payload",
    )
    log_telemetry_rollup_exclusion(
        session_id="c",
        task_description="y",
        quality=ContextTelemetryRecordQuality.SYNTHETIC,
        reason="synthetic_or_test_task_marker",
    )
    snap = snapshot_context_telemetry_exclusion_counters()
    assert snap.total_excluded == 3
    assert snap.breakdown == [
        ContextTelemetryExclusionBreakdown(
            record_quality="invalid_data",
            reason="zero_token_budget_with_context_payload",
            count=1,
        ),
        ContextTelemetryExclusionBreakdown(
            record_quality="synthetic",
            reason="synthetic_or_test_task_marker",
            count=2,
        ),
    ]


def test_log_and_classify_increments_exclusion_counter() -> None:
    entry = _log_entry(task_description="Test task")
    q, _ = log_and_classify_context_telemetry_entry("sid", entry)
    assert q == ContextTelemetryRecordQuality.SYNTHETIC
    assert snapshot_context_telemetry_exclusion_counters().total_excluded == 1


def test_log_telemetry_rollup_exclusion_logs() -> None:
    mock_logger = MagicMock()
    with patch(
        "cortex.tools.context.effectiveness_telemetry_quality.logger", mock_logger
    ):
        log_telemetry_rollup_exclusion(
            session_id="abc",
            task_description="Test task",
            quality=ContextTelemetryRecordQuality.SYNTHETIC,
            reason="synthetic_or_test_task_marker",
        )
    mock_logger.info.assert_called_once()
    call_args = mock_logger.info.call_args[0]
    assert "Excluded context telemetry" in str(call_args[0]) and "rollup" in str(
        call_args[0]
    )
    assert call_args[2] == "synthetic"
    assert call_args[3] == "synthetic_or_test_task_marker"


def test_log_telemetry_rollup_exclusion_truncates_long_task() -> None:
    long_task = "x" * 200
    mock_logger = MagicMock()
    with patch(
        "cortex.tools.context.effectiveness_telemetry_quality.logger", mock_logger
    ):
        log_telemetry_rollup_exclusion(
            session_id="z",
            task_description=long_task,
            quality=ContextTelemetryRecordQuality.INVALID_DATA,
            reason="zero_token_budget_with_context_payload",
        )
    mock_logger.info.assert_called_once()
    snippet = mock_logger.info.call_args[0][4]
    assert len(snippet) <= 120


def test_log_telemetry_rollup_exclusion_skips_production() -> None:
    mock_logger = MagicMock()
    with patch(
        "cortex.tools.context.effectiveness_telemetry_quality.logger", mock_logger
    ):
        log_telemetry_rollup_exclusion(
            session_id="abc",
            task_description="Real work",
            quality=ContextTelemetryRecordQuality.PRODUCTION,
            reason=None,
        )
    mock_logger.info.assert_not_called()


def test_exclusion_metrics_export_posts_when_url_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "CORTEX_CONTEXT_TELEMETRY_EXCLUSION_METRICS_URL",
        "http://example.invalid/metrics",
    )
    monkeypatch.setenv(
        "CORTEX_CONTEXT_TELEMETRY_EXCLUSION_METRICS_EXPORT_INTERVAL_SEC", "0"
    )
    posted: list[bytes] = []

    def fake_urlopen(req: object, timeout: float = 0) -> object:
        assert getattr(req, "full_url", "") == "http://example.invalid/metrics"
        posted.append(getattr(req, "data", b""))
        cm = MagicMock()
        cm.read.return_value = b"ok"
        cm.__enter__ = MagicMock(return_value=cm)
        cm.__exit__ = MagicMock(return_value=False)
        return cm

    with patch(
        "cortex.tools.context.effectiveness_telemetry_quality.urlopen",
        side_effect=fake_urlopen,
    ):
        log_telemetry_rollup_exclusion(
            session_id="a",
            task_description="Test task",
            quality=ContextTelemetryRecordQuality.SYNTHETIC,
            reason="synthetic_or_test_task_marker",
        )
    assert len(posted) == 1
    payload = json.loads(posted[0].decode("utf-8"))
    assert payload["total_excluded"] == 1
    assert len(payload["breakdown"]) == 1


def test_exclusion_metrics_export_debounced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "CORTEX_CONTEXT_TELEMETRY_EXCLUSION_METRICS_URL",
        "http://example.invalid/metrics",
    )
    monkeypatch.setenv(
        "CORTEX_CONTEXT_TELEMETRY_EXCLUSION_METRICS_EXPORT_INTERVAL_SEC", "10"
    )
    calls = 0

    def fake_urlopen(req: object, timeout: float = 0) -> object:
        nonlocal calls
        calls += 1
        cm = MagicMock()
        cm.read.return_value = b"ok"
        cm.__enter__ = MagicMock(return_value=cm)
        cm.__exit__ = MagicMock(return_value=False)
        return cm

    with patch(
        "cortex.tools.context.effectiveness_telemetry_quality.urlopen",
        side_effect=fake_urlopen,
    ):
        with patch(
            "cortex.tools.context.effectiveness_telemetry_quality.time.monotonic",
            side_effect=[0.0, 1.0, 15.0],
        ):
            log_telemetry_rollup_exclusion(
                session_id="a",
                task_description="Test task",
                quality=ContextTelemetryRecordQuality.SYNTHETIC,
                reason="synthetic_or_test_task_marker",
            )
            log_telemetry_rollup_exclusion(
                session_id="b",
                task_description="Test task",
                quality=ContextTelemetryRecordQuality.SYNTHETIC,
                reason="synthetic_or_test_task_marker",
            )
            log_telemetry_rollup_exclusion(
                session_id="c",
                task_description="Test task",
                quality=ContextTelemetryRecordQuality.SYNTHETIC,
                reason="synthetic_or_test_task_marker",
            )
    assert calls == 2


def test_analyze_log_entry_sets_quality_fields() -> None:
    entry = _log_entry(task_description="pytest integration")
    row = _analyze_log_entry("sid", entry)
    assert row.record_quality == ContextTelemetryRecordQuality.SYNTHETIC
    assert row.telemetry_quality_note == "synthetic_or_test_task_marker"


def test_update_aggregates_noop_when_entries_empty() -> None:
    stats = ContextUsageStatistics(
        last_updated="2026-01-21T10:00",
        total_sessions_analyzed=0,
        total_load_context_calls=3,
        avg_token_utilization=0.5,
        avg_files_selected=2.0,
        avg_relevance_score=0.6,
        common_task_patterns={"x": 1},
        insights=create_empty_insights(),
        entries=[],
    )
    _update_aggregates(stats)
    assert stats.total_load_context_calls == 3


def test_calculate_session_stats_empty_entries() -> None:
    stats = _calculate_session_stats([])
    assert stats.calls_count == 0
    assert stats.task_patterns == {}


def test_update_aggregates_uses_production_only() -> None:
    stats = ContextUsageStatistics(
        last_updated="2026-01-21T10:00",
        total_sessions_analyzed=2,
        total_load_context_calls=0,
        avg_token_utilization=0.0,
        avg_files_selected=0.0,
        avg_relevance_score=0.0,
        common_task_patterns={},
        insights=create_empty_insights(),
        entries=[
            _usage_entry(
                task="Test task",
                quality=ContextTelemetryRecordQuality.SYNTHETIC,
                note="synthetic_or_test_task_marker",
            ),
            _usage_entry(
                task="Add feature",
                quality=ContextTelemetryRecordQuality.PRODUCTION,
            ),
        ],
    )
    _update_aggregates(stats)
    assert stats.total_load_context_calls == 1
    assert stats.common_task_patterns == {"implement/add": 1}


def test_update_aggregates_all_filtered_yields_empty_rollups() -> None:
    stats = ContextUsageStatistics(
        last_updated="2026-01-21T10:00",
        total_sessions_analyzed=1,
        total_load_context_calls=99,
        avg_token_utilization=0.5,
        avg_files_selected=2.0,
        avg_relevance_score=0.5,
        common_task_patterns={"x": 1},
        insights=create_empty_insights(),
        entries=[
            _usage_entry(
                task="Test task",
                quality=ContextTelemetryRecordQuality.SYNTHETIC,
            ),
        ],
    )
    _update_aggregates(stats)
    assert stats.total_load_context_calls == 0
    assert stats.avg_token_utilization == 0.0
    assert stats.common_task_patterns == {}
    assert stats.insights is not None
    assert stats.insights.learned_patterns == []


def test_calculate_session_stats_counts_all_averages_production_only() -> None:
    stats = _calculate_session_stats(
        [
            _usage_entry(
                task="Test task",
                quality=ContextTelemetryRecordQuality.SYNTHETIC,
            ),
            _usage_entry(
                task="Fix bug",
                quality=ContextTelemetryRecordQuality.PRODUCTION,
                files=["b.md"],
            ),
        ]
    )
    assert stats.calls_count == 2
    assert stats.task_patterns == {"fix/debug": 1}
    assert stats.avg_token_utilization == 0.1


def test_session_log_integration_mixed_quality(tmp_path: Path) -> None:
    _enable_usage_writable(tmp_path)
    session_dir = get_cortex_path(tmp_path, CortexResourceType.SESSION)
    _ = session_dir.mkdir(parents=True)
    log_data: dict[str, object] = {
        "session_id": "mixed_quality",
        "session_start": "2026-01-21T10:00",
        "load_context_calls": [
            {
                "timestamp": "2026-01-21T10:05",
                "task_description": "Test task",
                "token_budget": 5000,
                "strategy": "dependency_aware",
                "selected_files": ["a.md"],
                "selected_sections": {},
                "total_tokens": 1000,
                "utilization": 0.2,
                "excluded_files": [],
                "relevance_scores": {"a.md": 0.8},
            },
            {
                "timestamp": "2026-01-21T10:10",
                "task_description": "Fix production bug",
                "token_budget": 10000,
                "strategy": "dependency_aware",
                "selected_files": ["b.md"],
                "selected_sections": {},
                "total_tokens": 4000,
                "utilization": 0.4,
                "excluded_files": [],
                "relevance_scores": {"b.md": 0.85},
            },
        ],
    }
    _ = (session_dir / "context-session-mixed_quality.json").write_text(
        json.dumps(log_data)
    )
    result = analyze_session_logs(tmp_path)
    assert result.status == "success"
    assert result.new_entries_added == 2
    stats_path = session_dir / "context-usage-statistics.json"
    assert stats_path.exists()
    raw = json.loads(stats_path.read_text(encoding="utf-8"))
    entries = cast(list[dict[str, object]], raw["entries"])
    assert entries[0]["record_quality"] == "synthetic"
    assert entries[1]["record_quality"] == "production"
    assert raw["total_load_context_calls"] == 1

    stats_result = get_context_statistics(tmp_path)
    assert stats_result.status == "success"
    assert stats_result.total_calls == 1


def test_load_statistics_defaults_schema_version_when_omitted(tmp_path: Path) -> None:
    stats_path = get_statistics_path(tmp_path)
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    insights_json = json.dumps(create_empty_insights().model_dump(mode="json"))
    raw = (
        '{"last_updated":"2026-03-21T12:00","total_sessions_analyzed":0,'
        '"total_load_context_calls":0,"avg_token_utilization":0.0,'
        '"avg_files_selected":0.0,"avg_relevance_score":0.0,'
        f'"common_task_patterns":{{}},"insights":{insights_json},"entries":[]}}'
    )
    _ = stats_path.write_text(raw, encoding="utf-8")
    loaded = load_statistics(stats_path)
    assert loaded.schema_version == 1


def test_load_statistics_accepts_explicit_schema_version(tmp_path: Path) -> None:
    stats_path = get_statistics_path(tmp_path)
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    insights_json = json.dumps(create_empty_insights().model_dump(mode="json"))
    raw = (
        '{"schema_version":1,"last_updated":"2026-03-21T12:00",'
        '"total_sessions_analyzed":0,"total_load_context_calls":0,'
        '"avg_token_utilization":0.0,"avg_files_selected":0.0,'
        '"avg_relevance_score":0.0,"common_task_patterns":{},'
        f'"insights":{insights_json},"entries":[]}}'
    )
    _ = stats_path.write_text(raw, encoding="utf-8")
    loaded = load_statistics(stats_path)
    assert loaded.schema_version == 1
