"""Unit tests for compress_memory_bank aggregation."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from cortex.tools.compress.compress import CompressResult
from cortex.tools.memory_compress_tool import run_compress_memory_bank


@pytest.mark.timeout(20)
def test_run_compress_skips_roadmap(tmp_path: Path) -> None:
    """roadmap.md is not passed to compress_file."""
    mb = tmp_path / ".cortex" / "memory-bank"
    mb.mkdir(parents=True)
    _ = (tmp_path / "CLAUDE.md").write_text("# T\n" + "word " * 20, encoding="utf-8")
    _ = (mb / "roadmap.md").write_text("x " * 100, encoding="utf-8")

    with patch("cortex.tools.memory_compress_tool.compress_file") as mock_cf:
        mock_cf.return_value = CompressResult(
            success=True,
            path=None,
            token_ratio=0.7,
        )
        result = run_compress_memory_bank(tmp_path)

    assert result.files_processed == 1
    assert result.files_compressed == 1
    called_paths = {c[0][0] for c in mock_cf.call_args_list}
    assert all(p.name != "roadmap.md" for p in called_paths)


@pytest.mark.timeout(20)
def test_run_compress_all_failures_aggregate(tmp_path: Path) -> None:
    """All failures increment files_failed and average ratio stays default."""
    _ = (tmp_path / "CLAUDE.md").write_text("one two", encoding="utf-8")

    with patch("cortex.tools.memory_compress_tool.compress_file") as mock_cf:
        mock_cf.return_value = CompressResult(
            success=False,
            path=None,
            token_ratio=0.9,
            errors=["bad"],
        )
        result = run_compress_memory_bank(tmp_path)

    assert result.files_failed == 1
    assert result.files_compressed == 0
    assert result.average_token_ratio == 1.0


@pytest.mark.asyncio
@pytest.mark.timeout(20)
async def test_compress_memory_bank_mcp_json_shape(tmp_path: Path) -> None:
    """MCP handler returns success wrapper JSON."""
    _ = (tmp_path / "CLAUDE.md").write_text("a b c", encoding="utf-8")

    from cortex.tools.memory_compress_tool import compress_memory_bank

    with (
        patch(
            "cortex.tools.memory_compress_tool.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=tmp_path,
        ),
        patch("cortex.tools.memory_compress_tool.compress_file") as mock_cf,
    ):
        mock_cf.return_value = CompressResult(success=True, token_ratio=0.6)
        raw = await compress_memory_bank(project_root=None, ctx=None)

    data = json.loads(raw)
    assert data["status"] == "success"
    assert data["result"]["files_compressed"] == 1
