"""Unit tests for cache JSON MCP tools (read_cache_json, write_cache_json)."""

import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from cortex.tools.cache_json_tools import (
    error_response,
    parse_write_content,
    read_cache_json,
    write_cache_json,
)


def _project_root(tmp_path: Path) -> Path:
    """Create project root with .cortex/.cache."""
    root = tmp_path / "project"
    _ = (root / ".cortex" / ".cache").mkdir(parents=True)
    return root


class TestReadCacheJsonTool:
    """Tests for read_cache_json MCP tool."""

    @pytest.mark.asyncio
    @pytest.mark.timeout(25)
    async def test_returns_missing_when_file_absent(self, tmp_path: Path) -> None:
        """Tool returns status missing when file does not exist."""
        root = _project_root(tmp_path)
        with patch.dict(os.environ, {"CORTEX_USE_FALLBACK_ROOT": "1"}):
            with patch(
                "cortex.core.project_root_resolver.get_project_root",
                return_value=root,
            ):
                result_str = await read_cache_json(
                    relative_path="usage/events/2026-01-01.json",
                )
        result = json.loads(result_str)
        assert result.get("status") == "missing"
        assert result.get("relative_path") == "usage/events/2026-01-01.json"

    @pytest.mark.asyncio
    @pytest.mark.timeout(25)
    async def test_returns_json_content_when_file_exists(self, tmp_path: Path) -> None:
        """Tool returns file content as JSON when file exists."""
        root = _project_root(tmp_path)
        path = root / ".cortex" / ".cache" / "data.json"
        _ = path.parent.mkdir(parents=True, exist_ok=True)
        _ = path.write_text('{"key": "value"}')
        with patch.dict(os.environ, {"CORTEX_USE_FALLBACK_ROOT": "1"}):
            with patch(
                "cortex.core.project_root_resolver.get_project_root",
                return_value=root,
            ):
                result_str = await read_cache_json(
                    relative_path="data.json",
                )
        result = json.loads(result_str)
        assert result == {"key": "value"}

    @pytest.mark.asyncio
    @pytest.mark.timeout(25)
    async def test_returns_error_for_invalid_relative_path(
        self, tmp_path: Path
    ) -> None:
        """Tool returns error for path traversal."""
        root = _project_root(tmp_path)
        with patch.dict(os.environ, {"CORTEX_USE_FALLBACK_ROOT": "1"}):
            with patch(
                "cortex.core.project_root_resolver.get_project_root",
                return_value=root,
            ):
                result_str = await read_cache_json(
                    relative_path="../../etc/passwd",
                )
        result = json.loads(result_str)
        assert result.get("status") == "error"
        assert "relative_path" in result


class TestWriteCacheJsonTool:
    """Tests for write_cache_json MCP tool."""

    @pytest.mark.asyncio
    @pytest.mark.timeout(25)
    async def test_write_then_read_roundtrip(self, tmp_path: Path) -> None:
        """Write then read returns same data."""
        root = _project_root(tmp_path)
        content = '{"a": 1, "b": "x"}'
        with patch.dict(os.environ, {"CORTEX_USE_FALLBACK_ROOT": "1"}):
            with patch(
                "cortex.core.project_root_resolver.get_project_root",
                return_value=root,
            ):
                out_str = await write_cache_json(
                    relative_path="roundtrip.json",
                    content=content,
                )
                out = json.loads(out_str)
                assert out.get("status") == "success"
                result_str = await read_cache_json(
                    relative_path="roundtrip.json",
                )
        result = json.loads(result_str)
        assert result == {"a": 1, "b": "x"}

    @pytest.mark.asyncio
    @pytest.mark.timeout(25)
    async def test_returns_error_for_invalid_json(self, tmp_path: Path) -> None:
        """Tool returns error for invalid JSON content."""
        root = _project_root(tmp_path)
        with patch.dict(os.environ, {"CORTEX_USE_FALLBACK_ROOT": "1"}):
            with patch(
                "cortex.core.project_root_resolver.get_project_root",
                return_value=root,
            ):
                result_str = await write_cache_json(
                    relative_path="bad.json",
                    content="not json {",
                )
        result = json.loads(result_str)
        assert result.get("status") == "error"
        assert "Invalid JSON" in str(result.get("message", ""))


