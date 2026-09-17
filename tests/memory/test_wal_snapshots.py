"""Regression proof for WAL snapshot boundaries and replacement recovery."""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

from cortex.memory.wal import MemoryWAL

INVALID_LABELS = (
    "",
    " ",
    "\t",
    ".",
    "..",
    "../outside",
    "nested/label",
    "./label",
    "nested\\label",
    "..\\outside",
    "/outside",
    "C:\\outside",
    "C:outside",
    "bad\x00label",
    "bad\x7flabel",
    "a" * 256,
)


def _snapshot_wal(tmp_path: Path) -> tuple[MemoryWAL, Path, Path]:
    memory = tmp_path / "project" / ".cortex" / "memory-bank"
    memory.mkdir(parents=True)
    _ = (memory / "a.md").write_text("original", encoding="utf-8")
    wal_dir = memory.parent / "wal"
    return MemoryWAL(wal_dir, project_root=tmp_path / "project"), memory, wal_dir


@pytest.mark.parametrize("label", INVALID_LABELS)
@pytest.mark.parametrize("restore", [False, True])
def test_invalid_snapshot_labels_leave_store_and_sentinel_unchanged(
    tmp_path: Path, label: str, restore: bool
) -> None:
    # Arrange
    wal = MemoryWAL(tmp_path / "wal", project_root=tmp_path / "project")
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel.md"
    if label == "/outside":
        label = str(outside)
    _ = sentinel.write_text("unrelated", encoding="utf-8")
    operation = wal.restore if restore else wal.snapshot
    # Act / Assert
    with pytest.raises(ValueError, match="single directory name"):
        _ = operation(label)
    assert not (tmp_path / "wal").exists()
    assert not (tmp_path / "project").exists()
    assert sentinel.read_text(encoding="utf-8") == "unrelated"


@pytest.mark.parametrize("label", ["release-1.2", " pre compact ", "备份"])
def test_valid_snapshot_label_identity_and_replacement(
    tmp_path: Path, label: str
) -> None:
    # Arrange
    wal, memory, wal_dir = _snapshot_wal(tmp_path)
    first = wal.snapshot(label)
    _ = (memory / "a.md").write_text("replacement", encoding="utf-8")
    # Act
    second = wal.snapshot(label)
    _ = (memory / "b.md").write_text("keep", encoding="utf-8")
    restored = wal.restore(label)
    # Assert
    assert first == second == wal_dir / "snapshots" / label
    assert restored == 1
    assert (second / "a.md").read_text(encoding="utf-8") == "replacement"
    assert (memory / "b.md").read_text(encoding="utf-8") == "keep"
    assert list((wal_dir / "snapshot-transactions").iterdir()) == []


@pytest.mark.parametrize("restore", [False, True])
@pytest.mark.parametrize("component", [".cortex", "wal", "snapshots", "safe"])
def test_snapshot_directory_symlinks_never_touch_external_sentinel(
    tmp_path: Path, restore: bool, component: str
) -> None:
    # Arrange
    root = tmp_path / "project"
    target = root / ".cortex" / "wal" / "snapshots" / "safe"
    link = next(path for path in (target, *target.parents) if path.name == component)
    link.parent.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel.md"
    _ = sentinel.write_text("unrelated", encoding="utf-8")
    link.symlink_to(outside, target_is_directory=True)
    wal = MemoryWAL(root / ".cortex" / "wal", project_root=root)
    operation = wal.restore if restore else wal.snapshot
    # Act / Assert
    with pytest.raises(ValueError, match="symlinks"):
        _ = operation("safe")
    assert sentinel.read_text(encoding="utf-8") == "unrelated"
    assert sorted(path.name for path in outside.iterdir()) == ["sentinel.md"]


@pytest.mark.parametrize("restore", [False, True])
def test_custom_wal_parent_symlink_is_rejected(tmp_path: Path, restore: bool) -> None:
    # Arrange
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / "linked").symlink_to(outside, target_is_directory=True)
    wal = MemoryWAL(tmp_path / "linked" / "wal", project_root=tmp_path / "project")
    operation = wal.restore if restore else wal.snapshot
    # Act / Assert
    with pytest.raises(ValueError, match="symlinks"):
        _ = operation("safe")
    assert list(outside.iterdir()) == []


@pytest.mark.parametrize("restore", [False, True])
def test_memory_bank_directory_symlink_is_rejected(
    tmp_path: Path, restore: bool
) -> None:
    # Arrange
    wal, memory, _ = _snapshot_wal(tmp_path)
    _ = wal.snapshot("safe")
    (memory / "a.md").unlink()
    memory.rmdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    _ = (outside / "a.md").write_text("external", encoding="utf-8")
    memory.symlink_to(outside, target_is_directory=True)
    operation = wal.restore if restore else wal.snapshot
    # Act / Assert
    with pytest.raises(ValueError, match="symlinks"):
        _ = operation("safe")
    assert (outside / "a.md").read_text(encoding="utf-8") == "external"


