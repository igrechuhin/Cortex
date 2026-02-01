"""Tests for script detection Pydantic models."""

from cortex.script_detection.models import (
    ScriptCaptureRecord,
    make_timestamp_utc,
)


class TestScriptCaptureRecord:
    """Tests for ScriptCaptureRecord model."""

    def test_creates_record_with_required_fields(self) -> None:
        """Record is created with script_id, timestamp, task_description, path, content."""
        record = ScriptCaptureRecord(
            script_id="id-1",
            timestamp="2026-01-16T10:30:00Z",
            task_description="Run lint",
            script_path="scripts/lint.py",
            script_content="print('lint')",
        )
        assert record.script_id == "id-1"
        assert record.timestamp == "2026-01-16T10:30:00Z"
        assert record.task_description == "Run lint"
        assert record.script_path == "scripts/lint.py"
        assert record.script_content == "print('lint')"
        assert record.script_type == "python"
        assert record.purpose == "utility"
        assert record.promotion_status == "pending"

    def test_creates_record_with_optional_fields(self) -> None:
        """Record accepts usage_context, agent_session, dependencies."""
        record = ScriptCaptureRecord(
            script_id="id-2",
            timestamp="2026-01-16T11:00:00Z",
            task_description="Analyze",
            script_path="analyze.sh",
            script_content="#!/bin/bash\necho done",
            script_type="shell",
            purpose="analysis",
            usage_context="One-off analysis",
            agent_session="session-1",
            dependencies=["dep1"],
        )
        assert record.script_type == "shell"
        assert record.purpose == "analysis"
        assert record.usage_context == "One-off analysis"
        assert record.agent_session == "session-1"
        assert record.dependencies == ["dep1"]

    def test_to_storage_dict_roundtrip(self) -> None:
        """to_storage_dict and from_storage_dict roundtrip."""
        record = ScriptCaptureRecord(
            script_id="id-3",
            timestamp="2026-01-16T12:00:00Z",
            task_description="Transform",
            script_path="transform.py",
            script_content="x = 1",
        )
        data = record.to_storage_dict()
        restored = ScriptCaptureRecord.from_storage_dict(data)
        assert restored.script_id == record.script_id
        assert restored.script_content == record.script_content


class TestMakeTimestampUtc:
    """Tests for make_timestamp_utc."""

    def test_returns_iso_format_string(self) -> None:
        """Timestamp is ISO format with Z suffix."""
        ts = make_timestamp_utc()
        assert "T" in ts
        assert ts.endswith("Z")
        assert len(ts) >= 20
