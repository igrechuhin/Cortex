"""The active-plan block transition and its dependency graph consequences."""

import asyncio
import hashlib
import json
import stat
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, patch

import pytest

from cortex.core.artifact_graph import compute_artifact_graph
from cortex.core.file_system import FileSystemManager
from cortex.tools.plans.completion_transaction_io import completion_lock
from cortex.tools.plans.plan import plan
from cortex.tools.plans.register_artifact_graph import (
    sync_plan_dependency_statuses_after_completion,
)

_READY = (
    b"\xef\xbb\xbf---\r\ntitle: Fiber\r\nstatus : 'READY'  # keep comment\r\n"
    b"execution: operator\r\ndepends_on: [base]\r\n---\r\n# Fiber\r\n\r\n"
    b"Body has a status: READY witness.\r\n"
)
_BLOCKED = _READY.replace(b"'READY'", b"'BLOCKED'", 1)
_ROW = "- **Fiber** - BLOCKED - External clock. Plan: .cortex/plans/fiber.md"


def _seed(root: Path, row: str = _ROW, body: bytes = _READY) -> tuple[Path, Path]:
    plans = root / ".cortex/plans"
    plans.mkdir(parents=True)
    _ = (plans / "base.md").write_text("---\nstatus: DONE\n---\n# Base\n")
    target = plans / "fiber.md"
    _ = target.write_bytes(body)
    roadmap = root / ".cortex/memory-bank/roadmap.md"
    roadmap.parent.mkdir()
    _ = roadmap.write_text(
        f"# Roadmap\n\n## Pending plans (from .cortex/plans)\n\n{row}\n"
    )
    return target, roadmap


async def _call(
    root: Path, *, slug: str = "fiber", body: bytes = _READY, **overrides: object
) -> dict[str, object]:
    payload = {
        "expected_sha256": hashlib.sha256(body).hexdigest(),
        "reason": "Existing approved roadmap block",
        "dry_run": False,
        **overrides,
    }
    with (
        patch(
            "cortex.tools.plans.mark_blocked.get_or_resolve_project_root",
            new_callable=AsyncMock,
            return_value=str(root.resolve()),
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
                    operation="mark_blocked", slug=slug, content=json.dumps(payload)
                )
            ),
        )


@pytest.mark.asyncio
async def test_preview_apply_and_retry_reconcile_graph(tmp_path: Path) -> None:
    target, roadmap = _seed(tmp_path)
    target.chmod(0o640)
    before = roadmap.read_bytes()
    preview = await _call(tmp_path, dry_run=True)
    assert preview["status"] == "success", preview
    assert preview["mutation_performed"] is False
    assert preview["after_sha256"] == hashlib.sha256(_BLOCKED).hexdigest()
    assert target.read_bytes() == _READY
    assert "fiber" in compute_artifact_graph(target.parent).ready

    applied = await _call(tmp_path)
    assert applied["previous_status"] == "READY"
    assert applied["new_status"] == "BLOCKED"
    assert applied["mutation_performed"] is True
    assert target.read_bytes() == _BLOCKED
    assert stat.S_IMODE(target.stat().st_mode) == 0o640
    assert roadmap.read_bytes() == before
    graph = compute_artifact_graph(target.parent)
    assert "fiber" not in graph.ready
    assert "fiber" in graph.blocked

    retry = await _call(tmp_path, body=_BLOCKED)
    assert retry["status"] == "success"
    assert retry["mutation_performed"] is False
    assert target.read_bytes() == _BLOCKED


