"""Consumer-visible guarded owner correction, isolated from real workspaces."""

import hashlib
import json
import os
import stat
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, patch

import pytest

from cortex.core.file_system import FileSystemManager
from cortex.tools.plans.plan import plan

_BODY = (
    b"\xef\xbb\xbf---\r\ntitle: Owner correction\r\nstatus: BLOCKED\r\n"
    b"execution : 'operator'  # authorized owner\r\nid: stable\r\n---\r\n"
    b"# Owner correction\r\n\r\nUnicode: \xc3\xa9\r\n- [ ] unfinished\r\n"
    b"execution: operator\r\n"
)


def _write(root: Path, name: str = "owner", body: bytes = _BODY) -> Path:
    target = root / ".cortex" / "plans" / f"{name}.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    _ = target.write_bytes(body)
    return target


async def _call(
    root: Path, slug: str | None = "owner", body: bytes = _BODY, /, **overrides: object
) -> dict[str, object]:
    payload = {
        "expected_sha256": hashlib.sha256(body).hexdigest(),
        "execution": "agent",
        "reason": "User authorized correcting contradictory execution owner",
        "dry_run": False,
        **overrides,
    }
    with (
        patch(
            "cortex.tools.plans.execution.get_or_resolve_project_root",
            new_callable=AsyncMock,
            return_value=str(root),
        ),
        patch(
            "cortex.core.mcp_stability_usage.get_current_managers",
            return_value={},
        ),
    ):
        return cast(
            dict[str, object],
            json.loads(
                await plan(
                    operation="set_execution", slug=slug, content=json.dumps(payload)
                )
            ),
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("dry_run", [True, False])
async def test_preview_apply_preserves_all_unrelated_bytes(
    tmp_path: Path, dry_run: bool
) -> None:
    target = _write(tmp_path)
    target.chmod(0o640)
    before_stat = target.stat()
    files = set(tmp_path.rglob("*"))
    result = await _call(tmp_path, dry_run=dry_run)
    after = _BODY.replace(b"'operator'", b"'agent'", 1)
    assert result == {
        "status": "success",
        "operation": "set_execution",
        "project_root": str(tmp_path),
        "target": ".cortex/plans/owner.md",
        "before_sha256": hashlib.sha256(_BODY).hexdigest(),
        "after_sha256": hashlib.sha256(after).hexdigest(),
        "previous_execution": "operator",
        "new_execution": "agent",
        "reason": "User authorized correcting contradictory execution owner",
        "dry_run": dry_run,
        "mutation_performed": not dry_run,
    }
    assert target.read_bytes() == (_BODY if dry_run else after)
    assert stat.S_IMODE(target.stat().st_mode) == 0o640
    assert set(tmp_path.rglob("*")) == files
    if dry_run:
        assert target.stat().st_mtime_ns == before_stat.st_mtime_ns


@pytest.mark.asyncio
async def test_already_matching_owner_noop(tmp_path: Path) -> None:
    target = _write(tmp_path)
    result = await _call(tmp_path, execution="operator")
    assert result["status"] == "success", result
    assert result["mutation_performed"] is False
    assert result["before_sha256"] == result["after_sha256"]
    assert target.read_bytes() == _BODY


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overrides",
    [
        {"expected_sha256": "0" * 64},
        {"expected_sha256": "sha256:" + "0" * 64},
        {"expected_sha256": None},
        {"dry_run": "true"},
        {"execution": "unknown"},
        {"reason": "  "},
        {"extra": "forbidden"},
    ],
)
async def test_invalid_payload_is_nonmutating(
    tmp_path: Path, overrides: dict[str, object]
) -> None:
    target = _write(tmp_path)
    result = await _call(tmp_path, **overrides)
    assert result["status"] == "error", result
    assert result["mutation_performed"] is False
    assert target.read_bytes() == _BODY
    assert not target.with_suffix(".md.lock").exists()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "slug",
    [
        None,
        "../owner",
        "/tmp/owner",
        "archive/owner",
        "owner.md",
        "README",
        "TEMPLATE",
        "a\\b",
        "a..b",
    ],
)
async def test_unsafe_scaffold_and_archive_paths_rejected(
    tmp_path: Path, slug: str | None
) -> None:
    target = _write(tmp_path)
    _ = _write(tmp_path, "archive/owner")
    _ = _write(tmp_path, "README")
    _ = _write(tmp_path, "TEMPLATE")
    result = await _call(tmp_path, slug)
    assert result["status"] == "error", result
    assert target.read_bytes() == _BODY


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kind",
    [
        "file",
        "ancestor",
        "root",
        "lock",
        "directory",
        "fifo",
        "missing",
        "archive_only",
    ],
)
async def test_invalid_target_types_rejected(tmp_path: Path, kind: str) -> None:
    root = tmp_path / "workspace"
    target = _write(root)
    external = _write(tmp_path / "external")
    if kind == "lock":
        target.with_suffix(".md.lock").symlink_to(external)
    elif kind == "root":
        pointer = tmp_path / "pointer"
        pointer.symlink_to(root, target_is_directory=True)
        root = pointer
    elif kind == "ancestor":
        target.unlink()
        target.parent.rmdir()
        target.parent.symlink_to(external.parent, target_is_directory=True)
    else:
        target.unlink()
        if kind == "file":
            target.symlink_to(external)
        elif kind == "directory":
            target.mkdir()
        elif kind == "fifo":
            os.mkfifo(target)
        elif kind == "archive_only":
            _ = _write(root, "archive/owner")
    result = await _call(root)
    assert result["status"] == "error", result
    assert result["mutation_performed"] is False
    assert external.read_bytes() == _BODY


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "replacement",
    [
        b"",
        b"execution: unknown",
        b"execution: [operator]",
        b"execution: operator\r\nexecution: operator",
        b"execution: operator\r\nexecution: agent",
        b"execution: operator\r\n'execution': agent",
        b"execution: operator\r\n<<: {execution: agent}",
    ],
)
async def test_missing_duplicate_conflicting_nonscalar_owner_rejected(
    tmp_path: Path, replacement: bytes
) -> None:
    body = _BODY.replace(b"execution : 'operator'  # authorized owner", replacement)
    target = _write(tmp_path, body=body)
    result = await _call(tmp_path, "owner", body)
    assert result["status"] == "error", result
    assert target.read_bytes() == body


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    [
        b"DONE",
        b"COMPLETE",
        b"COMPLETED",
        b"DECLINED",
        b"UNKNOWN",
        b"PENDING\r\nstatus: DONE",
    ],
)
async def test_terminal_or_unrecognized_status_rejected(
    tmp_path: Path, status: bytes
) -> None:
    body = _BODY.replace(b"status: BLOCKED", b"status: " + status)
    target = _write(tmp_path, body=body)
    result = await _call(tmp_path, "owner", body)
    assert result["status"] == "error", result
    assert target.read_bytes() == body


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["duplicate", "terminal_title", "draft"])
async def test_ambiguous_and_terminal_identity_rejected(
    tmp_path: Path, kind: str
) -> None:
    body = _BODY
    if kind == "duplicate":
        _ = _write(tmp_path, "archive/owner")
    elif kind == "terminal_title":
        body = body.replace(b"# Owner correction", b"# Owner correction (DONE)")
    else:
        body += b"<!-- CORTEX_STEP_PLAN_STATE\n{}\n-->\n"
    target = _write(tmp_path, body=body)
    result = await _call(tmp_path, "owner", body)
    assert result["status"] == "error", result
    assert target.read_bytes() == body


