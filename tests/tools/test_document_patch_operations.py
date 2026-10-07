"""Temporary-workspace evidence for guarded literal document repairs."""

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

_BODY = (
    b"---\r\nstatus: DONE\r\ntitle: Canceled plan\r\n---\r\n"
    b"# Canceled plan (DONE)\r\n\r\n- [ ] obsolete step\r\n"
    b"Reference: ../old.md\r\nUntouched Unicode: \xc3\xa9\r\n"
)
_TARGET = ".cortex/plans/archive/canceled.md"


def _write(root: Path, relative: str, body: bytes = _BODY) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_bytes(body)
    return path


def _payload(body: bytes = _BODY, /, **overrides: object) -> str:
    return json.dumps(
        {
            "expected_sha256": hashlib.sha256(body).hexdigest(),
            "replacements": [
                {"old": "- [ ] obsolete step", "new": "- [x] obsolete step", "count": 1}
            ],
            **overrides,
        }
    )


async def _patch(
    root: Path, relative: str = _TARGET, /, **overrides: object
) -> dict[str, object]:
    return cast(
        dict[str, object],
        json.loads(
            await handle_document_patch(root.resolve(), relative, _payload(**overrides))
        ),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("dry_run", [False, True])
async def test_exact_patch_preserves_mode_metadata_and_unmatched_bytes(
    tmp_path: Path, dry_run: bool
) -> None:
    target = _write(tmp_path, _TARGET)
    target.chmod(0o640)
    before_stat = target.stat()
    active = _write(tmp_path, ".cortex/memory-bank/activeContext.md", b"# Context\r\n")
    wiki = _write(tmp_path, ".cortex/wiki/index.md", b"# Wiki\r\n")
    files = set(tmp_path.rglob("*"))
    result = await _patch(tmp_path, dry_run=dry_run)
    after = _BODY.replace(b"- [ ] obsolete step", b"- [x] obsolete step", 1)
    assert result == {
        "status": "success",
        "operation": "patch_document",
        "project_root": str(tmp_path.resolve()),
        "target": _TARGET,
        "before_sha256": hashlib.sha256(_BODY).hexdigest(),
        "after_sha256": hashlib.sha256(after).hexdigest(),
        "replacement_counts": [1],
        "dry_run": dry_run,
        "mutation_performed": not dry_run,
    }
    assert target.read_bytes() == (_BODY if dry_run else after)
    assert stat.S_IMODE(target.stat().st_mode) == 0o640
    if dry_run:
        assert target.stat().st_mtime_ns == before_stat.st_mtime_ns
    assert active.read_bytes() == b"# Context\r\n"
    assert wiki.read_bytes() == b"# Wiki\r\n"
    assert set(tmp_path.rglob("*")) == files


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "relative",
    [
        ".cortex/plans/index.md",
        ".cortex/analyses/report.md",
        ".cortex/reviews/report.md",
        ".cortex/memory-bank/roadmap.md",
    ],
)
async def test_closed_allowed_roots(tmp_path: Path, relative: str) -> None:
    target = _write(tmp_path, relative)
    result = await _patch(tmp_path, relative)
    assert result["status"] == "success", result
    assert b"- [x] obsolete step" in target.read_bytes()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "relative",
    [
        "../outside.md",
        "/tmp/outside.md",
        ".cortex/plans/../index.md",
        ".cortex/plans/./index.md",
        ".cortex//plans/index.md",
        ".cortex/plans/bad\\name.md",
        ".cortex/plans/bad\nname.md",
        ".cortex/plans/bad:name.md",
        ".cortex/plans/ spaced.md",
        ".cortex/plans/file.txt",
        ".cortex/plans.md",
        ".cortex/memory-bank/activeContext.md",
        ".cortex/memory-bank/progress.md",
        ".cortex/memory-bank/reviews/report.md",
        ".cortex/wiki/report.md",
    ],
)
async def test_unsafe_and_noncanonical_targets_refused(
    tmp_path: Path, relative: str
) -> None:
    result = await _patch(tmp_path, relative)
    assert result["status"] == "error", result
    assert result["mutation_performed"] is False
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["missing", "directory", "fifo"])
async def test_missing_and_nonregular_targets_never_created(
    tmp_path: Path, kind: str
) -> None:
    import os

    target = tmp_path / _TARGET
    target.parent.mkdir(parents=True)
    if kind == "directory":
        target.mkdir()
    elif kind == "fifo":
        os.mkfifo(target)
    result = await _patch(tmp_path)
    assert result["status"] == "error", result
    assert not target.with_suffix(".md.lock").exists()
    if kind == "missing":
        assert not target.exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["file", "ancestor", "root", "lock"])
