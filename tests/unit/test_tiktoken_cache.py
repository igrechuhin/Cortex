"""Unit tests for tiktoken_cache module."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

from cortex.core.tiktoken_cache import (
    ensure_bundled_cache_available,
    get_bundled_cache_dir,
    setup_tiktoken_cache,
)


def test_get_bundled_cache_dir_when_exists() -> None:
    """get_bundled_cache_dir returns path when bundled cache directory exists."""
    mock_cache = MagicMock(spec=Path)
    mock_cache.exists.return_value = True
    mock_cache.is_dir.return_value = True

    # Mock the Path chain: Path(__file__).parent.parent / "resources" / "tiktoken_cache"
    mock_file = MagicMock()
    mock_parent = MagicMock()
    mock_grandparent = MagicMock()
    # First __truediv__("resources") returns an intermediate path
    mock_intermediate = MagicMock()
    # Second __truediv__("tiktoken_cache") returns the final cache path
    mock_intermediate.__truediv__ = MagicMock(return_value=mock_cache)
    mock_grandparent.__truediv__ = MagicMock(return_value=mock_intermediate)
    mock_parent.parent = mock_grandparent
    mock_file.parent = mock_parent

    with patch("cortex.core.tiktoken_cache.Path", return_value=mock_file):
        result = get_bundled_cache_dir()
        assert result == mock_cache


def test_get_bundled_cache_dir_when_not_exists() -> None:
    """get_bundled_cache_dir returns None when bundled cache directory doesn't exist."""
    mock_cache = MagicMock(spec=Path)
    mock_cache.exists.return_value = False

    mock_file = MagicMock()
    mock_parent = MagicMock()
    mock_grandparent = MagicMock()
    mock_intermediate = MagicMock()
    mock_intermediate.__truediv__ = MagicMock(return_value=mock_cache)
    mock_grandparent.__truediv__ = MagicMock(return_value=mock_intermediate)
    mock_parent.parent = mock_grandparent
    mock_file.parent = mock_parent

    with patch("cortex.core.tiktoken_cache.Path", return_value=mock_file):
        result = get_bundled_cache_dir()
        assert result is None


def test_get_bundled_cache_dir_when_not_dir() -> None:
    """get_bundled_cache_dir returns None when path exists but is not a directory."""
    mock_cache = MagicMock(spec=Path)
    mock_cache.exists.return_value = True
    mock_cache.is_dir.return_value = False

    mock_file = MagicMock()
    mock_parent = MagicMock()
    mock_grandparent = MagicMock()
    mock_intermediate = MagicMock()
    mock_intermediate.__truediv__ = MagicMock(return_value=mock_cache)
    mock_grandparent.__truediv__ = MagicMock(return_value=mock_intermediate)
    mock_parent.parent = mock_grandparent
    mock_file.parent = mock_parent

    with patch("cortex.core.tiktoken_cache.Path", return_value=mock_file):
        result = get_bundled_cache_dir()
        assert result is None


def test_get_bundled_cache_dir_handles_exception() -> None:
    """get_bundled_cache_dir returns None when exception occurs."""
    with patch("cortex.core.tiktoken_cache.Path", side_effect=Exception("Test error")):
        result = get_bundled_cache_dir()
        assert result is None


def test_setup_tiktoken_cache_when_use_bundled_false() -> None:
    """setup_tiktoken_cache returns False when use_bundled is False."""
    result = setup_tiktoken_cache(use_bundled=False)
    assert result is False


def test_setup_tiktoken_cache_when_bundled_cache_none() -> None:
    """setup_tiktoken_cache returns False when bundled cache is None."""
    with patch("cortex.core.tiktoken_cache.get_bundled_cache_dir", return_value=None):
        result = setup_tiktoken_cache(use_bundled=True)
        assert result is False


def test_setup_tiktoken_cache_when_env_already_set() -> None:
    """setup_tiktoken_cache returns False when TIKTOKEN_CACHE_DIR is already set."""
    with patch("cortex.core.tiktoken_cache.get_bundled_cache_dir") as mock_get:
        mock_cache = Path("/test/cache")
        mock_get.return_value = mock_cache
        with patch.dict(os.environ, {"TIKTOKEN_CACHE_DIR": "/existing/cache"}):
            result = setup_tiktoken_cache(use_bundled=True)
            assert result is False
            assert os.environ["TIKTOKEN_CACHE_DIR"] == "/existing/cache"


def test_setup_tiktoken_cache_sets_env_when_not_set() -> None:
    """setup_tiktoken_cache sets TIKTOKEN_CACHE_DIR when not already set."""
    with patch("cortex.core.tiktoken_cache.get_bundled_cache_dir") as mock_get:
        mock_cache = Path("/test/cache")
        mock_get.return_value = mock_cache
        with patch.dict(os.environ, {}, clear=True):
            result = setup_tiktoken_cache(use_bundled=True)
            assert result is True
            assert os.environ["TIKTOKEN_CACHE_DIR"] == str(mock_cache)


def test_ensure_bundled_cache_available_when_cache_none() -> None:
    """ensure_bundled_cache_available returns False when bundled cache is None."""
    with patch("cortex.core.tiktoken_cache.get_bundled_cache_dir", return_value=None):
        result = ensure_bundled_cache_available()
        assert result is False


def test_ensure_bundled_cache_available_when_not_exists() -> None:
    """ensure_bundled_cache_available returns False when directory doesn't exist."""
    mock_cache = MagicMock(spec=Path)
    mock_cache.exists.return_value = False

    with patch(
        "cortex.core.tiktoken_cache.get_bundled_cache_dir", return_value=mock_cache
    ):
        result = ensure_bundled_cache_available()
        assert result is False


def test_ensure_bundled_cache_available_when_empty() -> None:
    """ensure_bundled_cache_available returns False when directory has no files."""
    mock_cache = MagicMock(spec=Path)
    mock_cache.exists.return_value = True
    mock_cache.glob.return_value = []

    with patch(
        "cortex.core.tiktoken_cache.get_bundled_cache_dir", return_value=mock_cache
    ):
        result = ensure_bundled_cache_available()
        assert result is False


def test_ensure_bundled_cache_available_when_has_files() -> None:
    """ensure_bundled_cache_available returns True when directory has files."""
    mock_cache = MagicMock(spec=Path)
    mock_cache.exists.return_value = True
    mock_cache.glob.return_value = [
        Path("/test/cache/file1"),
        Path("/test/cache/file2"),
    ]

    with patch(
        "cortex.core.tiktoken_cache.get_bundled_cache_dir", return_value=mock_cache
    ):
        result = ensure_bundled_cache_available()
        assert result is True


def test_ensure_bundled_cache_available_handles_exception() -> None:
    """ensure_bundled_cache_available returns False when exception occurs."""
    mock_cache = MagicMock(spec=Path)
    mock_cache.exists.return_value = True
    mock_cache.glob.side_effect = Exception("Test error")

    with patch(
        "cortex.core.tiktoken_cache.get_bundled_cache_dir", return_value=mock_cache
    ):
        result = ensure_bundled_cache_available()
        assert result is False