@pytest.mark.asyncio
@pytest.mark.parametrize("dry_run", [False, True])
async def test_stale_under_lock_recheck(tmp_path: Path, dry_run: bool) -> None:
    target = _write(tmp_path)
    acquire = FileSystemManager.acquire_lock
    changed = _BODY + b"Concurrent edit\r\n"

    async def change_on_acquire(manager: FileSystemManager, lock: Path) -> None:
        await acquire(manager, lock)
        _ = target.write_bytes(changed)

    with patch.object(FileSystemManager, "acquire_lock", change_on_acquire):
        result = await _call(tmp_path, dry_run=dry_run)
    assert result["status"] == "error", result
    assert "Stale expected_sha256" in str(result["error"])
    assert target.read_bytes() == changed
    assert not target.with_suffix(".md.lock").exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [b"PENDING", b"READY", b"IN_PROGRESS", b"BLOCKED"])
async def test_agent_to_operator_preserves_active_status(
    tmp_path: Path, status: bytes
) -> None:
    body = _BODY.replace(b"status: BLOCKED", b"status: " + status).replace(
        b"'operator'", b"'agent'", 1
    )
    target = _write(tmp_path, body=body)
    result = await _call(tmp_path, "owner", body, execution="operator")
    assert result["status"] == "success", result
    assert result["previous_execution"] == "agent"
    assert result["new_execution"] == "operator"
    assert target.read_bytes() == body.replace(b"'agent'", b"'operator'", 1)


@pytest.mark.asyncio
async def test_quoted_conflicting_terminal_status_rejected(tmp_path: Path) -> None:
    body = _BODY.replace(b"status: BLOCKED", b"status: BLOCKED\r\n'status': DONE")
    target = _write(tmp_path, body=body)
    result = await _call(tmp_path, "owner", body)
    assert result["status"] == "error", result
    assert target.read_bytes() == body
