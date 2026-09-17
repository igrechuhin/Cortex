"""Behavior tests for atomic, idempotent plan completion."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import BaseModel

from cortex.core.file_system import FileSystemManager
from cortex.core.models import OperationStatus, PlanStatus
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.plans.completion_transaction import run_completion_transaction
from cortex.tools.plans.completion_transaction_io import (
    cleanup_completed_records,
    completion_operations_root,
    persist_record,
    record_path,
)
from cortex.tools.plans.completion_transaction_models import (
    CompletionOperationRecord,
    CompletionPhase,
    CompletionRequest,
)
from cortex.tools.plans.completion_transaction_prepare import normalized_request
from cortex.tools.plans.register_artifact_graph import replace_plan_frontmatter_status


class CompletionFixture(BaseModel):
    """Paths and original content for one isolated completion scenario."""

    root: Path
    plan: Path
    roadmap: Path
    active: Path
    progress: Path
    plan_before: str
    roadmap_before: str
    active_before: str
    progress_before: str


def _seed_plan(root: Path) -> tuple[Path, str]:
    plans = get_cortex_path(root, CortexResourceType.PLANS)
    plans.mkdir(parents=True)
    plan = plans / "sample.md"
    before = "---\ntitle: Sample\nstatus: PENDING\nstatus: READY\n---\n\n# Sample\n"
    _ = plan.write_text(before, encoding="utf-8")
    return plan, before


def _seed_memory_files(
    root: Path, roadmap_marker: str, roadmap_reference: str, create_progress: bool
) -> tuple[Path, str, Path, str, Path, str]:
    memory = get_cortex_path(root, CortexResourceType.MEMORY_BANK)
    memory.mkdir(parents=True)
    roadmap = memory / "roadmap.md"
    roadmap_before = (
        "# Roadmap\n\n## Pending\n\n"
        f"{roadmap_marker} **Sample** - PENDING - Plan: .cortex/plans/"
        f"{roadmap_reference}\n"
        "- **Keep** - PENDING\n"
    )
    _ = roadmap.write_text(roadmap_before, encoding="utf-8")
    active = memory / "activeContext.md"
    active_before = "# Active\n\n## Completed Work (2026-09-08)\n\n"
    _ = active.write_text(active_before, encoding="utf-8")
    progress = memory / "progress.md"
    progress_before = "# Progress\n\n## 2026-09-08\n\n"
    if create_progress:
        _ = progress.write_text(progress_before, encoding="utf-8")
    return roadmap, roadmap_before, active, active_before, progress, progress_before


def seed_completion(
    tmp_path: Path,
    *,
    roadmap_marker: str = "-",
    roadmap_reference: str = "sample.md",
    create_progress: bool = True,
) -> CompletionFixture:
    root = tmp_path / "project"
    plan, plan_before = _seed_plan(root)
    roadmap, roadmap_before, active, active_before, progress, progress_before = (
        _seed_memory_files(root, roadmap_marker, roadmap_reference, create_progress)
    )
    return CompletionFixture(
        root=root,
        plan=plan,
        roadmap=roadmap,
        active=active,
        progress=progress,
        plan_before=plan_before,
        roadmap_before=roadmap_before,
        active_before=active_before,
        progress_before=progress_before,
    )


def completion_request(summary: str = "Finished safely.") -> CompletionRequest:
    return normalized_request(
        "Sample",
        summary,
        "2026-09-08",
        "**Sample** - COMPLETE. Finished safely.",
        "sample.md",
    )


def assert_original(fixture: CompletionFixture) -> None:
    assert fixture.plan.read_text(encoding="utf-8") == fixture.plan_before
    assert fixture.roadmap.read_text(encoding="utf-8") == fixture.roadmap_before
    assert fixture.active.read_text(encoding="utf-8") == fixture.active_before
    assert fixture.progress.read_text(encoding="utf-8") == fixture.progress_before


def test_frontmatter_status_is_canonical_and_idempotent() -> None:
    source = "---\ntitle: Sample\nstatus: PENDING\nstatus: READY\n---\n\nBody\n"

    first = replace_plan_frontmatter_status(source, PlanStatus.DONE)
    second = replace_plan_frontmatter_status(first, PlanStatus.DONE)

    assert first == second
    assert first.count("status:") == 1
    assert "status: DONE" in first


def test_legacy_plan_receives_done_frontmatter() -> None:
    result = replace_plan_frontmatter_status("# Legacy\n", PlanStatus.DONE)

    assert result.startswith("---\nstatus: DONE\n---\n")
    assert result.count("status:") == 1


@pytest.mark.asyncio
async def test_success_persists_done_and_archives_once(tmp_path: Path) -> None:
    fixture = seed_completion(tmp_path)

    result = await run_completion_transaction(fixture.root, completion_request())

    assert result.status == OperationStatus.SUCCESS
    assert not fixture.plan.exists()
    archived = (
        get_cortex_path(fixture.root, CortexResourceType.PLANS_ARCHIVE)
        / "Other"
        / "sample.md"
    )
    archived_text = archived.read_text(encoding="utf-8")
    assert archived_text.count("status:") == 1
    assert "status: DONE" in archived_text
    assert "Sample" not in fixture.roadmap.read_text(encoding="utf-8")
    assert fixture.active.read_text(encoding="utf-8").count("**Sample**") == 1
    assert fixture.progress.read_text(encoding="utf-8").count("**Sample**") == 1


@pytest.mark.asyncio
async def test_identical_retry_is_noop_without_duplicate_entries(
    tmp_path: Path,
) -> None:
    fixture = seed_completion(tmp_path)
    first = await run_completion_transaction(fixture.root, completion_request())
    before_active = fixture.active.read_text(encoding="utf-8")
    before_progress = fixture.progress.read_text(encoding="utf-8")

    second = await run_completion_transaction(fixture.root, completion_request())

    assert first.status == second.status == OperationStatus.SUCCESS
    assert second.idempotent_replay is True
    assert fixture.active.read_text(encoding="utf-8") == before_active
    assert fixture.progress.read_text(encoding="utf-8") == before_progress


@pytest.mark.asyncio
async def test_success_preserves_memory_bank_wal_history(tmp_path: Path) -> None:
    fixture = seed_completion(tmp_path)

    result = await run_completion_transaction(fixture.root, completion_request())

    wal = fixture.root / ".cortex" / "wal" / "write_log.jsonl"
    assert result.status == OperationStatus.SUCCESS
    assert wal.is_file()
    content = wal.read_text(encoding="utf-8")
    assert content.count('"status":"ok"') == 3


@pytest.mark.asyncio
async def test_conflicting_retry_is_rejected(tmp_path: Path) -> None:
    fixture = seed_completion(tmp_path)
    first = await run_completion_transaction(fixture.root, completion_request())

    second = await run_completion_transaction(
        fixture.root, completion_request("Different summary")
    )

    assert first.status == OperationStatus.SUCCESS
    assert second.status == OperationStatus.ERROR
    assert "Conflicting" in second.message


@pytest.mark.asyncio
async def test_missing_progress_is_prevalidated_without_payloads(
    tmp_path: Path,
) -> None:
    fixture = seed_completion(tmp_path, create_progress=False)

    result = await run_completion_transaction(fixture.root, completion_request())

    assert result.status == OperationStatus.ERROR
    assert fixture.plan.read_text(encoding="utf-8") == fixture.plan_before
    assert fixture.roadmap.read_text(encoding="utf-8") == fixture.roadmap_before
    operations = completion_operations_root(fixture.root)
    assert list(operations.glob("*.txt")) == []


@pytest.mark.asyncio
async def test_archive_collision_is_rejected_before_mutation(tmp_path: Path) -> None:
    fixture = seed_completion(tmp_path)
    destination = (
        get_cortex_path(fixture.root, CortexResourceType.PLANS_ARCHIVE)
        / "Other"
        / "sample.md"
    )
    destination.parent.mkdir(parents=True)
    _ = destination.write_text("unrelated", encoding="utf-8")

    result = await run_completion_transaction(fixture.root, completion_request())

    assert result.status == OperationStatus.ERROR
    assert destination.read_text(encoding="utf-8") == "unrelated"
    assert_original(fixture)


@pytest.mark.asyncio
async def test_mismatched_roadmap_reference_is_rejected(tmp_path: Path) -> None:
    fixture = seed_completion(tmp_path, roadmap_reference="other.md")

    result = await run_completion_transaction(fixture.root, completion_request())

    assert result.status == OperationStatus.ERROR
    assert_original(fixture)


@pytest.mark.asyncio
@pytest.mark.parametrize("marker", ["–", "—"])
async def test_typographic_roadmap_bullets_complete(
    tmp_path: Path, marker: str
) -> None:
    fixture = seed_completion(tmp_path, roadmap_marker=marker)

    result = await run_completion_transaction(fixture.root, completion_request())

    assert result.status == OperationStatus.SUCCESS


@pytest.mark.asyncio
async def test_completion_lock_denial_leaves_all_inputs_unchanged(
    tmp_path: Path,
) -> None:
    fixture = seed_completion(tmp_path)

    async def deny_lock(self: FileSystemManager, path: Path) -> None:
        raise OSError(f"lock denied: {path.name}")

    with patch.object(FileSystemManager, "acquire_lock", new=deny_lock):
        result = await run_completion_transaction(fixture.root, completion_request())

    assert result.status == OperationStatus.ERROR
    assert_original(fixture)


def test_terminal_operation_records_are_bounded(tmp_path: Path) -> None:
    operations = completion_operations_root(tmp_path)
    operations.mkdir(parents=True)
    for index in range(35):
        request = normalized_request(f"Plan {index}", "Done", "2026-09-08", None, None)
        op_id = f"{index:024d}"
        record = CompletionOperationRecord(
            operation_id=op_id,
            request_fingerprint=str(index),
            request=request,
            phase=(
                CompletionPhase.COMPLETED if index % 2 else CompletionPhase.ROLLED_BACK
            ),
            files=[],
            created_at=f"2026-09-08T00:00:{index:02d}+00:00",
            updated_at=f"2026-09-08T00:00:{index:02d}+00:00",
        )
        persist_record(record_path(operations, op_id), record)

    cleanup_completed_records(operations)

    assert len(list(operations.glob("*.json"))) == 32
