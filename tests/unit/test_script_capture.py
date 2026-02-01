"""Tests for script_capture.capture_script."""

from pathlib import Path

import pytest

from cortex.script_detection.script_capture import capture_script
from cortex.script_detection.storage import list_captures


class TestCaptureScript:
    """Tests for capture_script function."""

    @pytest.mark.asyncio
    async def test_capture_creates_record_and_persists(self, tmp_path: Path) -> None:
        """capture_script returns record and saves to storage."""
        record = await capture_script(
            project_root=tmp_path,
            script_path="scripts/foo.py",
            script_content="print('hello')",
            task_description="Test capture",
        )
        assert record.script_id
        assert record.timestamp
        assert record.task_description == "Test capture"
        assert record.script_path == "scripts/foo.py"
        assert record.script_content == "print('hello')"
        assert record.script_type == "python"
        assert record.purpose == "utility"
        records = await list_captures(tmp_path)
        assert len(records) == 1
        assert records[0].script_id == record.script_id

    @pytest.mark.asyncio
    async def test_capture_with_optional_params(self, tmp_path: Path) -> None:
        """capture_script accepts script_type, purpose, usage_context."""
        record = await capture_script(
            project_root=tmp_path,
            script_path="analyze.sh",
            script_content="#!/bin/bash",
            task_description="Analyze",
            script_type="shell",
            purpose="analysis",
            usage_context="One-off",
        )
        assert record.script_type == "shell"
        assert record.purpose == "analysis"
        assert record.usage_context == "One-off"
