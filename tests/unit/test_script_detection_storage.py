"""Tests for script capture storage."""

from pathlib import Path

import pytest

from cortex.script_detection.models import ScriptCaptureRecord
from cortex.script_detection.storage import (
    ensure_capture_dir,
    generate_script_id,
    get_capture_by_id,
    list_captures,
    save_capture,
)


class TestEnsureCaptureDir:
    """Tests for ensure_capture_dir."""

    @pytest.mark.asyncio
    async def test_creates_script_capture_directory(self, tmp_path: Path) -> None:
        """Creates .cortex/script-capture when missing."""
        result = await ensure_capture_dir(tmp_path)
        assert result == tmp_path / ".cortex" / "script-capture"
        assert result.is_dir()

    @pytest.mark.asyncio
    async def test_returns_existing_directory(self, tmp_path: Path) -> None:
        """Returns path when directory already exists."""
        capture_dir = tmp_path / ".cortex" / "script-capture"
        capture_dir.mkdir(parents=True)
        result = await ensure_capture_dir(tmp_path)
        assert result == capture_dir


class TestSaveAndListCaptures:
    """Tests for save_capture and list_captures."""

    @pytest.mark.asyncio
    async def test_save_and_list_roundtrip(self, tmp_path: Path) -> None:
        """Save record then list returns it."""
        record = ScriptCaptureRecord(
            script_id="test-id",
            timestamp="2026-01-16T10:00:00Z",
            task_description="Test task",
            script_path="foo.py",
            script_content="print(1)",
        )
        await save_capture(tmp_path, record)
        records = await list_captures(tmp_path)
        assert len(records) == 1
        assert records[0].script_id == "test-id"
        assert records[0].script_content == "print(1)"

    @pytest.mark.asyncio
    async def test_list_empty_when_no_captures(self, tmp_path: Path) -> None:
        """list_captures returns empty list when directory does not exist."""
        records = await list_captures(tmp_path)
        assert records == []

    @pytest.mark.asyncio
    async def test_list_multiple_captures(self, tmp_path: Path) -> None:
        """list_captures returns all saved records."""
        await save_capture(
            tmp_path,
            ScriptCaptureRecord(
                script_id="a",
                timestamp="2026-01-16T10:00:00Z",
                task_description="A",
                script_path="a.py",
                script_content="a",
            ),
        )
        await save_capture(
            tmp_path,
            ScriptCaptureRecord(
                script_id="b",
                timestamp="2026-01-16T11:00:00Z",
                task_description="B",
                script_path="b.py",
                script_content="b",
            ),
        )
        records = await list_captures(tmp_path)
        assert len(records) == 2
        ids = {r.script_id for r in records}
        assert ids == {"a", "b"}


class TestGetCaptureById:
    """Tests for get_capture_by_id."""

    @pytest.mark.asyncio
    async def test_returns_none_when_missing(self, tmp_path: Path) -> None:
        """get_capture_by_id returns None when file does not exist."""
        result = await get_capture_by_id(tmp_path, "missing-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_record_when_exists(self, tmp_path: Path) -> None:
        """get_capture_by_id returns record when file exists."""
        record = ScriptCaptureRecord(
            script_id="found-id",
            timestamp="2026-01-16T10:00:00Z",
            task_description="Found",
            script_path="found.py",
            script_content="found",
        )
        await save_capture(tmp_path, record)
        result = await get_capture_by_id(tmp_path, "found-id")
        assert result is not None
        assert result.script_id == "found-id"
        assert result.script_content == "found"


class TestGenerateScriptId:
    """Tests for generate_script_id."""

    def test_returns_uuid_string(self) -> None:
        """generate_script_id returns a string that looks like UUID."""
        sid = generate_script_id()
        assert isinstance(sid, str)
        assert len(sid) == 36
        assert sid.count("-") == 4

    def test_ids_are_unique(self) -> None:
        """Multiple calls return different IDs."""
        ids = {generate_script_id() for _ in range(20)}
        assert len(ids) == 20
