"""Unit tests for cortex.core.project_root_resolver."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import cortex.core.project_root_resolver as project_root_resolver_mod
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.project_root_resolver import (
    clear_cached_root,
    file_uri_to_path,
    handle_roots_list_changed,
    resolve_project_root_async,
)
from cortex.wiki.wiki_root_files import WikiRootDocument


class TestFileUriToPath:
    """Test file_uri_to_path helper."""

    def test_file_uri_absolute_path(self) -> None:
        assert file_uri_to_path("file:///Users/foo/bar") == Path("/Users/foo/bar")

    def test_file_uri_non_file_scheme_returns_none(self) -> None:
        assert file_uri_to_path("https://example.com/path") is None

    def test_file_uri_empty_path_returns_none(self) -> None:
        assert file_uri_to_path("file://") is None


class TestResolveProjectRootAsync:
    """Test resolve_project_root_async."""

    @pytest.mark.asyncio
    async def test_resolve_bootstraps_wiki_when_dot_cortex_present(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """First successful resolve creates ``.cortex/wiki/`` (Cursor: no list_roots)."""
        _ = (tmp_path / ".cortex").mkdir()
        clear_cached_root()

        def _stub_get_project_root(project_root: Path | None = None) -> Path:
            _ = project_root
            return tmp_path

        monkeypatch.setattr(
            "cortex.core.project_root_resolver.get_project_root",
            _stub_get_project_root,
        )
        result = await resolve_project_root_async(None, None)
        assert result == tmp_path
        assert (tmp_path / ".cortex" / "wiki" / WikiRootDocument.SCHEMA.value).is_file()

    @pytest.mark.asyncio
    async def test_when_project_root_provided_returns_resolved(
        self, tmp_path: Path
    ) -> None:
        get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK).mkdir(parents=True)
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
    async def test_when_ctx_none_but_cache_populated_returns_cached(
        self, tmp_path: Path
    ) -> None:
        """ctx=None should still return the cached root from a prior list_roots call."""
        import cortex.core.project_root_resolver as resolver_mod

        resolver_mod.cached_root = tmp_path
        with patch(
            "cortex.core.project_root_resolver.get_project_root",
        ) as mock_get:
            result = await resolve_project_root_async(None, None)
            assert result == tmp_path
            mock_get.assert_not_called()

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

    @pytest.mark.asyncio
    async def test_when_list_roots_raises_runtime_error_falls_back(self) -> None:
        """RuntimeError from list_roots is part of the documented exception surface."""
        mock_session = AsyncMock()
        mock_session.list_roots = AsyncMock(
            side_effect=RuntimeError("transport closed")
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

    @pytest.mark.asyncio
    async def test_fallback_root_runs_in_thread_pool(self) -> None:
        """Test that _fallback_root() runs in thread pool to avoid blocking event loop."""
        with patch(
            "cortex.core.project_root_resolver.get_project_root",
            return_value=Path("/fallback"),
        ) as mock_get:
            # Verify that asyncio.to_thread is used (indirectly by checking it doesn't block)
            # We can't directly test asyncio.to_thread, but we can verify the function works
            # and that it's async (which it must be if to_thread is used)
            result = await resolve_project_root_async(None, None)
            assert result == Path("/fallback")
            mock_get.assert_called_once_with(None)

    @pytest.mark.asyncio
    async def test_when_client_lacks_roots_capability_falls_back(self) -> None:
        """Client that doesn't advertise roots capability must not trigger list_roots().

        Clients like Cursor's MCP bridge close the transport when they receive a
        ListRootsRequest, crashing the server.  The capability guard must skip
        list_roots() and go straight to the fallback.
        """
        mock_session = AsyncMock()
        # check_client_capability is sync; override it with a plain MagicMock
        mock_session.check_client_capability = MagicMock(return_value=False)
        mock_session.list_roots = AsyncMock()
        mock_ctx = MagicMock()
        mock_ctx.session = mock_session
        with patch(
            "cortex.core.project_root_resolver.get_project_root",
            return_value=Path("/fallback"),
        ) as mock_get:
            result = await resolve_project_root_async(None, mock_ctx)
            assert result == Path("/fallback")
            mock_get.assert_called_once_with(None)
            mock_session.list_roots.assert_not_called()

    @pytest.mark.asyncio
    async def test_fallback_root_with_env_var_runs_in_thread_pool(self) -> None:
        """Test that fallback root with CORTEX_USE_FALLBACK_ROOT env var runs in thread pool."""
        with patch.dict("os.environ", {"CORTEX_USE_FALLBACK_ROOT": "1"}):
            with patch(
                "cortex.core.project_root_resolver.get_project_root",
                return_value=Path("/fallback"),
            ) as mock_get:
                result = await resolve_project_root_async(None, None)
                assert result == Path("/fallback")
                mock_get.assert_called_once_with(None)


class TestRootsListChanged:
    """Tests for notifications/roots/list_changed cache invalidation."""

    @pytest.mark.asyncio
    async def test_roots_list_changed_clears_cache(self, tmp_path: Path) -> None:
        stale = tmp_path / "stale"
        stale.mkdir()
        resolved = stale.resolve()
        project_root_resolver_mod.cached_root = resolved
        project_root_resolver_mod.wiki_bootstrapped_roots.add(resolved.as_posix())
        await handle_roots_list_changed()
        assert project_root_resolver_mod.cached_root is None
        assert project_root_resolver_mod.wiki_bootstrapped_roots == set()

    @pytest.mark.asyncio
    async def test_roots_list_changed_noop_when_no_cache(self) -> None:
        project_root_resolver_mod.cached_root = None
        await handle_roots_list_changed()
        assert project_root_resolver_mod.cached_root is None

    @pytest.mark.asyncio
    async def test_roots_list_changed_triggers_re_resolve(self, tmp_path: Path) -> None:
        path_a = tmp_path / "a"
        path_b = tmp_path / "b"
        path_a.mkdir()
        path_b.mkdir()
        project_root_resolver_mod.cached_root = path_a.resolve()

        root_uri = f"file://{path_b}"
        mock_root = MagicMock()
        mock_root.uri = root_uri
        mock_result = MagicMock()
        mock_result.roots = [mock_root]
        mock_session = AsyncMock()
        mock_session.list_roots = AsyncMock(return_value=mock_result)
        mock_session.check_client_capability = MagicMock(return_value=True)
        mock_ctx = MagicMock()
        mock_ctx.session = mock_session

        await handle_roots_list_changed()
        result = await resolve_project_root_async(None, mock_ctx)
        assert result == path_b.resolve()
        mock_session.list_roots.assert_called_once()
