"""Filesystem boundaries and provenance for public WAL historical reads."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from cortex.memory.wal import (
    MemoryWAL,
    WalContentFields,
    WALEntry,
    WalOperation,
    WalStatus,
    wal_build_entry,
)
from cortex.memory.wal_content import CODEC_PRUNED, wal_as_of, wal_encode_reverse_delta

HISTORY_FILE = ".cortex/memory-bank/analyses/report.md"
INVALID_HISTORY_FILES = (
    "pyproject.toml",
    "src/private.py",
    "docs/private.md",
    "report.md",
    "",
    ".cortex/memory-bank/file.json",
    ".cortex/memory-bank/",
    ".cortex/memory-bank/../private.md",
    ".cortex/memory-bank/./file.md",
    ".cortex/memory-bank//file.md",
    ".cortex/memory-bank/nested\\file.md",
    ".cortex/memory-bank/invalid?.md",
    ".cortex/memory-bank/ leading.md",
    ".cortex/memory-bank/trailing.md ",
    ".cortex/memory-bank/CON/file.md",
    ".cortex/memory-bank/bad\x00.md",
    ".cortex/memory-bank/bad\n.md",
    "C:\\private.md",
)


@pytest.fixture
def history_entry() -> WALEntry:
    """One real compressed delta, identified exactly like a recorded nested write."""
    payload, codec = wal_encode_reverse_delta(True, "prior")
    return wal_build_entry(
        operation=WalOperation.WRITE,
        relative_file=HISTORY_FILE,
        agent_hint="synthetic-test",
        before_exists=True,
        before_text="prior",
        after_text="current",
        status=WalStatus.OK,
        error=None,
        content_fields=WalContentFields(
            reverse_delta=payload, delta_codec=codec, step_number=4
        ),
    )


@pytest.mark.parametrize("file", INVALID_HISTORY_FILES)
def test_history_rejects_invalid_requests_before_wal_or_content_reads(
    tmp_path: Path, file: str
) -> None:
    # Arrange
    root = tmp_path / "project"
    # Act / Assert
    with (
        patch.object(
            MemoryWAL, "read", side_effect=AssertionError("unexpected history read")
        ),
        patch.object(
            Path, "read_text", side_effect=AssertionError("unexpected content read")
        ),
        pytest.raises(ValueError),
    ):
        _ = wal_as_of(root, file, 0)
    assert not root.exists()


def test_history_rejects_absolute_synthetic_external_file(tmp_path: Path) -> None:
    # Arrange
    sentinel = tmp_path / "external.md"
    _ = sentinel.write_text("private-sentinel", encoding="utf-8")
    # Act / Assert
    with (
        patch.object(
            MemoryWAL, "read", side_effect=AssertionError("unexpected history read")
        ),
        patch.object(
            Path, "read_text", side_effect=AssertionError("unexpected content read")
        ),
        pytest.raises(ValueError),
    ):
        _ = wal_as_of(tmp_path / "project", str(sentinel), 0)
    assert sentinel.read_text(encoding="utf-8") == "private-sentinel"


@pytest.mark.parametrize(
    "component", [".cortex", "memory-bank", "analyses", "report.md"]
)
@pytest.mark.parametrize("broken", [False, True])
def test_history_rejects_symlinked_file_and_ancestors_before_reads(
    tmp_path: Path, component: str, broken: bool
) -> None:
    # Arrange
    root = tmp_path / "project"
    target = root / HISTORY_FILE
    link = next(path for path in (target, *target.parents) if path.name == component)
    link.parent.mkdir(parents=True)
    external = tmp_path / "external"
    sentinel = external if link == target else external / target.relative_to(link)
    if not broken:
        sentinel.parent.mkdir(parents=True, exist_ok=True)
        _ = sentinel.write_text("private-sentinel", encoding="utf-8")
    link.symlink_to(external, target_is_directory=link != target)
    # Act / Assert
    with (
        patch.object(
            MemoryWAL, "read", side_effect=AssertionError("unexpected history read")
        ),
        patch.object(
            Path, "read_text", side_effect=AssertionError("unexpected content read")
        ),
        pytest.raises(ValueError, match="symlinks"),
    ):
        _ = wal_as_of(root, HISTORY_FILE, 0)
    assert (
        not sentinel.exists()
        if broken
        else sentinel.read_text(encoding="utf-8") == "private-sentinel"
    )


@pytest.mark.parametrize("component", ["wal", "write_log.jsonl"])
def test_history_rejects_symlinked_wal_before_reads(
    tmp_path: Path, component: str
) -> None:
    # Arrange
    root = tmp_path / "project"
    log = root / ".cortex" / "wal" / "write_log.jsonl"
    link = log if component == "write_log.jsonl" else log.parent
    link.parent.mkdir(parents=True)
    external = tmp_path / "external"
    external.mkdir()
    _ = (external / "sentinel.md").write_text("private-sentinel", encoding="utf-8")
    link.symlink_to(external, target_is_directory=True)
    # Act / Assert
    with (
        patch.object(
            MemoryWAL, "read", side_effect=AssertionError("unexpected history read")
        ),
        pytest.raises(ValueError, match="symlinks"),
    ):
        _ = wal_as_of(root, HISTORY_FILE, 0)
    assert (external / "sentinel.md").read_text(encoding="utf-8") == "private-sentinel"


@pytest.mark.parametrize("file", [HISTORY_FILE, ".cortex/wal/write_log.jsonl"])
def test_history_rejects_directory_content_and_log_targets(
    tmp_path: Path, file: str
) -> None:
    # Arrange
    (tmp_path / file).mkdir(parents=True)
    # Act / Assert
    with (
        patch.object(
            MemoryWAL, "read", side_effect=AssertionError("unexpected history read")
        ),
        pytest.raises(ValueError, match="regular file"),
    ):
        _ = wal_as_of(tmp_path, HISTORY_FILE, 0)


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="Named pipes require POSIX")
def test_history_rejects_nonregular_wal_without_opening_it(tmp_path: Path) -> None:
    # Arrange
    wal_dir = tmp_path / ".cortex" / "wal"
    wal_dir.mkdir(parents=True)
    os.mkfifo(wal_dir / "write_log.jsonl")
    # Act / Assert
    with (
        patch.object(
            MemoryWAL, "read", side_effect=AssertionError("unexpected history read")
        ),
        pytest.raises(ValueError, match="regular file"),
    ):
        _ = wal_as_of(tmp_path, HISTORY_FILE, 0)


@pytest.mark.parametrize("file", [".cortex/memory-bank/missing.md", HISTORY_FILE])
def test_history_valid_missing_file_retains_absence_without_mutation(
    tmp_path: Path, file: str
) -> None:
    # Arrange
    root = tmp_path / "project"
    # Act
    result = wal_as_of(root, file, 3)
    # Assert
    assert result.file == file
    assert result.step_number == 3
    assert not result.exists
    assert result.content is None
    assert result.source == "current"
    assert not result.verified
    assert not root.exists()


def test_history_nested_file_keeps_canonical_identity_and_provenance(
    tmp_path: Path, history_entry: WALEntry
) -> None:
    # Arrange
    target = tmp_path / HISTORY_FILE
    target.parent.mkdir(parents=True)
    _ = target.write_text("current", encoding="utf-8")
    wal = MemoryWAL(tmp_path / ".cortex" / "wal", project_root=tmp_path)
    wal.log(history_entry)
    # Act
    before = wal_as_of(tmp_path, HISTORY_FILE, 1)
    after = wal_as_of(tmp_path, HISTORY_FILE, 8)
    # Assert
    assert before.file == after.file == HISTORY_FILE
    assert before.content == "prior"
    assert before.source == "reverse_delta"
    assert before.verified
    assert after.content == "current"
    assert after.source == "current"
    assert after.verified


def test_history_valid_missing_file_can_still_reconstruct_prior_content(
    tmp_path: Path, history_entry: WALEntry
) -> None:
    # Arrange
    MemoryWAL(tmp_path / ".cortex" / "wal", project_root=tmp_path).log(history_entry)
    # Act
    result = wal_as_of(tmp_path, HISTORY_FILE, 1)
    # Assert
    assert result.content == "prior"
    assert result.exists
    assert result.source == "reverse_delta"
    assert result.verified


@pytest.mark.parametrize("pruned", [False, True])
def test_history_scope_preserves_corrupt_and_pruned_delta_errors(
    tmp_path: Path, history_entry: WALEntry, pruned: bool
) -> None:
    # Arrange
    fields = (
        {"delta_codec": CODEC_PRUNED, "reverse_delta": None}
        if pruned
        else {"reverse_delta": "invalid"}
    )
    entry = history_entry.model_copy(update=fields)
    MemoryWAL(tmp_path / ".cortex" / "wal", project_root=tmp_path).log(entry)
    # Act / Assert
    with pytest.raises(
        ValueError, match="pruned" if pruned else "Corrupted WAL reverse delta"
    ):
        _ = wal_as_of(tmp_path, HISTORY_FILE, 1)


def test_history_scope_preserves_corrupt_log_error(tmp_path: Path) -> None:
    # Arrange
    wal_dir = tmp_path / ".cortex" / "wal"
    wal_dir.mkdir(parents=True)
    _ = (wal_dir / "write_log.jsonl").write_text("not valid JSON", encoding="utf-8")
    # Act / Assert
    with pytest.raises(ValueError, match="Invalid JSON"):
        _ = wal_as_of(tmp_path, HISTORY_FILE, 1)


def test_history_rechecks_content_path_after_wal_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    target = tmp_path / HISTORY_FILE
    target.parent.mkdir(parents=True)
    external = tmp_path / "external.md"
    _ = external.write_text("private-sentinel", encoding="utf-8")

    def swap_path(_wal: MemoryWAL, _since: str | None = None) -> list[WALEntry]:
        target.symlink_to(external)
        return []

    monkeypatch.setattr(MemoryWAL, "read", swap_path)
    # Act / Assert
    with (
        patch.object(
            Path, "read_text", side_effect=AssertionError("unexpected content read")
        ),
        pytest.raises(ValueError, match="symlinks"),
    ):
        _ = wal_as_of(tmp_path, HISTORY_FILE, 1)
    assert external.read_text(encoding="utf-8") == "private-sentinel"
