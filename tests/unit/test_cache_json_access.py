"""Unit tests for cache_json_access (concurrent-safe .cortex/.cache JSON)."""

from pathlib import Path

import pytest

from cortex.core.cache_json_access import (
    read_cache_json,
    read_modify_write_cache_json,
    write_cache_json,
)
from cortex.core.exceptions import FileLockTimeoutError


def _project_root(tmp_path: Path) -> Path:
    """Create project root with .cortex/.cache."""
    root = tmp_path / "project"
    _ = (root / ".cortex" / ".cache").mkdir(parents=True)
    return root


class TestReadCacheJson:
    """Tests for read_cache_json."""

    @pytest.mark.asyncio
    async def test_returns_none_when_file_missing(self, tmp_path: Path) -> None:
        """Read missing file returns None."""
        root = _project_root(tmp_path)
        result = await read_cache_json(root, "usage/events/2026-01-01.json")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_dict_when_valid_object(self, tmp_path: Path) -> None:
        """Read valid JSON object returns dict."""
        root = _project_root(tmp_path)
        path = root / ".cortex" / ".cache" / "data.json"
        _ = path.parent.mkdir(parents=True, exist_ok=True)
        _ = path.write_text('{"a": 1, "b": "x"}')
        result = await read_cache_json(root, "data.json")
        assert result == {"a": 1, "b": "x"}

    @pytest.mark.asyncio
    async def test_returns_list_when_valid_array(self, tmp_path: Path) -> None:
        """Read valid JSON array returns list."""
        root = _project_root(tmp_path)
        path = root / ".cortex" / ".cache" / "usage" / "events" / "2026-02-02.json"
        _ = path.parent.mkdir(parents=True, exist_ok=True)
        _ = path.write_text('[{"tool": "x"}, {"tool": "y"}]')
        result = await read_cache_json(root, "usage/events/2026-02-02.json")
        assert result == [{"tool": "x"}, {"tool": "y"}]

    @pytest.mark.asyncio
    async def test_returns_none_when_invalid_json(self, tmp_path: Path) -> None:
        """Read invalid JSON returns None."""
        root = _project_root(tmp_path)
        path = root / ".cortex" / ".cache" / "bad.json"
        _ = path.parent.mkdir(parents=True, exist_ok=True)
        _ = path.write_text("not json {")
        result = await read_cache_json(root, "bad.json")
        assert result is None

    @pytest.mark.asyncio
    async def test_rejects_path_traversal(self, tmp_path: Path) -> None:
        """Relative key with .. raises ValueError."""
        root = _project_root(tmp_path)
        with pytest.raises(ValueError, match="path traversal"):
            _ = await read_cache_json(root, "usage/../events/file.json")

    @pytest.mark.asyncio
    async def test_rejects_leading_slash(self, tmp_path: Path) -> None:
        """Relative key starting with / raises ValueError."""
        root = _project_root(tmp_path)
        with pytest.raises(ValueError, match="absolute path"):
            _ = await read_cache_json(root, "/usage/events/file.json")


class TestWriteCacheJson:
    """Tests for write_cache_json."""

    @pytest.mark.asyncio
    async def test_write_then_read_roundtrip(self, tmp_path: Path) -> None:
        """Write then read returns same data."""
        root = _project_root(tmp_path)
        data: dict[str, object] = {"key": "value", "n": 42}
        await write_cache_json(root, "roundtrip.json", data)
        result = await read_cache_json(root, "roundtrip.json")
        assert result == data

    @pytest.mark.asyncio
    async def test_write_list(self, tmp_path: Path) -> None:
        """Write list then read returns list."""
        root = _project_root(tmp_path)
        payload: list[object] = [1, 2, {"a": "b"}]
        await write_cache_json(root, "subdir/list.json", payload)
        result = await read_cache_json(root, "subdir/list.json")
        assert result == payload


class TestReadModifyWriteCacheJson:
    """Tests for read_modify_write_cache_json."""

    @pytest.mark.asyncio
    async def test_append_to_missing_uses_default(self, tmp_path: Path) -> None:
        """When file missing, updater receives default."""
        root = _project_root(tmp_path)

        def append_one(current: list[object] | dict[str, object]) -> list[object]:
            lst = list(current) if isinstance(current, list) else []
            lst.append({"event": 1})
            return lst

        await read_modify_write_cache_json(
            root, "usage/events/2026-02-02.json", append_one, default=[]
        )
        result = await read_cache_json(root, "usage/events/2026-02-02.json")
        assert result == [{"event": 1}]

    @pytest.mark.asyncio
    async def test_append_to_existing(self, tmp_path: Path) -> None:
        """Append to existing list file."""
        root = _project_root(tmp_path)
        path = root / ".cortex" / ".cache" / "usage" / "events" / "2026-02-02.json"
        _ = path.parent.mkdir(parents=True, exist_ok=True)
        _ = path.write_text('[{"a": 1}]')

        def append_second(
            current: list[object] | dict[str, object],
        ) -> list[object]:
            lst = list(current) if isinstance(current, list) else []
            lst.append({"a": 2})
            return lst

        await read_modify_write_cache_json(
            root, "usage/events/2026-02-02.json", append_second, default=[]
        )
        result = await read_cache_json(root, "usage/events/2026-02-02.json")
        assert result == [{"a": 1}, {"a": 2}]


class TestLockTimeout:
    """Tests for lock timeout behavior."""

    @pytest.mark.asyncio
    async def test_read_raises_file_lock_timeout_when_locked(
        self, tmp_path: Path
    ) -> None:
        """Read raises FileLockTimeoutError when lock is held and timeout is short."""
        root = _project_root(tmp_path)
        path = root / ".cortex" / ".cache" / "locked.json"
        lock_path = path.with_suffix(path.suffix + ".lock")
        _ = path.parent.mkdir(parents=True, exist_ok=True)
        _ = path.write_text("{}")
        _ = lock_path.touch()

        with pytest.raises(FileLockTimeoutError, match="locked"):
            _ = await read_cache_json(root, "locked.json", timeout_seconds=0.1)

        _ = lock_path.unlink(missing_ok=True)
