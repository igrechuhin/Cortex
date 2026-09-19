"""Content-preserving WAL: reverse deltas, AS-OF reconstruction, compaction.

Extends the audit-only WAL (:mod:`cortex.memory.wal`) so a memory-bank file's
content can be reconstructed as it stood at a given experience-store step
number. Each recorded mutation stores a compressed copy of the *prior* content
(the reverse delta); reconstruction walks forward to the first write that
happened after the requested step and returns what that write overwrote.

Growth is bounded by :func:`wal_compact_log_bytes`, which downgrades the oldest
entries to ``delta_codec="pruned"`` (dropping their payload) and finally drops
whole lines once the log exceeds the byte budget.
"""

from __future__ import annotations

import base64
import logging
import zlib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from cortex.core.input_validation import InputValidator
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.pydantic_extra import EXTRA_FORBID
from cortex.memory.wal import (
    WRITE_LOG_FILE_NAME,
    MemoryWAL,
    WalContentFields,
    WALEntry,
    wal_short_hash,
)

logger = logging.getLogger(__name__)

CODEC_NONE = "none"
CODEC_PRUNED = "pruned"
CODEC_ZLIB_B64 = "zlib-b64"

MEMORY_BANK_PREFIX = (
    f"{CortexResourceType.CORTEX_DIR.value}/{CortexResourceType.MEMORY_BANK.value}/"
)

# AI: per-entry cap keeps one oversized write from bloating a single JSONL line;
# such an entry degrades to "pruned" (same reconstruction semantics as compaction).
_MAX_DELTA_BYTES = 64 * 1024
# AI: whole-log budget from the plan's retention policy. The fast path below
# compares raw length first so the common append never parses the log.
_MAX_LOG_BYTES = 2 * 1024 * 1024

_ABSENT_HASH = "none"

# AI: which rung of `wal_compact_log_bytes`'s two-stage degradation ladder a
# write actually reached. Lives here, with its only user.
CompactionStage = Literal["none", "deltas_pruned", "lines_dropped"]


class WalCompactionResult(BaseModel):
    """Outcome of enforcing the WAL size budget on one write.

    ``stage`` names which rung of the two-stage degradation ladder was
    actually reached, so a caller can observe budget pressure directly
    instead of only reading the accompanying debug/info log line.
    """

    model_config = ConfigDict(extra=EXTRA_FORBID, frozen=True)

    content: bytes
    stage: CompactionStage
    pruned_count: int = Field(ge=0)
    dropped_count: int = Field(ge=0)


class WalAsOfResult(BaseModel):
    """Reconstructed view of one memory-bank file at a given step number."""

    model_config = ConfigDict(extra=EXTRA_FORBID, frozen=True)

    file: str
    step_number: int = Field(ge=0)
    exists: bool
    content: str | None = None
    source: str = Field(description="reverse_delta | current")
    verified: bool = Field(
        description="True when the returned content matched the recorded hash"
    )


def wal_encode_reverse_delta(
    before_exists: bool, before_text: str
) -> tuple[str | None, str]:
    """Encode prior content as ``(payload, codec)`` for AS-OF reconstruction.

    A file that did not exist yet encodes as the empty string; absence is
    recorded separately by ``content_hash_before == "none"``.
    """
    raw = before_text.encode("utf-8") if before_exists else b""
    payload = base64.b64encode(zlib.compress(raw, 6)).decode("ascii")
    if len(payload) > _MAX_DELTA_BYTES:
        return None, CODEC_PRUNED
    return payload, CODEC_ZLIB_B64


def wal_decode_reverse_delta(entry: WALEntry) -> str:
    """Decode an entry's reverse delta, or raise when it is unusable."""
    if entry.delta_codec != CODEC_ZLIB_B64 or entry.reverse_delta is None:
        detail = "legacy entry or pruned by compaction"
        raise ValueError(
            f"AS-OF unavailable for {entry.file}: reverse delta is "
            + f"'{entry.delta_codec}' ({detail})"
        )
    try:
        return zlib.decompress(base64.b64decode(entry.reverse_delta)).decode("utf-8")
    except (ValueError, zlib.error, UnicodeDecodeError) as exc:
        raise ValueError(
            f"Corrupted WAL reverse delta for {entry.file}: {exc}"
        ) from exc


