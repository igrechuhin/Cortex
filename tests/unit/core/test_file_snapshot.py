"""Unit tests for file snapshot and session cache helpers."""

from __future__ import annotations

from pathlib import Path

from cortex.core.file_snapshot import FileSnapshot, FileStateCache


class TestFileSnapshot:
    def test_from_path_existing(self, tmp_path: Path) -> None:
        target = tmp_path / "existing.txt"
        _ = target.write_text("hello", encoding="utf-8")

        snapshot = FileSnapshot.from_path(target)

        assert snapshot.path == target
        assert snapshot.content == "hello"
        assert snapshot.existed is True
        assert snapshot.encoding == "utf-8"
        assert snapshot.snapshot_at

    def test_from_path_nonexistent(self, tmp_path: Path) -> None:
        target = tmp_path / "missing.txt"

        snapshot = FileSnapshot.from_path(target)

        assert snapshot.path == target
        assert snapshot.content == ""
        assert snapshot.existed is False

    def test_restore_existing(self, tmp_path: Path) -> None:
        target = tmp_path / "state.txt"
        _ = target.write_text("before", encoding="utf-8")
        snapshot = FileSnapshot.from_path(target)
        _ = target.write_text("after", encoding="utf-8")

        snapshot.restore()

        assert target.read_text(encoding="utf-8") == "before"

    def test_restore_creates_deleted_file(self, tmp_path: Path) -> None:
        target = tmp_path / "state.txt"
        _ = target.write_text("before", encoding="utf-8")
        snapshot = FileSnapshot.from_path(target)
        target.unlink()

        snapshot.restore()

        assert target.read_text(encoding="utf-8") == "before"

    def test_restore_deletes_new_file(self, tmp_path: Path) -> None:
        target = tmp_path / "new-file.txt"
        snapshot = FileSnapshot.from_path(target)
        _ = target.write_text("created-later", encoding="utf-8")

        snapshot.restore()

        assert not target.exists()


class TestFileStateCache:
    def test_snapshot_creates_files(self, tmp_path: Path) -> None:
        first = tmp_path / "a.txt"
        second = tmp_path / "nested" / "b.txt"
        second.parent.mkdir(parents=True, exist_ok=True)
        _ = first.write_text("one", encoding="utf-8")
        _ = second.write_text("two", encoding="utf-8")
        cache = FileStateCache(tmp_path / "session")

        snapshot_id = cache.snapshot([first, second])
        snapshot_dir = tmp_path / "session" / "snapshots" / snapshot_id

        assert snapshot_dir.exists()
        assert len(list(snapshot_dir.glob("*.json"))) == 2

    def test_restore_returns_paths(self, tmp_path: Path) -> None:
        target = tmp_path / "value.txt"
        _ = target.write_text("before", encoding="utf-8")
        cache = FileStateCache(tmp_path / "session")
        snapshot_id = cache.snapshot([target])
        _ = target.write_text("after", encoding="utf-8")

        restored = cache.restore(snapshot_id)

        assert restored == [target]
        assert target.read_text(encoding="utf-8") == "before"

    def test_list_snapshots_chronological(self, tmp_path: Path) -> None:
        target = tmp_path / "value.txt"
        _ = target.write_text("v", encoding="utf-8")
        cache = FileStateCache(tmp_path / "session")

        first = cache.snapshot([target])
        second = cache.snapshot([target])

        assert cache.list_snapshots() == [first, second]

    def test_drop_removes_snapshot(self, tmp_path: Path) -> None:
        target = tmp_path / "value.txt"
        _ = target.write_text("v", encoding="utf-8")
        cache = FileStateCache(tmp_path / "session")
        snapshot_id = cache.snapshot([target])

        cache.drop(snapshot_id)

        assert snapshot_id not in cache.list_snapshots()

    def test_drop_all_clears_cache(self, tmp_path: Path) -> None:
        target = tmp_path / "value.txt"
        _ = target.write_text("v", encoding="utf-8")
        cache = FileStateCache(tmp_path / "session")
        _ = cache.snapshot([target])
        _ = cache.snapshot([target])

        cache.drop_all()

        assert cache.list_snapshots() == []
