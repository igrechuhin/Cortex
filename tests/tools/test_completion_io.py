"""Tests for plan completion file I/O helpers (narrow exception handling)."""

from pathlib import Path
from unittest.mock import patch

import pytest

from cortex.core.exceptions import FileConflictError, FileLockTimeoutError
from cortex.tools.plans.completion_io import read_file, write_progress, write_roadmap


def test_read_file_returns_error_on_permission_denied(tmp_path: Path) -> None:
    """read_file maps OSError from read_text to (None, message)."""
    path = tmp_path / "x.md"
    _ = path.write_text("ok", encoding="utf-8")
    with patch.object(
        Path,
        "read_text",
        side_effect=PermissionError(13, "Permission denied"),
    ):
        content, err = read_file(path)
    assert content is None
    assert err is not None
    assert "Permission denied" in err or "13" in err


def test_read_file_returns_error_on_unicode_decode_error(tmp_path: Path) -> None:
    """read_file maps UnicodeDecodeError to (None, message)."""
    path = tmp_path / "x.md"
    _ = path.write_bytes(b"\xff\xfe")
    content, err = read_file(path)
    assert content is None
    assert err is not None


@pytest.mark.asyncio
async def test_write_progress_returns_os_error_message(tmp_path: Path) -> None:
    """write_progress returns str(OSError) for write failures."""
    with patch.object(Path, "write_text", side_effect=OSError("disk full")):
        err = await write_progress(tmp_path / "p.md", "x", project_root=None)
    assert err is not None
    assert "disk full" in err


@pytest.mark.asyncio
async def test_write_roadmap_returns_os_error_message(tmp_path: Path) -> None:
    """write_roadmap returns str(OSError) for write failures."""
    with patch.object(Path, "write_text", side_effect=PermissionError("no")):
        err = await write_roadmap(tmp_path / "r.md", "# ok", project_root=None)
    assert err is not None


@pytest.mark.asyncio
async def test_write_progress_maps_file_conflict(tmp_path: Path) -> None:
    """FileConflictError is returned as message, not raised."""

    def boom(*_args: object, **_kwargs: object) -> None:
        raise FileConflictError("f.md", "a" * 64, "b" * 64)

    with patch.object(Path, "write_text", side_effect=boom):
        err = await write_progress(tmp_path / "p.md", "x", project_root=None)
    assert err is not None
    assert "File f.md was modified externally" in err


@pytest.mark.asyncio
async def test_write_progress_maps_lock_timeout(tmp_path: Path) -> None:
    """FileLockTimeoutError is returned as message."""

    def boom(*_args: object, **_kwargs: object) -> None:
        raise FileLockTimeoutError("f.md", 30)

    with patch.object(Path, "write_text", side_effect=boom):
        err = await write_progress(tmp_path / "p.md", "x", project_root=None)
    assert err is not None
    assert "Could not acquire lock" in err
