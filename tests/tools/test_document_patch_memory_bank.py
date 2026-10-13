"""Closed-target and structured-entry boundaries for Memory Bank repairs."""

import asyncio
import hashlib
import json
import stat
from pathlib import Path
from typing import cast

import pytest

from cortex.core.file_system import FileSystemManager
from cortex.tools.files.document_patch_operations import handle_document_patch
from cortex.tools.files.manage_file_helpers import execute_file_operation
from cortex.tools.files.operation_helpers import FileOperation

_TARGETS = [".cortex/memory-bank/activeContext.md", ".cortex/memory-bank/progress.md"]
_BODY = (
    "---\r\nstatus: DONE\r\n---\r\n# Context\r\n\r\n"
    "## 2026-10-02\r\n\r\n"
    "- <!-- memory_type: milestone -->\r\n"
    "- ✅ **First repair** - COMPLETE. measured 2026-10-02 14:27Z; 21 entries.\r\n"
    "- [ ] **Second repair** - PENDING; 34 entries.\r\n"
    "**Last updated**: 2026-10-01\r\n"
    "Status: paused\r\n"
    "Execution: manual\r\n"
    "Untouched Unicode: é; 43 entries.\r\n"
    "Plain first entry.\r\nPlain second entry.\r\n\r\n"
    "Setext section\r\n--------------\r\n\r\n"
    "```text\r\nFenced evidence\r\n~~~\r\nStill fenced\r\n```\r\n\r\n"
    "    Indented evidence\r\n\r\n| Column |\r\n| --- |\r\n| Value |\r\n"
).encode("utf-8")
_OLD = "measured 2026-10-02 14:27Z"
_NEW = "measured 2026-10-02T14:27Z"


def _fixture(root: Path, relative: str) -> Path:
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    _ = target.write_bytes(_BODY)
    return target


def _payload(*, old: str = _OLD, new: str = _NEW, **fields: object) -> str:
    return json.dumps(
        {
            "expected_sha256": hashlib.sha256(_BODY).hexdigest(),
            "replacements": [{"old": old, "new": new, "count": 1}],
            **fields,
        }
    )


async def _patch(
    root: Path, relative: str, *, old: str = _OLD, new: str = _NEW, **fields: object
) -> dict[str, object]:
    return cast(
        dict[str, object],
        json.loads(
            await handle_document_patch(
                root, relative, _payload(old=old, new=new, **fields)
            )
        ),
    )


