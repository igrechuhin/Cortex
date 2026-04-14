from pathlib import Path

from cortex.memory.memory_types import MemoryType
from cortex.memory.typed_reader import TypedMemoryReader


def test_typed_reader_filters_by_type(tmp_path: Path) -> None:
    path = tmp_path / "activeContext.md"
    _ = path.write_text(
        """<!-- memory_type: decision -->
we decided to migrate

<!-- memory_type: milestone -->
completed rollout

untyped fallback status
""",
        encoding="utf-8",
    )
    reader = TypedMemoryReader()
    decision_entries = reader.read_by_type(path, MemoryType.DECISION)
    assert len(decision_entries) == 1
    assert "decided" in decision_entries[0].content


def test_typed_reader_missing_file_returns_empty(tmp_path: Path) -> None:
    entries = TypedMemoryReader().read_all(tmp_path / "missing.md")
    assert entries == []
