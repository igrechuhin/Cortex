"""Tests for detached pre-commit result file reading."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cortex.core.models import OperationStatus
from cortex.tools.execution import pre_commit_process


@pytest.mark.asyncio
async def test_read_result_file_rejects_json_string_payload(tmp_path: Path) -> None:
    """Non-object JSON must not call .get on a str (AttributeError in production)."""
    p = tmp_path / "pre_commit_result_x.json"
    _ = p.write_text(json.dumps("not-a-result-object"), encoding="utf-8")
    data, status = await pre_commit_process.read_result_file(p)
    assert data is not None
    assert status == OperationStatus.ERROR.value
    assert data.get("status") == OperationStatus.ERROR.value
    assert "JSON object" in str(data.get("error", ""))


@pytest.mark.asyncio
async def test_read_result_file_accepts_object_envelope(tmp_path: Path) -> None:
    """Valid worker-style envelope is returned unchanged."""
    p = tmp_path / "pre_commit_result_y.json"
    envelope = {"version": 1, "status": "running", "pid": 12345}
    _ = p.write_text(json.dumps(envelope), encoding="utf-8")
    data, status = await pre_commit_process.read_result_file(p)
    assert data == envelope
    assert status == "running"
