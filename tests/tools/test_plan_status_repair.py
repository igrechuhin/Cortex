"""Focused regressions for evidence-gated archived status repair."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, patch

import pytest

from cortex.core.exceptions import FileLockTimeoutError
from cortex.core.file_system import FileSystemManager
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.plans.status_repair import repair_archived_plan_status


def _plan_text(status_lines: str, *, body: str = "# Plan\n") -> str:
    return f"---\ntitle: Plan\n{status_lines}\ndepends_on: []\n---\n\n{body}"


def _archived_plan(root: Path, status_lines: str = "status: PENDING") -> Path:
    archive = get_cortex_path(root, CortexResourceType.PLANS_ARCHIVE) / "Other"
    archive.mkdir(parents=True)
    path = archive / "legacy.md"
    _ = path.write_text(_plan_text(status_lines), encoding="utf-8")
    return path


async def _repair(root: Path, *, status: str = "DONE") -> dict[str, object]:
    with patch(
        "cortex.tools.plans.status_repair.get_or_resolve_project_root",
        new_callable=AsyncMock,
        return_value=str(root),
    ):
        raw = await repair_archived_plan_status(
            slug="legacy", requested_status=status, include_archive=True, ctx=None
        )
    # BELIEF: The tested public tool always returns a JSON object.
    return cast(dict[str, object], json.loads(raw))


@pytest.mark.asyncio
async def test_repair_pending_then_done_retry_is_idempotent(tmp_path: Path) -> None:
    # Arrange
    path = _archived_plan(tmp_path)

    # Act
    first = await _repair(tmp_path)
    second = await _repair(tmp_path)

    # Assert
    assert first["status"] == "success"
    assert first["changed"] is True
    assert first["previous_status"] == "PENDING"
    assert first["relative_path"] == ".cortex/plans/archive/Other/legacy.md"
    assert second["changed"] is False
    assert path.read_text(encoding="utf-8").count("status: DONE") == 1


@pytest.mark.asyncio
async def test_repair_canonicalizes_identical_eligible_duplicates(
    tmp_path: Path,
) -> None:
    # Arrange
    path = _archived_plan(tmp_path, "status: READY\nstatus: READY")

    # Act
    result = await _repair(tmp_path)

    # Assert
    assert result["status"] == "success"
    assert result["previous_status"] == "READY"
    assert path.read_text(encoding="utf-8").count("status:") == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status_lines",
    [
        "status: BLOCKED",
        "status: IN_PROGRESS",
        "status: DECLINED",
        "status: CUSTOM",
        "status: PENDING\nstatus: READY",
        "status:",
    ],
)
async def test_repair_preserves_ineligible_or_conflicting_statuses(
    tmp_path: Path, status_lines: str
) -> None:
    # Arrange
    path = _archived_plan(tmp_path, status_lines)
    before = path.read_text(encoding="utf-8")

    # Act
    result = await _repair(tmp_path)

    # Assert
    assert result["status"] == "error"
    assert "not eligible" in str(result["error"])
    assert path.read_text(encoding="utf-8") == before


@pytest.mark.asyncio
async def test_repair_rejects_active_target(tmp_path: Path) -> None:
    # Arrange
    plans = get_cortex_path(tmp_path, CortexResourceType.PLANS)
    plans.mkdir(parents=True)
    path = plans / "legacy.md"
    _ = path.write_text(_plan_text("status: PENDING"), encoding="utf-8")

    # Act
    result = await _repair(tmp_path)

    # Assert
    assert result["status"] == "error"
    assert "restricted to archived" in str(result["error"])
    assert "status: PENDING" in path.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_repair_rejects_real_and_symlink_duplicate(tmp_path: Path) -> None:
    # Arrange
    plans = get_cortex_path(tmp_path, CortexResourceType.PLANS)
    plans.mkdir(parents=True)
    real = plans / "legacy.md"
    _ = real.write_text(_plan_text("status: PENDING"), encoding="utf-8")
    archive = get_cortex_path(tmp_path, CortexResourceType.PLANS_ARCHIVE)
    archive.mkdir(parents=True)
    (archive / "legacy.md").symlink_to(real)

    # Act
    result = await _repair(tmp_path)

    # Assert
    assert result["status"] == "error"
    assert "Ambiguous plan slug" in str(result["error"])
    assert "status: PENDING" in real.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_repair_rejects_draft_and_malformed_frontmatter(tmp_path: Path) -> None:
    # Arrange
    draft = _archived_plan(tmp_path)
    _ = draft.write_text(
        _plan_text("status: PENDING") + "\n<!-- CORTEX_STEP_PLAN_STATE\n{}\n-->\n",
        encoding="utf-8",
    )

    # Act
    draft_result = await _repair(tmp_path)
    _ = draft.write_text(
        "---\ntitle: Broken\n\n**Status**: PENDING.\n", encoding="utf-8"
    )
    malformed_result = await _repair(tmp_path)

    # Assert
    assert draft_result["status"] == "error"
    assert malformed_result["status"] == "error"
    assert "could not produce" in str(malformed_result["error"])


@pytest.mark.asyncio
async def test_repair_detects_deletion_during_atomic_write(tmp_path: Path) -> None:
    # Arrange
    path = _archived_plan(tmp_path)
    original = FileSystemManager.check_file_conflict

    async def delete_then_check(
        manager: FileSystemManager, target: Path, expected_hash: str | None
    ) -> None:
        target.unlink()
        await original(manager, target, expected_hash)

    # Act
    with patch.object(FileSystemManager, "check_file_conflict", new=delete_then_check):
        result = await _repair(tmp_path)

    # Assert
    assert result["status"] == "error"
    assert "modified externally" in str(result["error"])
    assert not path.exists()


@pytest.mark.asyncio
async def test_repair_reports_completion_lock_denial(tmp_path: Path) -> None:
    # Arrange
    _ = _archived_plan(tmp_path)

    async def deny_lock(manager: FileSystemManager, path: Path) -> None:
        raise FileLockTimeoutError(path.name, 1)

    # Act
    with patch.object(FileSystemManager, "acquire_lock", new=deny_lock):
        result = await _repair(tmp_path)

    # Assert
    assert result["status"] == "error"
    assert "Could not acquire lock" in str(result["error"])
