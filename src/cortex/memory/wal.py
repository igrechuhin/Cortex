"""Write-ahead log for memory-bank mutations (audit, anomalies, rollback)."""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from tempfile import NamedTemporaryFile

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.pydantic_extra import EXTRA_FORBID

logger = logging.getLogger(__name__)


class WalOperation(StrEnum):
    """Recorded mutation kinds (aligned with MCP update_memory_bank naming)."""

    WRITE = "write"
    APPEND = "append"
    ROADMAP_ADD = "roadmap_add"
    ACTIVE_ADD = "active_add"
    PROGRESS_ADD = "progress_add"
    DELETE = "delete"


class WalStatus(StrEnum):
    """Whether the underlying mutation succeeded."""

    OK = "ok"
    ERROR = "error"


class WALEntry(BaseModel):
    """Single WAL record (JSONL line).

    ``after_byte_len`` supports shrink-ratio anomaly checks (``byte_delta`` alone
    is insufficient to recover ``len(before_bytes)``).
    """

    model_config = ConfigDict(extra=EXTRA_FORBID, frozen=True)

    id: str = Field(min_length=12, max_length=12)
    timestamp: str
    operation: WalOperation
    file: str
    agent_hint: str
    content_hash_before: str
    content_hash_after: str
    byte_delta: int
    after_byte_len: int = Field(
        default=0,
        ge=0,
        description="UTF-8 byte length of content after mutation (0 if absent in legacy lines)",
    )
    status: WalStatus
    error: str | None = None