@pytest.mark.parametrize("restore", [False, True])
@pytest.mark.parametrize("broken", [False, True])
def test_snapshot_sources_reject_symlinks_before_copying(
    tmp_path: Path, restore: bool, broken: bool
) -> None:
    # Arrange
    wal, memory, _ = _snapshot_wal(tmp_path)
    snapshot = wal.snapshot("safe")
    outside = tmp_path / "external.md"
    if not broken:
        _ = outside.write_text("external", encoding="utf-8")
    source_dir = snapshot if restore else memory
    (source_dir / "z.md").symlink_to(outside)
    _ = (memory / "a.md").write_text("current", encoding="utf-8")
    operation = wal.restore if restore else wal.snapshot
    # Act / Assert
    with pytest.raises(ValueError, match="symlinks"):
        _ = operation("safe")
    assert (memory / "a.md").read_text(encoding="utf-8") == "current"
    assert (snapshot / "a.md").read_text(encoding="utf-8") == "original"
    assert (
        not outside.exists()
        if broken
        else outside.read_text(encoding="utf-8") == "external"
    )


@pytest.mark.parametrize("broken", [False, True])
def test_restore_destination_symlink_is_rejected_before_any_copy(
    tmp_path: Path, broken: bool
) -> None:
    # Arrange
    wal, memory, _ = _snapshot_wal(tmp_path)
    _ = (memory / "z.md").write_text("snapshot", encoding="utf-8")
    _ = wal.snapshot("safe")
    _ = (memory / "a.md").write_text("current", encoding="utf-8")
    (memory / "z.md").unlink()
    outside = tmp_path / "external.md"
    if not broken:
        _ = outside.write_text("external", encoding="utf-8")
    (memory / "z.md").symlink_to(outside)
    # Act / Assert
    with pytest.raises(ValueError, match="symlinks"):
        _ = wal.restore("safe")
    assert (memory / "a.md").read_text(encoding="utf-8") == "current"
    assert (
        not outside.exists()
        if broken
        else outside.read_text(encoding="utf-8") == "external"
    )


@pytest.mark.parametrize("restore", [False, True])
def test_unsupported_snapshot_contents_are_preserved(
    tmp_path: Path, restore: bool
) -> None:
    # Arrange
    wal, _, _ = _snapshot_wal(tmp_path)
    snapshot = wal.snapshot("safe")
    nested = snapshot / "nested"
    nested.mkdir()
    _ = (nested / "sentinel.md").write_text("unrelated", encoding="utf-8")
    operation = wal.restore if restore else wal.snapshot
    # Act / Assert
    with pytest.raises(ValueError, match="Unsupported snapshot entry"):
        _ = operation("safe")
    assert (nested / "sentinel.md").read_text(encoding="utf-8") == "unrelated"


def test_snapshot_copy_failure_preserves_prior_snapshot(tmp_path: Path) -> None:
    # Arrange
    wal, memory, wal_dir = _snapshot_wal(tmp_path)
    snapshot = wal.snapshot("safe")
    _ = (memory / "a.md").write_text("new", encoding="utf-8")
    # Act
    with patch(
        "cortex.memory.wal_snapshots.shutil.copy2", side_effect=OSError("copy failed")
    ):
        with pytest.raises(OSError, match="copy failed"):
            _ = wal.snapshot("safe")
    # Assert
    assert (snapshot / "a.md").read_text(encoding="utf-8") == "original"
    assert list((wal_dir / "snapshot-transactions").iterdir()) == []


def test_snapshot_install_failure_restores_prior_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    wal, memory, wal_dir = _snapshot_wal(tmp_path)
    snapshot = wal.snapshot("safe")
    _ = (memory / "a.md").write_text("new", encoding="utf-8")
    rename = Path.rename

    def fail_install(source: Path, target: str | Path) -> Path:
        if source.name == "next":
            raise OSError("install failed")
        return rename(source, target)

    monkeypatch.setattr(Path, "rename", fail_install)
    # Act / Assert
    with pytest.raises(OSError, match="install failed"):
        _ = wal.snapshot("safe")
    assert (snapshot / "a.md").read_text(encoding="utf-8") == "original"
    assert list((wal_dir / "snapshot-transactions").iterdir()) == []