@pytest.mark.asyncio
async def test_pending_applies_only_after_completion_releases_its_lock(
    tmp_path: Path,
) -> None:
    body = _READY.replace(b"'READY'", b"'PENDING'", 1)
    target, _ = _seed(tmp_path, body=body)
    async with completion_lock(tmp_path):
        task = asyncio.create_task(_call(tmp_path, body=body))
        await asyncio.sleep(0)
        assert not task.done()
        assert target.read_bytes() == body
    result = await task
    assert result["previous_status"] == "PENDING"
    assert result["new_status"] == "BLOCKED"
    assert target.read_bytes() == _BLOCKED


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "row",
    [
        _ROW.replace(" - BLOCKED - ", " - READY - "),
        _ROW + "\n" + _ROW,
        _ROW + " _(BLOCKED by: base)_",
        "~~~markdown\n" + _ROW + "\n~~~",
        "## Historical Operator Decisions\n\n" + _ROW,
    ],
)
async def test_requires_one_explicit_canonical_roadmap_row(
    tmp_path: Path, row: str
) -> None:
    target, roadmap = _seed(tmp_path, row)
    before = roadmap.read_bytes()
    result = await _call(tmp_path)
    assert result["status"] == "error", result
    assert result["mutation_performed"] is False
    assert target.read_bytes() == _READY
    assert roadmap.read_bytes() == before


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("expected_sha256", "reason"),
    [("0" * 64, "Known block"), (hashlib.sha256(_READY).hexdigest(), " ")],
)
async def test_stale_hash_and_blank_reason_refuse(
    tmp_path: Path, expected_sha256: str, reason: str
) -> None:
    target, _ = _seed(tmp_path)
    result = await _call(tmp_path, expected_sha256=expected_sha256, reason=reason)
    assert result["status"] == "error"
    assert result["mutation_performed"] is False
    assert target.read_bytes() == _READY


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "token", [b"DONE", b"CANCELLED", b"IN_PROGRESS", b"READY'\r\nstatus: READY"]
)
async def test_invalid_status_is_nonmutating(tmp_path: Path, token: bytes) -> None:
    body = _READY.replace(b"READY", token, 1)
    target, _ = _seed(tmp_path, body=body)
    result = await _call(tmp_path, body=body)
    assert result["status"] == "error"
    assert result["mutation_performed"] is False
    assert target.read_bytes() == body


@pytest.mark.asyncio
async def test_rejects_unsafe_path_and_duplicate_identity(tmp_path: Path) -> None:
    target, _ = _seed(tmp_path)
    archived = target.parent / "archive" / target.name
    archived.parent.mkdir()
    _ = archived.write_bytes(_READY)
    for slug in ("../fiber", "fiber.md", "fiber"):
        result = await _call(tmp_path, slug=slug)
        assert result["status"] == "error"
        assert result["mutation_performed"] is False
    assert target.read_bytes() == archived.read_bytes() == _READY


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("suffix", "completed_slug", "expected"),
    [("", "unrelated", 0), ("", "base", 1), (" _(BLOCKED by: base)_", "unrelated", 1)],
)
async def test_completion_resync_preserves_only_explicit_roadmap_block(
    tmp_path: Path, suffix: str, completed_slug: str, expected: int
) -> None:
    target, _ = _seed(tmp_path, _ROW + suffix, _BLOCKED)
    promoted = await sync_plan_dependency_statuses_after_completion(
        tmp_path, None, completed_slug=completed_slug
    )
    assert promoted == expected
    graph = compute_artifact_graph(target.parent)
    assert ("fiber" in graph.blocked) == (expected == 0)
    if expected == 0:
        assert target.read_bytes() == _BLOCKED


@pytest.mark.asyncio
async def test_unmet_declared_dependency_cannot_be_reclassified_as_operator_block(
    tmp_path: Path,
) -> None:
    target, _ = _seed(tmp_path)
    _ = (target.parent / "base.md").write_text("---\nstatus: READY\n---\n# Base\n")
    result = await _call(tmp_path)
    assert result["status"] == "error"
    assert result["mutation_performed"] is False
    assert target.read_bytes() == _READY


@pytest.mark.asyncio
async def test_completion_resync_reads_roadmap_after_registration_lock(
    tmp_path: Path,
) -> None:
    target, roadmap = _seed(tmp_path, _ROW + " _(BLOCKED by: base)_", _BLOCKED)
    manager = FileSystemManager(tmp_path)
    lock = roadmap.with_suffix(".md.lock")
    await manager.acquire_lock(lock)
    try:
        task = asyncio.create_task(
            sync_plan_dependency_statuses_after_completion(tmp_path, None)
        )
        await asyncio.sleep(0)
        assert not task.done()
        _ = roadmap.write_text(roadmap.read_text().replace(" _(BLOCKED by: base)_", ""))
    finally:
        await manager.release_lock(lock)
    assert await task == 0
    assert target.read_bytes() == _BLOCKED