class TestParseWriteContent:
    """Unit tests for _parse_write_content helper."""

    def test_valid_object_returns_payload_and_none(self) -> None:
        """Valid JSON object returns (dict, None) with string keys."""
        payload, err = parse_write_content('{"a": 1, "b": "x"}')
        assert err is None
        assert payload is not None
        assert isinstance(payload, dict)
        assert payload == {"a": 1, "b": "x"}

    def test_valid_array_returns_payload_and_none(self) -> None:
        """Valid JSON array returns (list, None)."""
        payload, err = parse_write_content("[1, 2, 3]")
        assert err is None
        assert payload is not None
        assert payload == [1, 2, 3]

    def test_non_object_non_array_returns_error(self) -> None:
        """JSON number or string returns (None, error message)."""
        payload, err = parse_write_content("42")
        assert payload is None
        assert err is not None
        assert "object or array" in err

        payload2, err2 = parse_write_content('"hello"')
        assert payload2 is None
        assert err2 is not None

    def test_invalid_json_returns_decode_error_message(self) -> None:
        """Invalid JSON returns (None, error message)."""
        payload, err = parse_write_content("{ broken }")
        assert payload is None
        assert err is not None
        assert "Invalid JSON" in err

    def test_empty_string_content_returns_error(self) -> None:
        """Empty string is invalid JSON."""
        payload, err = parse_write_content("")
        assert payload is None
        assert err is not None
        assert "Invalid JSON" in err

    def test_null_literal_returns_object_or_array_error(self) -> None:
        """JSON null is not object or array."""
        payload, err = parse_write_content("null")
        assert payload is None
        assert err is not None
        assert "object or array" in err

    def test_boolean_literal_returns_error(self) -> None:
        """JSON true/false are not object or array."""
        for content in ("true", "false"):
            payload, err = parse_write_content(content)
            assert payload is None
            assert err is not None

    def test_empty_object_valid(self) -> None:
        """Empty JSON object is valid."""
        payload, err = parse_write_content("{}")
        assert err is None
        assert payload == {}

    def test_empty_array_valid(self) -> None:
        """Empty JSON array is valid."""
        payload, err = parse_write_content("[]")
        assert err is None
        assert payload == []

    def test_dict_with_numeric_string_keys_accepted(self) -> None:
        """Dict with string keys that look numeric is valid JSON and accepted."""
        payload, err = parse_write_content('{"1": "a", "2": "b"}')
        assert err is None
        assert payload is not None
        assert payload == {"1": "a", "2": "b"}


class TestErrorResponse:
    """Unit tests for _error_response helper."""

    def test_includes_status_message_and_path(self) -> None:
        """Error response includes status, message, relative_path."""
        out = error_response("something failed", "cache/file.json")
        data = json.loads(out)
        assert data["status"] == "error"
        assert data["message"] == "something failed"
        assert data["relative_path"] == "cache/file.json"
        assert "error_type" not in data

    def test_includes_error_type_when_provided(self) -> None:
        """Error response includes error_type when provided."""
        out = error_response("oops", "x.json", error_type="ValueError")
        data = json.loads(out)
        assert data["error_type"] == "ValueError"

    def test_empty_message_and_path_serialize(self) -> None:
        """Empty message and path still produce valid JSON."""
        out = error_response("", "")
        data = json.loads(out)
        assert data["status"] == "error"
        assert data["message"] == ""
        assert data["relative_path"] == ""


class TestReadCacheJsonErrorPaths:
    """Tests for read_cache_json exception handling."""

    @pytest.mark.asyncio
    @pytest.mark.timeout(25)
    async def test_returns_error_when_read_raises_value_error(
        self, tmp_path: Path
    ) -> None:
        """Tool returns error JSON when _read_cache_json raises ValueError."""
        root = _project_root(tmp_path)
        with patch.dict(os.environ, {"CORTEX_USE_FALLBACK_ROOT": "1"}):
            with patch(
                "cortex.core.project_root_resolver.get_project_root",
                return_value=root,
            ):
                with patch(
                    "cortex.tools.cache_json_tools._read_cache_json",
                    new_callable=AsyncMock,
                    side_effect=ValueError("invalid path"),
                ):
                    result_str = await read_cache_json(relative_path="bad.json")
        result = json.loads(result_str)
        assert result["status"] == "error"
        assert "invalid path" in str(result.get("message", ""))

    @pytest.mark.asyncio
    @pytest.mark.timeout(25)
    async def test_returns_error_with_error_type_when_read_raises_generic(
        self, tmp_path: Path
    ) -> None:
        """Tool returns error JSON with error_type when read raises generic Exception."""
        root = _project_root(tmp_path)
        with patch.dict(os.environ, {"CORTEX_USE_FALLBACK_ROOT": "1"}):
            with patch(
                "cortex.core.project_root_resolver.get_project_root",
                return_value=root,
            ):
                with patch(
                    "cortex.tools.cache_json_tools._read_cache_json",
                    new_callable=AsyncMock,
                    side_effect=RuntimeError("lock timeout"),
                ):
                    result_str = await read_cache_json(relative_path="x.json")
        result = json.loads(result_str)
        assert result["status"] == "error"
        assert result.get("error_type") == "RuntimeError"


