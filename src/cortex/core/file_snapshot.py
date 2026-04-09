"""Session-scoped file snapshot and rollback helpers."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel


class FileSnapshot(BaseModel):
    """Serializable snapshot of one file's text state."""

    path: Path
    content: str
    encoding: str
    snapshot_at: str
    existed: bool

    @classmethod
    def from_path(cls, path: Path, encoding: str = "utf-8") -> "FileSnapshot":
        if path.exists():
            content = path.read_text(encoding=encoding)
            return cls(
                path=path,
                content=content,
                encoding=encoding,
                snapshot_at=datetime.now(UTC).isoformat(),
                existed=True,
            )
        return cls(
            path=path,
            content="",
            encoding=encoding,
            snapshot_at=datetime.now(UTC).isoformat(),
            existed=False,
        )

    def restore(self) -> None:
        if not self.existed:
            if self.path.exists():
                self.path.unlink()
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        _ = self.path.write_text(self.content, encoding=self.encoding)


class FileStateCache:
    """Stores snapshots under a session directory."""

    def __init__(self, session_dir: Path) -> None:
        self._session_dir = session_dir
        self._snapshots_dir = session_dir / "snapshots"

    @staticmethod
    def _encoded_path(path: Path) -> str:
        return path.as_posix().replace("/", "__")

    @staticmethod
    def _new_snapshot_id() -> str:
        return datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")

    def snapshot(self, paths: list[Path]) -> str:
        snapshot_id = self._new_snapshot_id()
        target_dir = self._snapshots_dir / snapshot_id
        target_dir.mkdir(parents=True, exist_ok=True)
        for path in paths:
            snapshot = FileSnapshot.from_path(path)
            snap_file = target_dir / f"{self._encoded_path(path)}.json"
            _ = snap_file.write_text(
                snapshot.model_dump_json(indent=2), encoding="utf-8"
            )
        return snapshot_id

    def restore(self, snapshot_id: str) -> list[Path]:
        target_dir = self._snapshots_dir / snapshot_id
        if not target_dir.exists():
            return []
        restored: list[Path] = []
        for snap_file in sorted(target_dir.glob("*.json")):
            payload = json.loads(snap_file.read_text(encoding="utf-8"))
            snapshot = FileSnapshot.model_validate(payload)
            snapshot.restore()
            restored.append(snapshot.path)
        return restored

    def list_snapshots(self) -> list[str]:
        if not self._snapshots_dir.exists():
            return []
        return sorted(
            p.name for p in self._snapshots_dir.iterdir() if p.is_dir() and p.name
        )

    def drop(self, snapshot_id: str) -> None:
        target_dir = self._snapshots_dir / snapshot_id
        if target_dir.exists():
            shutil.rmtree(target_dir, ignore_errors=True)

    def drop_all(self) -> None:
        if self._snapshots_dir.exists():
            shutil.rmtree(self._snapshots_dir, ignore_errors=True)
