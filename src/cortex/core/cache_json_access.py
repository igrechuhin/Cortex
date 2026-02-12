"""Concurrent-safe read/write of JSON files under .cortex/.cache.

All access to JSON files in .cortex/.cache MUST go through this module
(or the read_cache_json / write_cache_json MCP tools) so that multiple
chat sessions and processes get reliable, serialized access via file locking.
"""

import asyncio
import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import cast

from cortex.core.constants import (
    LOCK_POLL_INTERVAL_SECONDS,
    LOCK_TIMEOUT_SECONDS,
)
from cortex.core.exceptions import FileLockTimeoutError
from cortex.core.path_resolver import get_cache_path

from .async_file_utils import open_async_text_file

_DEFAULT_TIMEOUT = float(LOCK_TIMEOUT_SECONDS)


def _validate_relative_key(relative_key: str) -> None:
    """Reject path traversal and absolute paths."""
    if (
        ".." in relative_key
        or relative_key.startswith("/")
        or relative_key.startswith("\\")
    ):
        raise ValueError(
            f"Invalid cache key: {relative_key!r} (path traversal or absolute path)"
        )
    normalized = Path(relative_key)
    if normalized.is_absolute() or any(p == ".." for p in normalized.parts):
        raise ValueError(f"Invalid cache key: {relative_key!r}")


def _resolve_cache_file(project_root: Path, relative_key: str) -> Path:
    """Resolve relative_key under .cortex/.cache; validate it stays under cache."""
    _validate_relative_key(relative_key)
    cache_dir = get_cache_path(project_root, None)
    full = (cache_dir / relative_key).resolve()
    cache_resolved = cache_dir.resolve()
    try:
        _ = full.relative_to(cache_resolved)
    except ValueError:
        raise ValueError(
            f"Cache key {relative_key!r} resolves outside .cortex/.cache"
        ) from None
    return full


def _lock_path_for(file_path: Path) -> Path:
    """Path for the lock file (same pattern as FileSystemManager)."""
    return file_path.with_suffix(file_path.suffix + ".lock")


async def _acquire_lock(lock_path: Path, timeout_seconds: float) -> None:
    """Acquire file lock with timeout.

    Treats any existing lock older than a small safety window as stale and
    cleans it up before proceeding. This prevents broken sessions from
    permanently blocking access to usage/cache files.
    """
    start = asyncio.get_event_loop().time()
    while lock_path.exists():
        # Stale-lock cleanup: if the lock file is older than 180 seconds,
        # assume it was left behind by a crashed session and remove it.
        try:
            mtime = lock_path.stat().st_mtime
        except OSError:
            mtime = None
        if mtime is not None and (time.time() - mtime) > 180:
            try:
                lock_path.unlink()
                break
            except OSError:
                # If we fail to delete, fall back to normal timeout behaviour.
                pass

        if (asyncio.get_event_loop().time() - start) > timeout_seconds:
            raise FileLockTimeoutError(
                file_name=lock_path.stem,
                timeout_seconds=int(timeout_seconds),
            )
        await asyncio.sleep(LOCK_POLL_INTERVAL_SECONDS)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.touch()


async def _release_lock(lock_path: Path) -> None:
    """Release file lock."""
    try:
        if lock_path.exists():
            lock_path.unlink()
    except OSError:
        pass


async def read_cache_json(
    project_root: Path,
    relative_key: str,
    *,
    timeout_seconds: float = _DEFAULT_TIMEOUT,
) -> dict[str, object] | list[object] | None:
    """Read a JSON file from .cortex/.cache with lock. Returns None if missing/invalid."""
    path = _resolve_cache_file(project_root, relative_key)
    lock_path = _lock_path_for(path)
    await _acquire_lock(lock_path, timeout_seconds)
    try:
        if not path.exists():
            return None
        async with open_async_text_file(path, "r", "utf-8") as f:
            raw = await f.read()
        if not raw.strip():
            return None
        parsed: object = json.loads(raw)
        if isinstance(parsed, dict):
            d = cast(dict[str, object], parsed)
            return {str(k): v for k, v in d.items()}
        if isinstance(parsed, list):
            lst = cast(list[object], parsed)
            return list(lst)
        return None
    except (OSError, json.JSONDecodeError):
        return None
    finally:
        await _release_lock(lock_path)


async def write_cache_json(
    project_root: Path,
    relative_key: str,
    data: dict[str, object] | list[object],
    *,
    indent: int = 2,
    timeout_seconds: float = _DEFAULT_TIMEOUT,
) -> None:
    """Write a JSON file under .cortex/.cache with lock."""
    path = _resolve_cache_file(project_root, relative_key)
    lock_path = _lock_path_for(path)
    await _acquire_lock(lock_path, timeout_seconds)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(data, indent=indent)
        async with open_async_text_file(path, "w", "utf-8") as f:
            _ = await f.write(payload)
    finally:
        await _release_lock(lock_path)


async def _load_current_cached_value(
    path: Path,
    default: dict[str, object] | list[object],
) -> dict[str, object] | list[object]:
    """Load current value from path or return default if missing/invalid."""
    if not path.exists():
        return default
    try:
        async with open_async_text_file(path, "r", "utf-8") as f:
            raw = await f.read()
        if not raw.strip():
            return default
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            d = cast(dict[str, object], parsed)
            return {str(k): v for k, v in d.items()}
        if isinstance(parsed, list):
            lst = cast(list[object], parsed)
            return list(lst)
        return default
    except (OSError, json.JSONDecodeError):
        return default


async def _write_cached_value(
    path: Path,
    data: dict[str, object] | list[object],
    indent: int = 2,
) -> None:
    """Write data to path under .cortex/.cache."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=indent)
    async with open_async_text_file(path, "w", "utf-8") as f:
        _ = await f.write(payload)


async def read_modify_write_cache_json(
    project_root: Path,
    relative_key: str,
    updater: Callable[
        [dict[str, object] | list[object]],
        dict[str, object] | list[object],
    ],
    default: dict[str, object] | list[object],
    *,
    indent: int = 2,
    timeout_seconds: float = _DEFAULT_TIMEOUT,
) -> None:
    """Atomically read, update, and write a cache JSON file (single lock)."""
    path = _resolve_cache_file(project_root, relative_key)
    lock_path = _lock_path_for(path)
    await _acquire_lock(lock_path, timeout_seconds)
    try:
        current = await _load_current_cached_value(path, default)
        new_data = updater(current)
        await _write_cached_value(path, new_data, indent)
    finally:
        await _release_lock(lock_path)
