"""Unit tests for cache JSON MCP tools (read_cache_json, write_cache_json)."""

import json
from pathlib import Path

import pytest

from cortex.tools.cache_json_tools import read_cache_json, write_cache_json


def _project_root(tmp_path: Path) -> Path:
    """Create project root with .cortex/.cache."""
    root = tmp_path / "project"
    _ = (root / ".cortex" / ".cache").mkdir(parents=True)
    return root


class TestReadCacheJsonTool:
    """Tests for read_cache_json MCP tool."""

    @pytest.mark.asyncio
    async def test_returns_missing_when_file_absent(self, tmp_path: Path) -> None:
        """Tool returns status missing when file does not exist."""
        root = _project_root(tmp_path)
        result_str = await read_cache_json(
            relative_path="usage/events/2026-01-01.json",
            project_root=str(root),
        )
        result = json.loads(result_str)
        assert result.get("status") == "missing"
        assert result.get("relative_path") == "usage/events/2026-01-01.json"

    @pytest.mark.asyncio
    async def test_returns_json_content_when_file_exists(self, tmp_path: Path) -> None:
        """Tool returns file content as JSON when file exists."""
        root = _project_root(tmp_path)
        path = root / ".cortex" / ".cache" / "data.json"
        _ = path.parent.mkdir(parents=True, exist_ok=True)
        _ = path.write_text('{"key": "value"}')
        result_str = await read_cache_json(
            relative_path="data.json",
            project_root=str(root),
        )
        result = json.loads(result_str)
        assert result == {"key": "value"}

    @pytest.mark.asyncio
    async def test_returns_error_for_invalid_relative_path(
        self, tmp_path: Path
    ) -> None:
        """Tool returns error for path traversal."""
        root = _project_root(tmp_path)
        result_str = await read_cache_json(
            relative_path="../../etc/passwd",
            project_root=str(root),
        )
        result = json.loads(result_str)
        assert result.get("status") == "error"
        assert "relative_path" in result


class TestWriteCacheJsonTool:
    """Tests for write_cache_json MCP tool."""

    @pytest.mark.asyncio
    async def test_write_then_read_roundtrip(self, tmp_path: Path) -> None:
        """Write then read returns same data."""
        root = _project_root(tmp_path)
        content = '{"a": 1, "b": "x"}'
        out_str = await write_cache_json(
            relative_path="roundtrip.json",
            content=content,
            project_root=str(root),
        )
        out = json.loads(out_str)
        assert out.get("status") == "success"
        result_str = await read_cache_json(
            relative_path="roundtrip.json",
            project_root=str(root),
        )
        result = json.loads(result_str)
        assert result == {"a": 1, "b": "x"}

    @pytest.mark.asyncio
    async def test_returns_error_for_invalid_json(self, tmp_path: Path) -> None:
        """Tool returns error for invalid JSON content."""
        root = _project_root(tmp_path)
        result_str = await write_cache_json(
            relative_path="bad.json",
            content="not json {",
            project_root=str(root),
        )
        result = json.loads(result_str)
        assert result.get("status") == "error"
        assert "Invalid JSON" in str(result.get("message", ""))