def wal_current_step_number(project_root: Path, agent_hint: str) -> int | None:
    """Highest experience-store step number recorded for ``agent_hint``.

    Best-effort: returns ``None`` when the store is absent or unreadable, so a
    WAL write never fails because experience recording is off.
    """
    try:
        from cortex.experience.recorder import experience_db_path
        from cortex.experience.store_core import ExperienceStoreCore

        db_path = experience_db_path(project_root)
        if not db_path.is_file():
            return None
        core = ExperienceStoreCore(db_path)
        steps = [
            node.step_number
            for session in core.list_sessions()
            if session.owner == agent_hint
            for node in [core.latest_node(session.id)]
            if node is not None
        ]
        return max(steps) if steps else None
    except Exception as exc:  # noqa: BLE001 - advisory linkage only
        logger.debug("WAL step-number lookup skipped: %s", exc)
        return None


def wal_content_fields(
    *,
    project_root: Path,
    relative_file: str,
    agent_hint: str,
    before_exists: bool,
    before_text: str,
) -> WalContentFields:
    """Build the content-preservation fields for one memory-bank mutation.

    Files outside ``.cortex/memory-bank/`` are tagged with the step number only
    (no content is retained) -- versioning them is explicitly out of scope.
    """
    step = wal_current_step_number(project_root, agent_hint)
    if not relative_file.startswith(MEMORY_BANK_PREFIX):
        return WalContentFields(step_number=step)
    payload, codec = wal_encode_reverse_delta(before_exists, before_text)
    return WalContentFields(reverse_delta=payload, delta_codec=codec, step_number=step)


def _prune_line(line: bytes) -> bytes:
    """Drop one entry's reverse delta, keeping its audit fields intact."""
    try:
        entry = WALEntry.model_validate_json(line)
    except ValidationError:
        return line
    if entry.reverse_delta is None:
        return line
    pruned = entry.model_copy(
        update={"reverse_delta": None, "delta_codec": CODEC_PRUNED}
    )
    return pruned.model_dump_json().encode("utf-8")


def _prune_oldest_deltas(lines: list[bytes], budget: int) -> tuple[int, int]:
    """Prune reverse deltas from the oldest entries (in place) until under budget.

    Returns ``(total_bytes_remaining, pruned_count)``.
    """
    total = sum(len(line) + 1 for line in lines)
    pruned_count = 0
    for index, line in enumerate(lines):
        if total <= budget:
            break
        pruned = _prune_line(line)
        if pruned is not line:
            pruned_count += 1
        total -= len(line) - len(pruned)
        lines[index] = pruned
    return total, pruned_count


def _drop_oldest_lines(lines: list[bytes], total: int, budget: int) -> int:
    """Drop whole oldest lines (in place) until under budget; return count dropped."""
    dropped_count = 0
    while lines and total > budget:
        total -= len(lines.pop(0)) + 1
        dropped_count += 1
    return dropped_count


def wal_compact_log_bytes(raw: bytes) -> WalCompactionResult:
    """Enforce the WAL size budget: prune oldest deltas, then drop oldest lines.

    Returns the compacted content plus which stage of the two-stage
    degradation ladder was actually reached: ``none`` (under budget
    already), ``deltas_pruned`` (reverse deltas dropped, all lines kept), or
    ``lines_dropped`` (whole lines removed after every prunable delta was
    exhausted). Also reports the same stage via ``logging``.
    """
    before = len(raw)
    if before <= _MAX_LOG_BYTES:
        return WalCompactionResult(
            content=raw, stage="none", pruned_count=0, dropped_count=0
        )
    lines = [line for line in raw.splitlines() if line.strip()]
    total, pruned_count = _prune_oldest_deltas(lines, _MAX_LOG_BYTES)
    dropped_count = _drop_oldest_lines(lines, total, _MAX_LOG_BYTES)
    content = b"".join(line + b"\n" for line in lines)
    stage: CompactionStage = (
        "lines_dropped"
        if dropped_count
        else "deltas_pruned"
        if pruned_count
        else "none"
    )
    _log_compaction_stage(before, len(content), pruned_count, dropped_count)
    return WalCompactionResult(
        content=content,
        stage=stage,
        pruned_count=pruned_count,
        dropped_count=dropped_count,
    )


def _log_compaction_stage(
    before: int, after: int, pruned_count: int, dropped_count: int
) -> None:
    """Report which rung of the degradation ladder compaction actually reached."""
    if dropped_count:
        logger.info(
            "WAL compaction reached lines_dropped: %d bytes -> %d bytes, "
            + "%d deltas pruned, %d lines dropped",
            before,
            after,
            pruned_count,
            dropped_count,
        )
    elif pruned_count:
        logger.debug(
            "WAL compaction reached deltas_pruned: %d bytes -> %d bytes, "
            + "%d deltas pruned",
            before,
            after,
            pruned_count,
        )


