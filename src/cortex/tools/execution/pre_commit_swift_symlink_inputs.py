"""Cache file-target SHA-256 digests for trusted local SwiftPM test evidence."""

# cspell:words birthtime

from __future__ import annotations

import hashlib
import math
import os
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from cortex.core.path_resolver import CortexResourceType, get_cortex_path

SWIFT_SYMLINK_CACHE_FILENAME = "swiftpm-symlink-digests-v1.json"


class _TargetMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    link_text: str
    resolved_path: str
    size: int = Field(ge=0)
    creation_time: str
    mtime_ns: int


class _CachedTarget(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    metadata: _TargetMetadata
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class _CacheFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    targets: dict[str, _CachedTarget] = Field(default_factory=dict[str, _CachedTarget])


@dataclass(frozen=True, slots=True)
class _LinkSnapshot:
    path: Path
    target: Path
    link_stat: os.stat_result
    target_stat: os.stat_result
    metadata: _TargetMetadata


def _creation_stamp(info: os.stat_result) -> str:
    nanoseconds = getattr(info, "st_birthtime_ns", None)
    if isinstance(nanoseconds, int):
        return str(nanoseconds)
    # AI: macOS Python may expose creation time only as float seconds.
    # Preserve all available precision and never substitute a different clock.
    seconds = getattr(info, "st_birthtime", None)
    if isinstance(seconds, float) and math.isfinite(seconds):
        return seconds.hex()
    raise ValueError("SwiftPM link target has no creation timestamp")


def _snapshot(path: Path) -> _LinkSnapshot:
    link_stat = path.lstat()
    if not stat.S_ISLNK(link_stat.st_mode) or path.parent.resolve() != path.parent:
        raise ValueError("Unsupported SwiftPM symlink path")
    link_text = os.readlink(path)
    target = path.resolve(strict=True)
    target_stat = target.lstat()
    if not stat.S_ISREG(target_stat.st_mode):
        raise ValueError("SwiftPM symlink target is not a regular file")
    modified_ns: object = getattr(target_stat, "st_mtime_ns", None)
    if not isinstance(modified_ns, int):
        raise ValueError("SwiftPM link target has no modification timestamp")
    return _LinkSnapshot(
        path=path,
        target=target,
        link_stat=link_stat,
        target_stat=target_stat,
        metadata=_TargetMetadata(
            link_text=link_text,
            resolved_path=str(target),
            size=target_stat.st_size,
            creation_time=_creation_stamp(target_stat),
            mtime_ns=modified_ns,
        ),
    )


def _stat_identity(info: os.stat_result) -> tuple[int, ...]:
    # AI: Reading can update atime. Compare identity, mode, and write/change
    # clocks instead, with nanosecond precision where Python exposes it.
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def _verify_snapshot(before: _LinkSnapshot) -> None:
    after = _snapshot(before.path)
    if (
        after.metadata != before.metadata
        or _stat_identity(after.link_stat) != _stat_identity(before.link_stat)
        or _stat_identity(after.target_stat) != _stat_identity(before.target_stat)
    ):
        raise ValueError("SwiftPM symlink changed during fingerprinting")


def _open_target(path: str, flags: int) -> int:
    return os.open(path, flags | os.O_NOFOLLOW | os.O_NONBLOCK)


def _read_target_digest(snapshot: _LinkSnapshot) -> str:
    expected = _stat_identity(snapshot.target_stat)
    with open(snapshot.target, "rb", opener=_open_target) as source:
        if _stat_identity(os.fstat(source.fileno())) != expected:
            raise ValueError("SwiftPM symlink target changed before reading")
        sha256 = hashlib.file_digest(source, "sha256").hexdigest()
        if _stat_identity(os.fstat(source.fileno())) != expected:
            raise ValueError("SwiftPM symlink target changed while reading")
        return sha256


def _confirm_cached_target(snapshot: _LinkSnapshot) -> None:
    # AI: A metadata cache hit must still prove the worker can open the target.
    fd = _open_target(str(snapshot.target), os.O_RDONLY)
    try:
        if _stat_identity(os.fstat(fd)) != _stat_identity(snapshot.target_stat):
            raise ValueError("SwiftPM symlink target changed before validation")
    finally:
        os.close(fd)


def _load_cache(path: Path) -> _CacheFile:
    try:
        return _CacheFile.model_validate_json(path.read_bytes(), strict=True)
    except (FileNotFoundError, ValidationError):
        return _CacheFile()


class TrustedSymlinkInputs:
    """Snapshot one checkout's file links and cache only validated digests."""

    def __init__(self, root: Path, paths: list[str]) -> None:
        self._snapshots = {
            name: _snapshot(root / name) for name in paths if (root / name).is_symlink()
        }
        cache_dir = get_cortex_path(root, CortexResourceType.SESSION)
        self._path = (
            cache_dir / SWIFT_SYMLINK_CACHE_FILENAME if self._snapshots else None
        )
        if self._path is not None and self._path.resolve() != self._path:
            raise ValueError("Unsupported SwiftPM symlink cache path")
        self._previous = _load_cache(self._path) if self._path else _CacheFile()
        self._observed = _CacheFile()

    def fingerprint_fields(self, relative: str) -> tuple[bytes, ...] | None:
        """Identify a linked file independently of its cache freshness stamps."""
        snapshot = self._snapshots.get(relative)
        if snapshot is None:
            return None
        entry = self._previous.targets.get(relative)
        if entry is None or entry.metadata != snapshot.metadata:
            entry = _CachedTarget(
                metadata=snapshot.metadata, sha256=_read_target_digest(snapshot)
            )
        else:
            _confirm_cached_target(snapshot)
        _verify_snapshot(snapshot)
        self._observed.targets[relative] = entry
        return (
            b"SwiftPM symlink target",
            relative.encode(),
            snapshot.metadata.link_text.encode(),
            snapshot.metadata.resolved_path.encode(),
            str(snapshot.target_stat.st_mode & 0o777).encode(),
            bytes.fromhex(entry.sha256),
        )

    def save(self) -> None:
        """Publish an updated cache only after the complete input scan."""
        path = self._path
        if path is None or self._observed == self._previous:
            return
        if path.resolve() != path:
            raise ValueError("Unsupported SwiftPM symlink cache path")
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=".swiftpm-symlinks-", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                _ = stream.write(self._observed.model_dump_json())
            _ = Path(temporary).replace(path)
        finally:
            Path(temporary).unlink(missing_ok=True)
