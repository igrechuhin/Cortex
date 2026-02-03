"""Unit tests for cortex.core.project_root_resolver."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# pyright: reportPrivateUsage=false
from cortex.core.project_root_resolver import (
    _file_uri_to_path,
    resolve_project_root_async,
)


class TestFileUriToPath:
    """Test _file_uri_to_path helper."""

    def test_file_uri_absolute_path(self) -> None:
        assert _file_uri_to_path("file:///Users/foo/bar") == Path("/Users/foo/bar")

    def test_file_uri_non_file_scheme_returns_none(self) -> None:
        assert _file_uri_to_path("https://example.com/path") is None

    def test_file_uri_empty_path_returns_none(self) -> None:
        assert _file_uri_to_path("file://") is None


class TestResolveProjectRootAsync:
    """Test resolve_project_root_async."""

    @pytest.mark.asyncio
    async def test_when_project_root_provided_returns_resolved(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / ".cortex" / "memory-bank").mkdir(parents=True)
        result = await resolve_project_root_async(str(tmp_path), None)
        assert result == tmp_path.resolve()

    @pytest.mark.asyncio
    async def test_when_ctx_has_roots_uses_first_file_uri(self, tmp_path: Path) -> None:
        root_uri = f"file://{tmp_path}"
        mock_root = MagicMock()
        mock_root.uri = root_uri
        mock_result = MagicMock()
        mock_result.roots = [mock_root]
        mock_session = AsyncMock()
        mock_session.list_roots = AsyncMock(return_value=mock_result)
        mock_ctx = MagicMock()
        mock_ctx.session = mock_session
        result = await resolve_project_root_async(None, mock_ctx)
        assert result == tmp_path.resolve()
        mock_session.list_roots.assert_called_once()

    @pytest.mark.asyncio
    async def test_when_ctx_none_falls_back_to_get_project_root(self) -> None:
        with patch(
            "cortex.core.project_root_resolver.get_project_root",
            return_value=Path("/fallback"),
        ) as mock_get:
            result = await resolve_project_root_async(None, None)
            assert result == Path("/fallback")
            mock_get.assert_called_once_with(None)

    @pytest.mark.asyncio
    async def test_when_list_roots_raises_falls_back(self) -> None:
        mock_session = AsyncMock()
        mock_session.list_roots = AsyncMock(
            side_effect=Exception("roots not supported")
        )
        mock_ctx = MagicMock()
        mock_ctx.session = mock_session
        with patch(
            "cortex.core.project_root_resolver.get_project_root",
            return_value=Path("/fallback"),
        ) as mock_get:
            result = await resolve_project_root_async(None, mock_ctx)
            assert result == Path("/fallback")
            mock_get.assert_called_once_with(None)