def _reconstruct_before(entry: WALEntry, step_number: int) -> WalAsOfResult:
    """Return the content ``entry`` overwrote, hash-verified."""
    text = wal_decode_reverse_delta(entry)
    if entry.content_hash_before == _ABSENT_HASH:
        return WalAsOfResult(
            file=entry.file,
            step_number=step_number,
            exists=False,
            content=None,
            source="reverse_delta",
            verified=True,
        )
    if wal_short_hash(text) != entry.content_hash_before:
        raise ValueError(
            f"WAL reverse delta for {entry.file} failed hash verification "
            + f"(expected {entry.content_hash_before})"
        )
    return WalAsOfResult(
        file=entry.file,
        step_number=step_number,
        exists=True,
        content=text,
        source="reverse_delta",
        verified=True,
    )


def wal_as_of_from_entries(
    *,
    file: str,
    step_number: int,
    entries: list[WALEntry],
    current_text: str | None,
) -> WalAsOfResult:
    """Reconstruct ``file`` at ``step_number`` from ordered WAL entries.

    ``entries`` must already be filtered to ``file`` and in log order. When no
    recorded write happened after ``step_number``, the on-disk content is what
    the file said then; it is hash-checked against the last recorded write.
    """
    for entry in entries:
        if entry.step_number is not None and entry.step_number > step_number:
            return _reconstruct_before(entry, step_number)
    verified = _current_matches_log(entries, current_text)
    return WalAsOfResult(
        file=file,
        step_number=step_number,
        exists=current_text is not None,
        content=current_text,
        source="current",
        verified=verified,
    )


def _current_matches_log(entries: list[WALEntry], current_text: str | None) -> bool:
    """True when on-disk content still matches the last recorded write."""
    if not entries or current_text is None:
        return False
    return wal_short_hash(current_text) == entries[-1].content_hash_after


def _validated_history_relative_path(file: str) -> Path:
    """Retain canonical WAL identities and the existing memory filename rules."""
    _ = InputValidator.validate_string_input(file, allow_newlines=False)
    if not file.startswith(MEMORY_BANK_PREFIX) or "\\" in file:
        raise ValueError("AS-OF requires a project-relative memory-bank Markdown path")
    relative = file.removeprefix(MEMORY_BANK_PREFIX)
    components = relative.split("/")
    if any(not part or part in {".", ".."} for part in components):
        raise ValueError("AS-OF path cannot contain empty, dot, or parent segments")
    for part in components:
        if InputValidator.validate_file_name(part) != part:
            raise ValueError("AS-OF path components must use canonical file names")
    if Path(relative).suffix != ".md":
        raise ValueError("AS-OF requires a memory-bank Markdown (.md) file")
    return Path(relative)


def resolve_memory_history_file(project_root: Path, file: str) -> Path:
    """Validate a memory-bank target before reading either content or history."""
    relative = _validated_history_relative_path(file)
    root = project_root.resolve()
    memory_bank = get_cortex_path(root, CortexResourceType.MEMORY_BANK)
    target = memory_bank / relative
    _validate_history_target(target, root)
    _ = InputValidator.validate_path(target, memory_bank)
    return target


def _validate_history_target(target: Path, root: Path) -> None:
    """Reject linked paths and unsupported types for content and its fixed WAL."""
    if not target.is_relative_to(root):
        raise ValueError(f"AS-OF path is outside project root: {target}")
    current = target
    while current != root:
        if current.is_symlink():
            raise ValueError(f"AS-OF paths cannot contain symlinks: {current}")
        if current != target and current.exists() and not current.is_dir():
            raise ValueError(f"AS-OF ancestor must be a directory: {current}")
        current = current.parent
    _ = InputValidator.validate_path(target, root)
    if target.exists() and not target.is_file():
        raise ValueError(f"AS-OF target must be a regular file: {target}")


def wal_as_of(project_root: Path, file: str, step_number: int) -> WalAsOfResult:
    """AS-OF view of a memory-bank file at an experience-store step number.

    Typed entry point for the analyze pipeline: callers get reconstructed
    content plus provenance instead of reading WAL files directly.
    """
    root = project_root.resolve()
    target = resolve_memory_history_file(root, file)
    identity = target.relative_to(root).as_posix()
    wal_dir = get_cortex_path(root, CortexResourceType.CORTEX_DIR) / "wal"
    _validate_history_target(wal_dir / WRITE_LOG_FILE_NAME, root)
    wal = MemoryWAL(wal_dir, project_root=root)
    entries = [entry for entry in wal.read() if entry.file == identity]
    # AI: A history read can yield to filesystem changes; recheck before current content.
    target = resolve_memory_history_file(root, identity)
    current = target.read_text(encoding="utf-8") if target.is_file() else None
    return wal_as_of_from_entries(
        file=identity,
        step_number=step_number,
        entries=entries,
        current_text=current,
    )
