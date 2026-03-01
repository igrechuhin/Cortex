"""Unit tests for markdown_lint_cache module."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from cortex.tools.files.markdown_lint_cache import (
    MarkdownLintIndex,
    load_markdown_lint_index,
    load_markdown_lint_index_safe,
    save_markdown_lint_index,
)


class TestMarkdownLintIndex:
    """Tests for MarkdownLintIndex model."""

    def test_default_empty(self):
        """Default index has empty files and version 2.0."""
        idx = MarkdownLintIndex()
        assert idx.version == "2.0"
        assert idx.files == {}

    def test_with_files(self):
        """Index accepts files dict."""
        idx = MarkdownLintIndex(files={"a.md": "sha256:abc", "b.md": "sha256:def"})
        assert len(idx.files) == 2
        assert idx.files["a.md"] == "sha256:abc"

    def test_empty_files_explicit(self):
        """Index with explicit empty files dict."""
        idx = MarkdownLintIndex(files={})
        assert idx.files == {}
        assert idx.version == "2.0"


class TestLoadMarkdownLintIndex:
    """Tests for load_markdown_lint_index."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_raw_none(self, tmp_path: Path):
        """When read_cache_json returns None, returns empty index."""
        with patch(
            "cortex.tools.files.markdown_lint_cache.read_cache_json",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await load_markdown_lint_index(tmp_path)
        assert result.files == {}
        assert result.version == "2.0"

    @pytest.mark.asyncio
    async def test_returns_empty_when_raw_not_dict(self, tmp_path: Path):
        """When raw is not a dict, returns empty index."""
        with patch(
            "cortex.tools.files.markdown_lint_cache.read_cache_json",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await load_markdown_lint_index(tmp_path)
        assert result.files == {}

    @pytest.mark.asyncio
    async def test_returns_validated_index_when_valid_dict(self, tmp_path: Path):
        """When raw is valid v2 dict, returns validated index."""
        raw = {"version": "2.0", "files": {"f.md": "sha256:xyz"}}
        with patch(
            "cortex.tools.files.markdown_lint_cache.read_cache_json",
            new_callable=AsyncMock,
            return_value=raw,
        ):
            result = await load_markdown_lint_index(tmp_path)
        assert result.files == {"f.md": "sha256:xyz"}
        assert result.version == "2.0"

    @pytest.mark.asyncio
    async def test_returns_empty_on_validation_error(self, tmp_path: Path):
        """When model_validate raises, returns empty index."""
        with patch(
            "cortex.tools.files.markdown_lint_cache.read_cache_json",
            new_callable=AsyncMock,
            return_value={"version": "1.0", "invalid": True},
        ):
            result = await load_markdown_lint_index(tmp_path)
        assert result.files == {}

    @pytest.mark.asyncio
    async def test_returns_empty_index_when_raw_empty_dict(self, tmp_path: Path):
        """When raw is valid empty dict, returns index with empty files."""
        with patch(
            "cortex.tools.files.markdown_lint_cache.read_cache_json",
            new_callable=AsyncMock,
            return_value={"version": "2.0", "files": {}},
        ):
            result = await load_markdown_lint_index(tmp_path)
        assert result.files == {}
        assert result.version == "2.0"


class TestLoadMarkdownLintIndexSafe:
    """Tests for load_markdown_lint_index_safe."""

    @pytest.mark.asyncio
    async def test_returns_empty_and_logs_on_exception(self, tmp_path: Path):
        """When load_markdown_lint_index raises, returns empty and logs warning."""
        with (
            patch(
                "cortex.tools.files.markdown_lint_cache.load_markdown_lint_index",
                new_callable=AsyncMock,
                side_effect=RuntimeError("cache read failed"),
            ),
            patch(
                "cortex.tools.files.markdown_lint_cache.log_client",
                new_callable=AsyncMock,
            ) as mock_log,
        ):
            result = await load_markdown_lint_index_safe(tmp_path, ctx=None)
        assert result.files == {}
        mock_log.assert_called_once()
        assert "Failed to load markdown lint cache" in mock_log.call_args[0][2]


class TestSaveMarkdownLintIndex:
    """Tests for save_markdown_lint_index."""

    @pytest.mark.asyncio
    async def test_writes_index_via_cache(self, tmp_path: Path) -> None:
        """save_markdown_lint_index calls write_cache_json with serialized index."""
        index = MarkdownLintIndex(files={"a.md": "sha256:aa", "b.md": "sha256:bb"})
        with (
            patch(
                "cortex.tools.files.markdown_lint_cache.write_cache_json",
                new_callable=AsyncMock,
            ) as mock_write,
        ):
            await save_markdown_lint_index(tmp_path, index)
        mock_write.assert_called_once()
        args = mock_write.call_args[0]
        assert args[0] == tmp_path
        assert args[1] == "markdown-lint-index.json"
        payload = args[2]
        assert payload.get("version") == "2.0"
        assert payload.get("files") == {"a.md": "sha256:aa", "b.md": "sha256:bb"}

    @pytest.mark.asyncio
    async def test_handles_save_failure_gracefully(self, tmp_path: Path) -> None:
        """When write_cache_json raises, save logs and does not propagate."""
        index = MarkdownLintIndex()
        with (
            patch(
                "cortex.tools.files.markdown_lint_cache.write_cache_json",
                new_callable=AsyncMock,
                side_effect=OSError("disk full"),
            ),
            patch(
                "cortex.tools.files.markdown_lint_cache.log_client",
                new_callable=AsyncMock,
            ) as mock_log,
        ):
            await save_markdown_lint_index(tmp_path, index)
        mock_log.assert_called_once()
        assert "Failed to save markdown lint cache" in mock_log.call_args[0][2]