class TestWriteCacheJsonContentValidation:
    """Tests for write_cache_json content validation."""

    @pytest.mark.asyncio
    @pytest.mark.timeout(25)
    async def test_returns_error_for_json_number_content(self, tmp_path: Path) -> None:
        """Tool returns error when content is a JSON number (not object/array)."""
        root = _project_root(tmp_path)
        with patch.dict(os.environ, {"CORTEX_USE_FALLBACK_ROOT": "1"}):
            with patch(
                "cortex.core.project_root_resolver.get_project_root",
                return_value=root,
            ):
                result_str = await write_cache_json(
                    relative_path="n.json",
                    content="123",
                )
        result = json.loads(result_str)
        assert result["status"] == "error"
        assert "object or array" in str(result.get("message", ""))


class TestCacheJsonToolsEdgeCases:
    """Edge cases for read_cache_json and write_cache_json."""

    @pytest.mark.asyncio
    @pytest.mark.timeout(25)
    async def test_write_empty_object_succeeds_and_invokes_write(
        self, tmp_path: Path
    ) -> None:
        """Writing empty object {} returns success and calls _write_cache_json with {}."""
        root = _project_root(tmp_path)
        with patch.dict(os.environ, {"CORTEX_USE_FALLBACK_ROOT": "1"}):
            with patch(
                "cortex.core.project_root_resolver.get_project_root",
                return_value=root,
            ):
                with patch(
                    "cortex.tools.cache_json_tools._write_cache_json",
                    new_callable=AsyncMock,
                ) as mock_write:
                    result_str = await write_cache_json(
                        relative_path="empty.json",
                        content="{}",
                    )
        result = json.loads(result_str)
        assert result["status"] == "success"
        mock_write.assert_called_once()
        assert mock_write.call_args[0][2] == {}

    @pytest.mark.asyncio
    @pytest.mark.timeout(25)
    async def test_write_empty_array_succeeds_and_invokes_write(
        self, tmp_path: Path
    ) -> None:
        """Writing empty array [] returns success and calls _write_cache_json with []."""
        root = _project_root(tmp_path)
        with patch.dict(os.environ, {"CORTEX_USE_FALLBACK_ROOT": "1"}):
            with patch(
                "cortex.core.project_root_resolver.get_project_root",
                return_value=root,
            ):
                with patch(
                    "cortex.tools.cache_json_tools._write_cache_json",
                    new_callable=AsyncMock,
                ) as mock_write:
                    result_str = await write_cache_json(
                        relative_path="empty_arr.json",
                        content="[]",
                    )
        result = json.loads(result_str)
        assert result["status"] == "success"
        mock_write.assert_called_once()
        assert mock_write.call_args[0][2] == []

    @pytest.mark.asyncio
    @pytest.mark.timeout(25)
    async def test_write_returns_error_when_write_raises_value_error(
        self, tmp_path: Path
    ) -> None:
        """When _write_cache_json raises ValueError, tool returns error JSON."""
        root = _project_root(tmp_path)
        with patch.dict(os.environ, {"CORTEX_USE_FALLBACK_ROOT": "1"}):
            with patch(
                "cortex.core.project_root_resolver.get_project_root",
                return_value=root,
            ):
                with patch(
                    "cortex.tools.cache_json_tools._write_cache_json",
                    new_callable=AsyncMock,
                    side_effect=ValueError("Invalid cache key"),
                ):
                    result_str = await write_cache_json(
                        relative_path="x.json",
                        content='{"a": 1}',
                    )
        result = json.loads(result_str)
        assert result["status"] == "error"
        assert "Invalid cache key" in str(result.get("message", ""))
