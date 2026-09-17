"""Validated, bounded filesystem snapshots for the memory-bank WAL."""

from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path, PureWindowsPath
from tempfile import NamedTemporaryFile

from pydantic import BaseModel, ConfigDict

from cortex.core.pydantic_extra import EXTRA_FORBID


def validate_snapshot_label(label: str) -> str:
    """Accept one literal directory name; never normalize caller input."""
    if (
        not label.strip()
        or label in {".", ".."}
        or "/" in label
        or "\\" in label
        or PureWindowsPath(label).drive
        or any(ord(char) < 32 or ord(char) == 127 for char in label)
        or len(label.encode("utf-8")) > 255
    ):
        raise ValueError("Snapshot label must be a non-empty single directory name")
    return label


def _checked_path(path: Path, anchor: Path) -> Path:
    """Reject linked components before resolving beneath an established anchor."""
    current = path
    if not path.is_relative_to(anchor):
        raise ValueError(f"Snapshot path escapes its allowed root: {path}")
    while current != anchor:
        if current.is_symlink():
            raise ValueError(f"Snapshot paths cannot contain symlinks: {current}")
        current = current.parent
    if anchor.is_symlink() or not path.resolve().is_relative_to(anchor):
        raise ValueError(f"Snapshot path escapes its allowed root: {path}")
    return path


class SnapshotPaths(BaseModel):
    """Canonical anchors retained and rechecked before filesystem operations."""

    model_config = ConfigDict(extra=EXTRA_FORBID, frozen=True)

    store_anchor: Path
    memory_anchor: Path
    store: Path
    memory: Path
    snapshot: Path
    transaction: Path

    def check_store(self, path: Path) -> Path:
        return _checked_path(path, self.store_anchor)

    def check_memory(self, path: Path) -> Path:
        return _checked_path(path, self.memory_anchor)


def _snapshot_paths(
    wal_dir: Path, memory_bank: Path, project_root: Path | None, label: str
) -> SnapshotPaths:
    label = validate_snapshot_label(label)
    # AI: Explicit WAL locations remain supported independently of project_root.
    root = (
        project_root.absolute()
        if project_root is not None
        else wal_dir.parent.absolute()
    )
    memory_anchor = root.resolve()
    store_base = Path(os.path.commonpath((root, wal_dir.absolute())))
    if project_root is None and root.is_symlink():
        raise ValueError(f"Snapshot paths cannot contain symlinks: {root}")
    store_anchor = store_base.resolve()
    store = store_anchor / wal_dir.absolute().relative_to(store_base) / "snapshots"
    memory = memory_anchor / memory_bank.absolute().relative_to(root)
    digest = hashlib.sha256(label.encode("utf-8")).hexdigest()
    paths = SnapshotPaths(
        store_anchor=store_anchor,
        memory_anchor=memory_anchor,
        store=store,
        memory=memory,
        snapshot=store / label,
        transaction=store.parent / "snapshot-transactions" / digest,
    )
    _ = paths.check_store(paths.snapshot)
    _ = paths.check_store(paths.transaction)
    _ = paths.check_memory(paths.memory)
    return paths


def _snapshot_files(directory: Path, anchor: Path, *, strict: bool) -> list[Path]:
    """Validate the complete candidate set before a copy or removal begins."""
    _ = _checked_path(directory, anchor)
    if not directory.exists():
        return []
    if not directory.is_dir():
        raise ValueError(f"Snapshot directory required: {directory}")
    entries = sorted(directory.iterdir()) if strict else sorted(directory.glob("*.md"))
    for entry in entries:
        _ = _checked_path(entry, anchor)
        if not entry.is_file() or (strict and entry.suffix != ".md"):
            raise ValueError(f"Unsupported snapshot entry: {entry}")
    return entries


def _remove_snapshot_tree(directory: Path, paths: SnapshotPaths) -> None:
    """Remove only the validated flat snapshot files, never recursively delete."""
    for entry in _snapshot_files(directory, paths.store_anchor, strict=True):
        paths.check_store(entry).unlink()
    paths.check_store(directory).rmdir()