def test_snapshot_failed_rollback_retains_bounded_recovery_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    wal, memory, wal_dir = _snapshot_wal(tmp_path)
    _ = wal.snapshot("safe")
    _ = (memory / "a.md").write_text("new", encoding="utf-8")
    rename = Path.rename

    def fail_install_and_rollback(source: Path, target: str | Path) -> Path:
        if source.name in {"next", "previous"}:
            raise OSError("rename failed")
        return rename(source, target)

    monkeypatch.setattr(Path, "rename", fail_install_and_rollback)
    # Act / Assert
    with pytest.raises(OSError, match="Snapshot recovery required"):
        _ = wal.snapshot("safe")
    with pytest.raises(FileExistsError):
        _ = wal.snapshot("safe")
    transactions = list((wal_dir / "snapshot-transactions").iterdir())
    assert len(transactions) == 1
    assert (transactions[0] / "previous" / "a.md").read_text(
        encoding="utf-8"
    ) == "original"


def test_restore_replaces_hard_link_without_changing_external_file(
    tmp_path: Path,
) -> None:
    # Arrange
    wal, memory, _ = _snapshot_wal(tmp_path)
    _ = wal.snapshot("safe")
    outside = tmp_path / "external.md"
    _ = outside.write_text("external", encoding="utf-8")
    (memory / "a.md").unlink()
    (memory / "a.md").hardlink_to(outside)
    # Act
    restored = wal.restore("safe")
    # Assert
    assert restored == 1
    assert (memory / "a.md").read_text(encoding="utf-8") == "original"
    assert outside.read_text(encoding="utf-8") == "external"


def test_restore_copy_failure_preserves_destination(tmp_path: Path) -> None:
    # Arrange
    wal, memory, _ = _snapshot_wal(tmp_path)
    _ = wal.snapshot("safe")
    _ = (memory / "a.md").write_text("current", encoding="utf-8")
    # Act
    with patch(
        "cortex.memory.wal_snapshots.shutil.copy2", side_effect=OSError("copy failed")
    ):
        with pytest.raises(OSError, match="copy failed"):
            _ = wal.restore("safe")
    # Assert
    assert (memory / "a.md").read_text(encoding="utf-8") == "current"
    assert sorted(path.name for path in memory.iterdir()) == ["a.md"]


def test_empty_snapshot_and_missing_restore_do_not_create_memory_bank(
    tmp_path: Path,
) -> None:
    # Arrange
    wal = MemoryWAL(tmp_path / "wal")
    # Act / Assert
    with pytest.raises(FileNotFoundError):
        _ = wal.restore("missing")
    assert not (tmp_path / "wal").exists()
    snapshot = wal.snapshot("empty")
    assert list(snapshot.iterdir()) == []
    assert not (tmp_path / "memory-bank").exists()
    assert wal.restore("empty") == 0


def test_snapshot_supports_explicit_store_outside_project(tmp_path: Path) -> None:
    # Arrange
    _, memory, _ = _snapshot_wal(tmp_path)
    store = tmp_path / "custom-wal"
    wal = MemoryWAL(store, project_root=tmp_path / "project")
    # Act
    snapshot = wal.snapshot("safe")
    _ = (memory / "a.md").write_text("new", encoding="utf-8")
    restored = wal.restore("safe")
    # Assert
    assert snapshot == store / "snapshots" / "safe"
    assert restored == 1
    assert (memory / "a.md").read_text(encoding="utf-8") == "original"


@pytest.mark.parametrize("restore", [False, True])
def test_snapshot_label_file_is_rejected_without_replacing_it(
    tmp_path: Path, restore: bool
) -> None:
    # Arrange
    wal, _, wal_dir = _snapshot_wal(tmp_path)
    (wal_dir / "snapshots").mkdir(parents=True)
    destination = wal_dir / "snapshots" / "safe"
    _ = destination.write_text("unrelated", encoding="utf-8")
    operation = wal.restore if restore else wal.snapshot
    # Act / Assert
    with pytest.raises(ValueError, match="Snapshot directory required"):
        _ = operation("safe")
    assert destination.read_text(encoding="utf-8") == "unrelated"


def test_restore_rechecks_destination_after_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    wal, memory, _ = _snapshot_wal(tmp_path)
    _ = wal.snapshot("safe")
    outside = tmp_path / "external.md"
    _ = outside.write_text("external", encoding="utf-8")
    copy_file = shutil.copy2

    def copy_and_swap(source: Path, destination: Path, *, follow_symlinks: bool) -> str:
        result = copy_file(source, destination, follow_symlinks=follow_symlinks)
        (memory / "a.md").unlink()
        (memory / "a.md").symlink_to(outside)
        return str(result)

    monkeypatch.setattr(shutil, "copy2", copy_and_swap)
    # Act / Assert
    with pytest.raises(ValueError, match="symlinks"):
        _ = wal.restore("safe")
    assert outside.read_text(encoding="utf-8") == "external"
