"""Unit tests for :mod:`cortex.memory.wal_content` (AS-OF reconstruction)."""

from __future__ import annotations

import secrets
from pathlib import Path

import pytest

from cortex.memory.wal import (
    MemoryWAL,
    WalContentFields,
    WALEntry,
    WalOperation,
    WalStatus,
    wal_build_entry,
)
from cortex.memory.wal_content import (
    CODEC_PRUNED,
    CODEC_ZLIB_B64,
    wal_as_of,
    wal_as_of_from_entries,
    wal_compact_log_bytes,
    wal_content_fields,
    wal_current_step_number,
    wal_decode_reverse_delta,
    wal_encode_reverse_delta,
)

FILE = ".cortex/memory-bank/a.md"


def _noise(size: int) -> str:
    """Incompressible text so encoded deltas keep their size."""
    return secrets.token_hex(size // 2)


def _entry(
    before_exists: bool, before_text: str, after_text: str, step: int
) -> WALEntry:
    payload, codec = wal_encode_reverse_delta(before_exists, before_text)
    return wal_build_entry(
        operation=WalOperation.WRITE,
        relative_file=FILE,
        agent_hint="t",
        before_exists=before_exists,
        before_text=before_text,
        after_text=after_text,
        status=WalStatus.OK,
        error=None,
        content_fields=WalContentFields(
            reverse_delta=payload, delta_codec=codec, step_number=step
        ),
    )


def test_reverse_delta_roundtrip() -> None:
    # Arrange
    entry = _entry(True, "old body", "new body", 3)
    # Act
    decoded = wal_decode_reverse_delta(entry)
    # Assert
    assert decoded == "old body"
    assert entry.delta_codec == CODEC_ZLIB_B64
    assert entry.step_number == 3


def test_oversized_content_degrades_to_pruned() -> None:
    # Arrange
    huge = "".join(chr(0x4E00 + (i % 20000)) for i in range(400_000))
    # Act
    payload, codec = wal_encode_reverse_delta(True, huge)
    # Assert
    assert payload is None
    assert codec == CODEC_PRUNED


def test_as_of_reconstructs_every_recorded_step() -> None:
    # Arrange
    texts = ["", "v1", "v2", "v3"]
    entries = [
        _entry(index > 0, texts[index], texts[index + 1], index + 1)
        for index in range(3)
    ]
    # Act / Assert
    for step, expected in enumerate(texts[:-1]):
        result = wal_as_of_from_entries(
            file=FILE, step_number=step, entries=entries, current_text="v3"
        )
        assert result.content == (expected or None)
        assert result.verified is True
        assert result.source == "reverse_delta"


def test_as_of_after_last_write_returns_current_content() -> None:
    # Arrange
    entries = [_entry(True, "v1", "v2", 1)]
    # Act
    result = wal_as_of_from_entries(
        file=FILE, step_number=9, entries=entries, current_text="v2"
    )
    # Assert
    assert result.content == "v2"
    assert result.source == "current"
    assert result.verified is True


def test_as_of_flags_unverified_when_file_edited_out_of_band() -> None:
    # Arrange
    entries = [_entry(True, "v1", "v2", 1)]
    # Act
    result = wal_as_of_from_entries(
        file=FILE, step_number=9, entries=entries, current_text="edited elsewhere"
    )
    # Assert
    assert result.verified is False


def test_as_of_rejects_corrupted_delta() -> None:
    # Arrange
    payload, _ = wal_encode_reverse_delta(True, "not the recorded content")
    entry = _entry(True, "v1", "v2", 1).model_copy(update={"reverse_delta": payload})
    # Act / Assert
    with pytest.raises(ValueError, match="hash verification"):
        _ = wal_as_of_from_entries(
            file=FILE, step_number=0, entries=[entry], current_text="v2"
        )


def test_as_of_rejects_pruned_history() -> None:
    # Arrange
    entry = _entry(True, "v1", "v2", 1).model_copy(
        update={"reverse_delta": None, "delta_codec": CODEC_PRUNED}
    )
    # Act / Assert
    with pytest.raises(ValueError, match="pruned"):
        _ = wal_as_of_from_entries(
            file=FILE, step_number=0, entries=[entry], current_text="v2"
        )


def test_legacy_entries_without_step_number_are_skipped() -> None:
    # Arrange
    legacy = wal_build_entry(
        operation=WalOperation.WRITE,
        relative_file=FILE,
        agent_hint="t",
        before_exists=True,
        before_text="old",
        after_text="v1",
        status=WalStatus.OK,
        error=None,
    )
    entries = [legacy, _entry(True, "v1", "v2", 5)]
    # Act
    result = wal_as_of_from_entries(
        file=FILE, step_number=1, entries=entries, current_text="v2"
    )
    # Assert
    assert result.content == "v1"


def test_compaction_is_a_no_op_under_budget() -> None:
    # Arrange
    raw = (_entry(True, "v1", "v2", 1).model_dump_json() + "\n").encode("utf-8")
    # Act / Assert
    assert wal_compact_log_bytes(raw) == raw


def test_compaction_prunes_then_drops_oldest(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange - incompressible bodies so each stored delta is genuinely large
    lines = [
        (_entry(True, _noise(4_000), "after", index + 1).model_dump_json() + "\n")
        for index in range(20)
    ]
    raw = "".join(lines).encode("utf-8")
    monkeypatch.setattr("cortex.memory.wal_content._MAX_LOG_BYTES", 12_000)
    # Act
    compacted = wal_compact_log_bytes(raw)
    # Assert
    assert len(compacted) <= 12_000
    assert compacted.endswith(lines[-1].encode("utf-8"))
    assert CODEC_ZLIB_B64.encode("utf-8") not in compacted.split(b"\n")[0]


def test_compaction_then_reconstruction_still_works(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    old_body = _noise(8_000)
    old_entry = _entry(True, old_body, "mid", 1)
    recent = _entry(True, "mid", "new", 2)
    raw = "".join(
        entry.model_dump_json() + "\n" for entry in (old_entry, recent)
    ).encode("utf-8")
    monkeypatch.setattr("cortex.memory.wal_content._MAX_LOG_BYTES", 4_000)
    # Act
    compacted = wal_compact_log_bytes(raw)
    entries = [
        WALEntry.model_validate_json(line)
        for line in compacted.decode("utf-8").splitlines()
    ]
    # Assert - oldest delta is gone, the recent one still reconstructs
    assert entries[0].delta_codec == CODEC_PRUNED
    result = wal_as_of_from_entries(
        file=FILE, step_number=1, entries=entries, current_text="new"
    )
    assert result.content == "mid"


def test_content_fields_skip_content_outside_memory_bank(tmp_path: Path) -> None:
    # Arrange / Act
    fields = wal_content_fields(
        project_root=tmp_path,
        relative_file="docs/other.md",
        agent_hint="t",
        before_exists=True,
        before_text="secret",
    )
    # Assert
    assert fields.reverse_delta is None
    assert fields.delta_codec == "none"


def test_content_fields_capture_memory_bank_content(tmp_path: Path) -> None:
    # Arrange / Act
    fields = wal_content_fields(
        project_root=tmp_path,
        relative_file=FILE,
        agent_hint="t",
        before_exists=True,
        before_text="prior",
    )
    # Assert
    assert fields.delta_codec == CODEC_ZLIB_B64
    assert fields.reverse_delta is not None


def test_current_step_number_is_none_without_store(tmp_path: Path) -> None:
    # Arrange / Act / Assert
    assert wal_current_step_number(tmp_path, "anything") is None


def test_wal_as_of_end_to_end(tmp_path: Path) -> None:
    # Arrange
    mem_bank = tmp_path / ".cortex" / "memory-bank"
    mem_bank.mkdir(parents=True)
    wal = MemoryWAL(tmp_path / ".cortex" / "wal", project_root=tmp_path)
    wal.log(_entry(True, "first", "second", 4))
    _ = (mem_bank / "a.md").write_text("second", encoding="utf-8")
    # Act
    before = wal_as_of(tmp_path, FILE, 1)
    after = wal_as_of(tmp_path, FILE, 8)
    # Assert
    assert before.content == "first"
    assert after.content == "second"
    assert after.source == "current"


def test_current_step_number_reads_the_experience_store(tmp_path: Path) -> None:
    # Arrange
    from cortex.experience.models import (
        ExperienceNode,
        ExperienceSession,
        ExperienceTask,
    )
    from cortex.experience.recorder import experience_db_path
    from cortex.experience.store_core import ExperienceStoreCore

    db_path = experience_db_path(tmp_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    core = ExperienceStoreCore(db_path)
    task = core.create_task(ExperienceTask(spec="pipeline:implement"))
    session = core.create_session(
        ExperienceSession(task_id=task.id, algorithm="implement", owner="agent-7")
    )
    for step in (1, 2, 3):
        _ = core.append_node(
            ExperienceNode(session_id=session.id, step_number=step, label=f"s{step}")
        )
    # Act / Assert
    assert wal_current_step_number(tmp_path, "agent-7") == 3
    assert wal_current_step_number(tmp_path, "someone-else") is None