def _install_snapshot(stage: Path, paths: SnapshotPaths) -> None:
    previous = paths.transaction / "previous"
    _ = _snapshot_files(paths.snapshot, paths.store_anchor, strict=True)
    if paths.check_store(paths.snapshot).exists():
        _ = paths.check_store(previous)
        _ = paths.snapshot.rename(previous)
    try:
        _ = paths.check_store(stage)
        _ = paths.check_store(paths.snapshot)
        _ = stage.rename(paths.snapshot)
    except (OSError, ValueError):
        if paths.check_store(previous).exists():
            _ = paths.check_store(paths.snapshot)
            _ = previous.rename(paths.snapshot)
        raise
    if previous.exists():
        _remove_snapshot_tree(previous, paths)


def _finish_transaction(paths: SnapshotPaths, stage: Path) -> None:
    """Keep a failed rollback discoverable instead of deleting the prior copy."""
    if paths.check_store(paths.transaction / "previous").exists():
        raise OSError(f"Snapshot recovery required at {paths.transaction}")
    if paths.check_store(stage).exists():
        _remove_snapshot_tree(stage, paths)
    paths.check_store(paths.transaction).rmdir()


def snapshot_memory_bank(
    wal_dir: Path, memory_bank: Path, project_root: Path | None, label: str
) -> Path:
    """Stage a valid snapshot before replacing its prior version."""
    paths = _snapshot_paths(wal_dir, memory_bank, project_root, label)
    sources = _snapshot_files(paths.memory, paths.memory_anchor, strict=False)
    _ = _snapshot_files(paths.snapshot, paths.store_anchor, strict=True)
    paths.check_store(paths.store).mkdir(parents=True, exist_ok=True)
    paths.check_store(paths.transaction.parent).mkdir(parents=True, exist_ok=True)
    # AI: One exclusive directory per label bounds failures and excludes writers.
    paths.check_store(paths.transaction).mkdir()
    stage = paths.transaction / "next"
    try:
        paths.check_store(stage).mkdir()
        for source in sources:
            _ = paths.check_memory(source)
            destination = paths.check_store(stage / source.name)
            _ = shutil.copy2(source, destination, follow_symlinks=False)
        _ = _snapshot_files(stage, paths.store_anchor, strict=True)
        _install_snapshot(stage, paths)
    finally:
        _finish_transaction(paths, stage)
    return paths.snapshot


def _restore_file(source: Path, paths: SnapshotPaths) -> None:
    destination = paths.memory / source.name
    _ = paths.check_memory(destination)
    _ = paths.check_store(source)
    # AI: Replacing a temporary file avoids mutating hard-linked destinations.
    with NamedTemporaryFile(dir=paths.check_memory(paths.memory), delete=False) as temp:
        temporary = Path(temp.name)
    try:
        _ = paths.check_memory(temporary)
        _ = paths.check_store(source)
        _ = shutil.copy2(source, temporary, follow_symlinks=False)
        _ = paths.check_store(source)
        _ = paths.check_memory(temporary)
        _ = paths.check_memory(destination)
        os.replace(temporary, destination)
    finally:
        if paths.check_memory(temporary).exists():
            temporary.unlink()


def restore_memory_bank(
    wal_dir: Path, memory_bank: Path, project_root: Path | None, label: str
) -> int:
    """Prevalidate all files, then restore regular files through atomic replaces."""
    paths = _snapshot_paths(wal_dir, memory_bank, project_root, label)
    if not paths.snapshot.exists():
        raise FileNotFoundError(f"No WAL snapshot at {paths.snapshot}")
    sources = _snapshot_files(paths.snapshot, paths.store_anchor, strict=True)
    for source in sources:
        destination = paths.check_memory(paths.memory / source.name)
        if destination.exists() and not destination.is_file():
            raise ValueError(
                f"Restore destination must be a regular file: {destination}"
            )
    paths.check_memory(paths.memory).mkdir(parents=True, exist_ok=True)
    for source in sources:
        _restore_file(source, paths)
    return len(sources)