def wal_short_hash(text: str) -> str:
    """Return first 16 hex chars of sha256 UTF-8 digest."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def wal_build_entry(
    *,
    operation: WalOperation,
    relative_file: str,
    agent_hint: str,
    before_exists: bool,
    before_text: str,
    after_text: str,
    status: WalStatus,
    error: str | None,
) -> WALEntry:
    """Construct a WAL entry with hashes, byte delta, and fresh id/timestamp."""
    before_hash = "none" if not before_exists else wal_short_hash(before_text)
    after_hash = wal_short_hash(after_text)
    before_b = b"" if not before_exists else before_text.encode("utf-8")
    after_b = after_text.encode("utf-8")
    byte_delta = len(after_b) - len(before_b)
    return WALEntry(
        id=uuid.uuid4().hex[:12],
        timestamp=datetime.now(UTC).isoformat(),
        operation=operation,
        file=relative_file,
        agent_hint=agent_hint,
        content_hash_before=before_hash,
        content_hash_after=after_hash,
        byte_delta=byte_delta,
        after_byte_len=len(after_b),
        status=status,
        error=error,
    )


class MemoryWAL:
    """Append-only JSONL WAL under ``wal_dir`` (typically ``.cortex/wal``)."""

    def __init__(self, wal_dir: Path, project_root: Path | None = None) -> None:
        self._wal_dir = wal_dir
        self._project_root = project_root
        self._log_path = wal_dir / "write_log.jsonl"
        wal_dir.mkdir(parents=True, exist_ok=True)

    def _memory_bank_dir(self) -> Path:
        if self._project_root is not None:
            return self._project_root / ".cortex" / "memory-bank"
        return self._wal_dir.parent / "memory-bank"

    def log(self, entry: WALEntry) -> None:
        """Atomically append one JSON line (read-merge-write + replace)."""
        line = entry.model_dump_json() + "\n"
        new_bytes = self._existing_log_bytes() + line.encode("utf-8")
        self._atomic_write_bytes(self._log_path, new_bytes)

    def _existing_log_bytes(self) -> bytes:
        if not self._log_path.is_file():
            return b""
        return self._log_path.read_bytes()

    def _atomic_write_bytes(self, dest: Path, payload: bytes) -> None:
        self._wal_dir.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(dir=self._wal_dir, prefix=".wal_", delete=False) as tmp:
            _ = tmp.write(payload)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp_path = Path(tmp.name)
        os.replace(tmp_path, dest)

    def read(self, since: str | None = None) -> list[WALEntry]:
        """Parse WAL lines; optional ISO timestamp lower bound (inclusive)."""
        if not self._log_path.is_file():
            return []
        lines = self._log_path.read_text(encoding="utf-8").splitlines()
        entries = [WALEntry.model_validate_json(line) for line in lines if line.strip()]
        if since is None:
            return entries
        return [e for e in entries if e.timestamp >= since]

    def detect_anomalies(self) -> list[str]:
        """Heuristic warnings from the last 50 entries."""
        entries = self.read()
        tail = entries[-50:]
        return _wal_anomaly_messages(tail)

    def snapshot(self, label: str) -> Path:
        """Copy memory-bank ``*.md`` into ``wal_dir/snapshots/{label}/``."""
        mem_bank = self._memory_bank_dir()
        dest = self._wal_dir / "snapshots" / label
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True, exist_ok=True)
        if mem_bank.is_dir():
            for src in sorted(mem_bank.glob("*.md")):
                if src.is_file():
                    _ = shutil.copy2(src, dest / src.name)
        return dest

    def restore(self, label: str) -> int:
        """Restore snapshot ``label`` into memory-bank; return files copied."""
        snap = self._wal_dir / "snapshots" / label
        if not snap.is_dir():
            raise FileNotFoundError(f"No WAL snapshot at {snap}")
        mem_bank = self._memory_bank_dir()
        mem_bank.mkdir(parents=True, exist_ok=True)
        n = 0
        for src in sorted(snap.glob("*.md")):
            if src.is_file():
                _ = shutil.copy2(src, mem_bank / src.name)
                n += 1
        return n


def _wal_anomaly_messages(entries: list[WALEntry]) -> list[str]:
    warnings: list[str] = []
    for e in entries:
        if e.status == WalStatus.ERROR:
            warnings.append(f"error status for {e.file} at {e.timestamp}")
    warnings.extend(_wal_shrink_warnings(entries))
    warnings.extend(_wal_burst_warnings(entries))
    return warnings


def _wal_shrink_warnings(entries: list[WALEntry]) -> list[str]:
    out: list[str] = []
    for e in entries:
        if e.content_hash_before == "none":
            continue
        after_len = e.after_byte_len
        before_len = after_len - e.byte_delta
        if before_len <= 0 or e.byte_delta >= 0:
            continue
        shrink = -e.byte_delta / float(before_len)
        if shrink > 0.3:
            out.append(
                f"large shrink ({shrink:.0%}) on {e.file} at {e.timestamp} (byte_delta={e.byte_delta})"
            )
    return out


def _wal_burst_warnings(entries: list[WALEntry]) -> list[str]:
    by_file: dict[str, list[str]] = {}
    for e in entries:
        by_file.setdefault(e.file, []).append(e.timestamp)
    out: list[str] = []
    for file_key, stamps in by_file.items():
        ts_sorted = sorted(stamps)
        if _wal_max_writes_in_sliding_window(ts_sorted, 60.0) > 10:
            out.append(f"burst writes (>10 in 60s) on {file_key} near {ts_sorted[-1]}")
    return out


def _wal_max_writes_in_sliding_window(
    sorted_ts: list[str], window_seconds: float
) -> int:
    if not sorted_ts:
        return 0
    best = 1
    left = 0
    for right, stamp in enumerate(sorted_ts):
        while (
            left <= right
            and _wal_seconds_between(sorted_ts[left], stamp) > window_seconds
        ):
            left += 1
        best = max(best, right - left + 1)
    return best


def _wal_seconds_between(a: str, b: str) -> float:
    try:
        ta = datetime.fromisoformat(a.replace("Z", "+00:00"))
        tb = datetime.fromisoformat(b.replace("Z", "+00:00"))
    except ValueError:
        return 0.0
    return abs((tb - ta).total_seconds())