async def test_symlink_ancestry_and_lock_refused(tmp_path: Path, kind: str) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = _write(workspace, _TARGET)
    external = _write(tmp_path, "external.md")
    if kind == "file":
        target.unlink()
        target.symlink_to(external)
    elif kind == "ancestor":
        target.unlink()
        target.parent.rmdir()
        target.parent.symlink_to(tmp_path, target_is_directory=True)
    elif kind == "root":
        pointer = tmp_path / "pointer"
        pointer.symlink_to(workspace, target_is_directory=True)
        workspace = pointer
    else:
        target.with_suffix(".md.lock").symlink_to(external)
    result = json.loads(await handle_document_patch(workspace, _TARGET, _payload()))
    assert result["status"] == "error", result
    assert external.read_bytes() == _BODY
    assert not list(tmp_path.rglob(".wal_*"))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overrides",
    [
        {"expected_sha256": "0" * 64},
        {"expected_sha256": "sha256:" + "0" * 64},
        {"dry_run": "true"},
        {"extra": "forbidden"},
        {"replacements": []},
        {"replacements": [{"old": "", "new": "x", "count": 1}]},
        {"replacements": [{"old": "obsolete", "new": "obsolete", "count": 1}]},
        {"replacements": [{"old": "missing", "new": "new", "count": 1}]},
        {"replacements": [{"old": "obsolete", "new": "new", "count": True}]},
        {"replacements": [{"old": "obsolete", "new": "new", "count": 2}]},
        {"replacements": [{"old": "obsolete", "new": "new"}]},
        {"replacements": [{"old": "DONE", "new": "PENDING", "count": 1}]},
    ],
)
async def test_invalid_stale_and_nonunique_requests_leave_no_artifacts(
    tmp_path: Path, overrides: dict[str, object]
) -> None:
    target = _write(tmp_path, _TARGET)
    files = set(tmp_path.rglob("*"))
    result = await _patch(tmp_path, **overrides)
    assert result["status"] == "error", result
    assert target.read_bytes() == _BODY
    assert set(tmp_path.rglob("*")) == files


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "replacements",
    [
        [
            {"old": "obsolete", "new": "new", "count": 1},
            {"old": "obsolete", "new": "other", "count": 1},
        ],
        [
            {"old": "obsolete step", "new": "new", "count": 1},
            {"old": "step", "new": "other", "count": 1},
        ],
        [{"old": "status: DONE", "new": "status: PENDING", "count": 1}],
        [{"old": "# Canceled plan (DONE)", "new": "# Active plan", "count": 1}],
    ],
)
async def test_overlap_duplicate_and_lifecycle_changes_refused(
    tmp_path: Path, replacements: list[dict[str, object]]
) -> None:
    target = _write(tmp_path, _TARGET)
    result = await _patch(tmp_path, replacements=replacements)
    assert result["status"] == "error", result
    assert target.read_bytes() == _BODY


@pytest.mark.asyncio
async def test_replacements_use_original_bytes_not_cascading_output(
    tmp_path: Path,
) -> None:
    target = _write(tmp_path, _TARGET)
    result = await _patch(
        tmp_path,
        replacements=[
            {"old": "obsolete", "new": "Reference", "count": 1},
            {"old": "Reference", "new": "Link", "count": 1},
        ],
    )
    assert result["status"] == "success", result
    assert target.read_bytes() == _BODY.replace(b"obsolete", b"Reference").replace(
        b"Reference:", b"Link:"
    )
    assert result["replacement_counts"] == [1, 1]


@pytest.mark.asyncio
async def test_invalid_utf8_is_refused(tmp_path: Path) -> None:
    body = _BODY + b"\xff"
    target = _write(tmp_path, _TARGET, body)
    result = json.loads(
        await handle_document_patch(tmp_path.resolve(), _TARGET, _payload(body))
    )
    assert result["status"] == "error", result
    assert target.read_bytes() == body


@pytest.mark.asyncio
async def test_waiting_writer_rechecks_hash_under_existing_lock(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    target = _write(root, _TARGET)
    lock = target.with_suffix(".md.lock")
    manager = FileSystemManager(root)
    await manager.acquire_lock(lock)
    pending = asyncio.create_task(handle_document_patch(root, _TARGET, _payload()))
    await asyncio.sleep(0)
    changed = _BODY + b"Concurrent edit\r\n"
    _ = target.write_bytes(changed)
    await manager.release_lock(lock)
    result = json.loads(await pending)
    assert result["status"] == "error", result
    assert "Stale" in result["error"]
    assert target.read_bytes() == changed
    assert not lock.exists()


@pytest.mark.asyncio
async def test_native_dispatch_accepts_workspace_relative_target(
    tmp_path: Path,
) -> None:
    target = _write(tmp_path, _TARGET)
    result = json.loads(
        await execute_file_operation(
            tmp_path.resolve(),
            _TARGET,
            FileOperation.PATCH_DOCUMENT,
            _payload(),
            False,
            None,
            None,
        )
    )
    assert result["status"] == "success", result
    assert b"status: DONE\r\n" in target.read_bytes()
    assert b"# Canceled plan (DONE)\r\n" in target.read_bytes()
