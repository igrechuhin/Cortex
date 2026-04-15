"""Integration tests for manage_file operation='search'."""

import json
from pathlib import Path
from typing import cast

import pytest

from cortex.tools.files.manage_file_helpers import execute_file_operation
from cortex.tools.files.operation_helpers import FileOperation


def _setup_cortex(root: Path, content: str, filename: str = "activeContext.md") -> None:
    """Create minimal .cortex memory-bank with a test file."""
    mb = root / ".cortex" / "memory-bank"
    mb.mkdir(parents=True, exist_ok=True)
    _: int = (mb / filename).write_text(content)


def _parse_response(raw: str) -> dict[str, object]:
    parsed = json.loads(raw)
    assert isinstance(parsed, dict)
    return cast(dict[str, object], parsed)


async def _search(root: Path, query: str, **kwargs: object) -> dict[str, object]:
    payload = json.dumps({"query": query, **kwargs})
    result = await execute_file_operation(
        root, "_search", FileOperation.SEARCH, payload, False, None, None
    )
    return _parse_response(result)


class TestManageFileSearch:
    @pytest.mark.asyncio
    async def test_search_returns_results(self, tmp_path: Path) -> None:
        _setup_cortex(
            tmp_path,
            "# Active Context\n\nTemporal memory indexing stores time-series facts.\n",
        )
        result = await _search(tmp_path, "temporal memory")
        assert result["status"] == "success"
        results_raw = result["results"]
        assert isinstance(results_raw, list)
        typed_results = cast(list[object], results_raw)
        assert len(typed_results) >= 1

    @pytest.mark.asyncio
    async def test_search_empty_query_returns_error(self, tmp_path: Path) -> None:
        _setup_cortex(tmp_path, "Some content here.\n")
        result = await _search(tmp_path, "")
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_search_no_content_returns_error(self, tmp_path: Path) -> None:
        raw = await execute_file_operation(
            tmp_path, "_search", FileOperation.SEARCH, None, False, None, None
        )
        assert _parse_response(raw)["status"] == "error"

    @pytest.mark.asyncio
    async def test_search_invalid_json_returns_error(self, tmp_path: Path) -> None:
        raw = await execute_file_operation(
            tmp_path,
            "_search",
            FileOperation.SEARCH,
            "not valid json",
            False,
            None,
            None,
        )
        assert _parse_response(raw)["status"] == "error"

    @pytest.mark.asyncio
    async def test_search_result_fields(self, tmp_path: Path) -> None:
        _setup_cortex(
            tmp_path,
            "# Context\n\nFastMCP startup crash during initialization.\n",
        )
        result = await _search(tmp_path, "FastMCP startup crash")
        assert result["status"] == "success"
        results_raw = result["results"]
        assert isinstance(results_raw, list)
        typed_results = cast(list[object], results_raw)
        if typed_results:
            first = typed_results[0]
            assert isinstance(first, dict)
            first_typed = cast(dict[str, object], first)
            for field in ("text", "source", "score", "heading", "start_line"):
                assert field in first_typed

    @pytest.mark.asyncio
    async def test_search_top_k_respected(self, tmp_path: Path) -> None:
        mb = tmp_path / ".cortex" / "memory-bank"
        mb.mkdir(parents=True, exist_ok=True)
        for i in range(10):
            _: int = (mb / f"doc{i}.md").write_text(
                f"# Doc {i}\n\nSearch term match content for document number {i}.\n"
            )
        result = await _search(tmp_path, "Search term match", top_k=3)
        assert result["status"] == "success"
        results_raw = result["results"]
        assert isinstance(results_raw, list)
        typed_results = cast(list[object], results_raw)
        assert len(typed_results) <= 3

    @pytest.mark.asyncio
    async def test_search_with_file_filter(self, tmp_path: Path) -> None:
        mb = tmp_path / ".cortex" / "memory-bank"
        mb.mkdir(parents=True, exist_ok=True)
        _a: int = (mb / "activeContext.md").write_text(
            "Target term in active context file content.\n"
        )
        _b: int = (mb / "roadmap.md").write_text(
            "Target term in roadmap file content.\n"
        )
        result = await _search(
            tmp_path, "Target term", file_filter=["activeContext.md"]
        )
        assert result["status"] == "success"
        results_raw = result["results"]
        assert isinstance(results_raw, list)
        for item in cast(list[object], results_raw):
            assert isinstance(item, dict)
            item_typed = cast(dict[str, object], item)
            assert "roadmap.md" not in str(item_typed.get("source", ""))

    @pytest.mark.asyncio
    async def test_existing_operations_unaffected(self, tmp_path: Path) -> None:
        """Regression: adding search must not break read/write/metadata."""
        _setup_cortex(tmp_path, "# Brief\n\nProject overview.\n", "projectBrief.md")
        _m: int = (
            tmp_path / ".cortex" / "memory-bank" / ".metadata_index.json"
        ).write_text("{}")
        raw = await execute_file_operation(
            tmp_path, "projectBrief.md", FileOperation.METADATA, None, False, None, None
        )
        data = _parse_response(raw)
        assert "status" in data