async def _native_patch(root: Path, relative: str, dry_run: bool) -> dict[str, object]:
    return cast(
        dict[str, object],
        json.loads(
            await execute_file_operation(
                root,
                relative,
                FileOperation.PATCH_DOCUMENT,
                _payload(dry_run=dry_run),
                False,
                None,
                None,
            )
        ),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("relative", _TARGETS)
@pytest.mark.parametrize("dry_run", [True, False])
async def test_native_entry_repair_preserves_other_bytes_and_mode(
    tmp_path: Path, relative: str, dry_run: bool
) -> None:
    root = tmp_path.resolve()
    target = _fixture(root, relative)
    neighbor = _fixture(root, ".cortex/wiki/untouched.md")
    target.chmod(0o640)
    before_mtime = target.stat().st_mtime_ns
    inventory = set(root.rglob("*"))
    result = await _native_patch(root, relative, dry_run)
    after = _BODY.replace(_OLD.encode(), _NEW.encode(), 1)
    assert result["status"] == "success", result
    assert result["project_root"] == str(root)
    assert result["target"] == relative
    assert result["before_sha256"] == hashlib.sha256(_BODY).hexdigest()
    assert result["after_sha256"] == hashlib.sha256(after).hexdigest()
    assert result["replacement_counts"] == [1]
    assert result["mutation_performed"] is not dry_run
    assert target.read_bytes() == (_BODY if dry_run else after)
    assert stat.S_IMODE(target.stat().st_mode) == 0o640
    assert not dry_run or target.stat().st_mtime_ns == before_mtime
    assert neighbor.read_bytes() == _BODY
    assert set(root.rglob("*")) == inventory


@pytest.mark.asyncio
@pytest.mark.parametrize("relative", _TARGETS)
@pytest.mark.parametrize("dry_run", [True, False])
@pytest.mark.parametrize(
    "old,new",
    [
        ("status: DONE", "status: PENDING"),
        ("# Context", "# Other"),
        ("## 2026-10-02", "## 2026-10-03"),
        ("Setext section", "Renamed section"),
        ("First repair", "Another entry"),
        ("COMPLETE", "PENDING"),
        ("PENDING", "done"),
        ("Status: paused", "Status: finished"),
        ("Execution: manual", "Execution: automated"),
        ("- [ ]", "- [x]"),
        ("- ✅", "1. ✅"),
        ("- ✅ **First repair**", "- # ✅ **First repair**"),
        ("- ✅ **First repair**", "- - ✅ **First repair**"),
        ("memory_type: milestone", "memory_type: decision"),
        (_OLD, _OLD),
        (_OLD, ""),
        (_OLD, "\n- Added entry"),
        (_OLD, "\rInserted entry"),
        (_OLD, "\u2028Inserted entry"),
        (_OLD, "\x00Hidden bytes"),
        ("Plain first entry.\r\nPlain second entry.", "Reordered entries."),
        ("Plain first entry.", "Plain second entry."),
        ("Plain first entry.", "## New heading"),
        ("Plain first entry.", "- New bullet"),
        ("Plain first entry.", "    New code"),
        ("Fenced evidence", "Changed code"),
        ("Still fenced", "Changed fence evidence"),
        ("Indented evidence", "Changed code"),
        ("| Value |", "| Changed |"),
        ("43 entries.", "43 entries.\n"),
    ],
)
async def test_outline_entries_and_lifecycle_cannot_be_mutated(
    tmp_path: Path, relative: str, dry_run: bool, old: str, new: str
) -> None:
    target = _fixture(tmp_path, relative)
    inventory = set(tmp_path.rglob("*"))
    result = await _patch(
        tmp_path.resolve(), relative, old=old, new=new, dry_run=dry_run
    )
    assert result["status"] == "error", result
    assert result["mutation_performed"] is False
    assert target.read_bytes() == _BODY
    assert set(tmp_path.rglob("*")) == inventory


@pytest.mark.asyncio
@pytest.mark.parametrize("relative", _TARGETS)
async def test_full_line_and_timestamp_prose_repair_remain_targeted(
    tmp_path: Path, relative: str
) -> None:
    target = _fixture(tmp_path, relative)
    old = "- ✅ **First repair** - COMPLETE. measured 2026-10-02 14:27Z; 21 entries."
    new = old.replace(" 14:27Z", "T14:27Z")
    result = await _patch(
        tmp_path.resolve(),
        relative,
        replacements=[
            {"old": old, "new": new, "count": 1},
            {
                "old": "**Last updated**: 2026-10-01",
                "new": "**Last updated**: 2026-10-02",
                "count": 1,
            },
        ],
    )
    assert result["status"] == "success", result
    assert target.read_bytes() == _BODY.replace(old.encode(), new.encode()).replace(
        b"**Last updated**: 2026-10-01", b"**Last updated**: 2026-10-02"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("relative", _TARGETS)
@pytest.mark.parametrize(
    "fields",
    [
        {"expected_sha256": "0" * 64},
        {"operator_authorized": True},
        {"content": "# Replacement document"},
        {"replacements": [{"old": "entries", "new": "items", "count": 1}]},
        {"replacements": [{"old": _OLD, "new": _NEW, "count": 2}]},
        {
            "replacements": [
                {"old": _OLD, "new": _NEW, "count": 1},
                {"old": "14:27Z", "new": "14:27 UTC", "count": 1},
            ]
        },
    ],
)
async def test_hash_schema_uniqueness_and_overlap_remain_enforced(
    tmp_path: Path, relative: str, fields: dict[str, object]
) -> None:
    target = _fixture(tmp_path, relative)
    request = cast(dict[str, object], json.loads(_payload()))
    request.update(fields)
    result = json.loads(
        await handle_document_patch(tmp_path.resolve(), relative, json.dumps(request))
    )
    assert result["status"] == "error", result
    assert target.read_bytes() == _BODY
    assert not target.with_suffix(".md.lock").exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("relative", _TARGETS)
@pytest.mark.parametrize("kind", ["file", "ancestor", "root", "lock"])
async def test_entry_target_symlinks_and_lock_symlinks_are_refused(
    tmp_path: Path, relative: str, kind: str
) -> None:
    root = tmp_path / "workspace"
    target = _fixture(root, relative)
    outside = _fixture(tmp_path, "outside.md")
    if kind == "file":
        target.unlink()
        target.symlink_to(outside)
    elif kind == "ancestor":
        target.unlink()
        target.parent.rmdir()
        target.parent.symlink_to(tmp_path, target_is_directory=True)
    elif kind == "root":
        alias = tmp_path / "alias"
        alias.symlink_to(root, target_is_directory=True)
        root = alias
    else:
        target.with_suffix(".md.lock").symlink_to(outside)
    result = await _patch(root, relative)
    assert result["status"] == "error", result
    assert outside.read_bytes() == _BODY
    assert not list(tmp_path.rglob(".wal_*"))


@pytest.mark.asyncio
@pytest.mark.parametrize("relative", _TARGETS)
async def test_entry_lock_rechecks_stale_preimage(
    tmp_path: Path, relative: str
) -> None:
    root = tmp_path.resolve()
    target = _fixture(root, relative)
    lock = target.with_suffix(".md.lock")
    manager = FileSystemManager(root)
    await manager.acquire_lock(lock)
    pending = asyncio.create_task(_patch(root, relative))
    await asyncio.sleep(0)
    changed = _BODY + b"Concurrent unrelated entry\r\n"
    _ = target.write_bytes(changed)
    await manager.release_lock(lock)
    result = await pending
    assert result["status"] == "error", result
    assert "Stale" in str(result["error"])
    assert target.read_bytes() == changed
    assert not lock.exists()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "relative",
    [
        ".cortex/memory-bank/projectBrief.md",
        ".cortex/memory-bank/ActiveContext.md",
        ".cortex/memory-bank/progress.MD",
        ".cortex/memory-bank/nested/progress.md",
        ".cortex/memory-bank/../memory-bank/progress.md",
        ".cortex/memory-bank/progress.md.bak",
    ],
)
async def test_only_exact_existing_memory_bank_targets_are_allowed(
    tmp_path: Path, relative: str
) -> None:
    result = await _patch(tmp_path.resolve(), relative)
    assert result["status"] == "error", result
    assert list(tmp_path.iterdir()) == []
