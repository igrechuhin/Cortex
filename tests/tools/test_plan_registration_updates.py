"""Registration updates preserve roadmap position, content, and failed writes."""

import asyncio
from functools import partial
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from cortex.core.artifact_graph import compute_artifact_graph
from cortex.core.file_system import FileSystemManager
from cortex.core.models import PlanStatus
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.plans.register import register_plan_in_roadmap
from cortex.tools.plans.register_artifact_graph import persist_registered_status
from cortex.tools.plans.register_helpers import register_plan_entry
from cortex.tools.plans.register_models import RegisterPlanResult


@pytest.fixture
def roadmap(tmp_path: Path) -> Path:
    memory = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
    plans = get_cortex_path(tmp_path, CortexResourceType.PLANS)
    memory.mkdir(parents=True)
    plans.mkdir(parents=True)
    _ = (plans / "existing.md").write_text(
        "---\ntitle: Existing\nstatus: PENDING\n---\n\n## Goal\nKeep state.\n"
    )
    path = memory / "roadmap.md"
    _ = path.write_text(
        "# Roadmap\n\n## Blockers (ASAP Priority)\n\n- Unrelated blocker\n\n"
        + "## Pending plans (from .cortex/plans)\n\n- Before\n"
        + "- **Existing** - PENDING - Original. Plan: .cortex/plans/existing.md\n"
        + "- After\n\n## Unrelated section\n\nKeep this text.\n"
    )
    return path


async def register(tmp_path: Path, description: str, status: str) -> RegisterPlanResult:
    with patch(
        "cortex.tools.plans.register.resolve_project_root_async",
        new_callable=AsyncMock,
        return_value=tmp_path,
    ):
        return await _invoke_registration(description, status)


async def _invoke_registration(description: str, status: str) -> RegisterPlanResult:
    raw = await register_plan_in_roadmap(
        plan_title="Existing",
        description=description,
        status=status,
        section="pending",
        plan_file_name="existing.md",
    )
    return RegisterPlanResult.model_validate_json(raw)


@pytest.mark.asyncio
async def test_update_then_replay_preserves_roadmap(
    tmp_path: Path, roadmap: Path
) -> None:
    # Arrange
    original = roadmap.read_text()
    expected = original.replace("PENDING - Original.", "IN PROGRESS - Revised.")
    # Act
    result = await register(tmp_path, "Revised.", "IN PROGRESS")
    replay = await register(tmp_path, "Revised.", "IN PROGRESS")
    # Assert
    assert result.status == "success"
    assert replay.status == "success"
    assert roadmap.read_text() == expected
    assert roadmap.read_text().count(".cortex/plans/existing.md") == 1
    plans = get_cortex_path(tmp_path, CortexResourceType.PLANS)
    assert "status: IN_PROGRESS" in (plans / "existing.md").read_text()
    assert (
        compute_artifact_graph(plans).nodes["existing"].status == PlanStatus.IN_PROGRESS
    )


@pytest.mark.asyncio
async def test_unchanged_registration_succeeds(tmp_path: Path, roadmap: Path) -> None:
    # Arrange
    original = roadmap.read_bytes()
    # Act
    result = await register(tmp_path, "Original.", "PENDING")
    # Assert
    assert result.status == "success"
    assert roadmap.read_bytes() == original


@pytest.mark.asyncio
async def test_failed_replacement_preserves_registration(
    tmp_path: Path,
    roadmap: Path,
) -> None:
    # Arrange
    original = roadmap.read_bytes()
    # Act
    with patch.object(Path, "replace", side_effect=OSError("replacement denied")):
        result = await register(tmp_path, "Revised.", "IN PROGRESS")
    # Assert
    assert result.status == "error"
    assert result.error is not None and "replacement denied" in result.error
    assert roadmap.read_bytes() == original
    assert sorted(path.name for path in roadmap.parent.iterdir()) == ["roadmap.md"]


@pytest.mark.asyncio
async def test_partial_write_failure_preserves_registration(
    tmp_path: Path,
    roadmap: Path,
) -> None:
    # Arrange
    original = roadmap.read_bytes()
    write_text = Path.write_text

    def fail_write(path: Path, content: str, encoding: str) -> None:
        _ = write_text(path, content[:10], encoding=encoding)
        raise OSError("disk full")

    # Act
    with patch.object(Path, "write_text", autospec=True, side_effect=fail_write):
        result = await register(tmp_path, "Revised.", "IN PROGRESS")
    # Assert
    assert result.status == "error"
    assert result.error is not None and "disk full" in result.error
    assert roadmap.read_bytes() == original


def test_pathless_replay_preserves_header() -> None:
    # Arrange
    original = "## Pending plans (from .cortex/plans)\n\n- **A** - PENDING - Work\n"
    # Act
    updated, line = register_plan_entry(original, "A", "Work", "PENDING", "pending")
    # Assert
    assert updated == original
    assert line == 3


def test_unknown_section_does_not_modify_roadmap() -> None:
    # Arrange
    original = "# Roadmap\n\n## Pending plans (from .cortex/plans)\n"
    # Act
    updated, line = register_plan_entry(original, "A", "Work", "PENDING", "unknown")
    # Assert
    assert updated == original
    assert line is None


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["READY", "IN_PROGRESS", "BLOCKED", "CUSTOM"])
async def test_default_retry_preserves_established_status_in_both_artifacts(
    tmp_path: Path,
    roadmap: Path,
    status: str,
) -> None:
    # Arrange
    plan = get_cortex_path(tmp_path, CortexResourceType.PLANS) / "existing.md"
    _ = plan.write_text(
        plan.read_text().replace("status: PENDING", f"status: {status}")
    )
    original_plan = plan.read_bytes()
    row_status = status.replace("_", " ")
    expected = roadmap.read_text().replace(
        "PENDING - Original.", f"{row_status} - Original."
    )
    # Act
    first = await register(tmp_path, "Original.", "PENDING")
    replay = await register(tmp_path, "Original.", "PENDING")
    # Assert
    assert first.status == replay.status == "success"
    assert roadmap.read_text() == expected
    assert plan.read_bytes() == original_plan


@pytest.mark.asyncio
async def test_partial_status_write_failure_rolls_back_owned_roadmap(
    tmp_path: Path,
    roadmap: Path,
) -> None:
    # Arrange
    plan = get_cortex_path(tmp_path, CortexResourceType.PLANS) / "existing.md"
    original_roadmap, original_plan = roadmap.read_bytes(), plan.read_bytes()
    write_text = Path.write_text

    def fail_status_write(path: Path, content: str, encoding: str) -> int:
        if path.name == plan.name and path.parent != plan.parent:
            _ = write_text(path, content[:10], encoding=encoding)
            raise OSError("status disk full")
        return write_text(path, content, encoding=encoding)

    # Act
    with patch.object(Path, "write_text", autospec=True, side_effect=fail_status_write):
        result = await register(tmp_path, "Revised.", "IN PROGRESS")
    # Assert
    assert result.status == "error"
    assert result.error is not None and "status disk full" in result.error
    assert roadmap.read_bytes() == original_roadmap
    assert plan.read_bytes() == original_plan
    assert sorted(path.name for path in plan.parent.iterdir()) == ["existing.md"]


@pytest.mark.asyncio
async def test_stale_plan_read_preserves_competing_plan_and_rolls_back_roadmap(
    tmp_path: Path,
    roadmap: Path,
) -> None:
    # Arrange
    plan = get_cortex_path(tmp_path, CortexResourceType.PLANS) / "existing.md"
    original_roadmap = roadmap.read_bytes()
    concurrent = plan.read_text() + "\nOperator clarification.\n"

    async def edit_plan(*_args: object) -> None:
        _ = plan.write_text(concurrent)

    # Act
    with patch(
        "cortex.tools.plans.entries_io._roadmap_verify_write_lock",
        side_effect=edit_plan,
    ):
        result = await register(tmp_path, "Revised.", "IN PROGRESS")
    # Assert
    assert result.status == "error"
    assert result.error is not None and "changed" in result.error.lower()
    assert roadmap.read_bytes() == original_roadmap
    assert plan.read_text() == concurrent


@pytest.mark.asyncio
async def test_status_failure_never_rolls_back_competing_roadmap_bytes(
    tmp_path: Path,
    roadmap: Path,
) -> None:
    # Arrange
    plan = get_cortex_path(tmp_path, CortexResourceType.PLANS) / "existing.md"
    original_plan = plan.read_bytes()
    concurrent = roadmap.read_text() + "\n- Operator retained work\n"

    async def fail_after_concurrent_edit(*_args: object) -> None:
        _ = roadmap.write_text(concurrent)
        raise OSError("status write denied")

    # Act
    with patch(
        "cortex.tools.plans.register_artifact_graph.persist_registered_status",
        side_effect=fail_after_concurrent_edit,
    ):
        result = await register(tmp_path, "Revised.", "IN PROGRESS")
    # Assert
    assert result.status == "error"
    assert result.error is not None and "rollback failed" in result.error
    assert roadmap.read_text() == concurrent
    assert plan.read_bytes() == original_plan


@pytest.mark.asyncio
async def test_conflicting_metadata_refuses_registration_without_mutation(
    tmp_path: Path,
    roadmap: Path,
) -> None:
    # Arrange
    plan = get_cortex_path(tmp_path, CortexResourceType.PLANS) / "existing.md"
    _ = plan.write_text(
        plan.read_text().replace("status: PENDING", "status: PENDING\nstatus: READY")
    )
    original_roadmap, original_plan = roadmap.read_bytes(), plan.read_bytes()
    # Act
    result = await register(tmp_path, "Revised.", "IN PROGRESS")
    # Assert
    assert result.status == "error"
    assert result.error is not None and "Conflicting" in result.error
    assert roadmap.read_bytes() == original_roadmap
    assert plan.read_bytes() == original_plan


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["IN_PROGRESS", "READY"])
async def test_unmet_dependency_does_not_downgrade_established_lifecycle(
    tmp_path: Path,
    roadmap: Path,
    status: str,
) -> None:
    # Arrange
    plans = get_cortex_path(tmp_path, CortexResourceType.PLANS)
    plan = plans / "existing.md"
    _ = plan.write_text(
        plan.read_text().replace(
            "status: PENDING", f"status: {status}\ndepends_on: [missing-repair]"
        )
    )
    before = plan.read_bytes()
    # Act
    first = await register(tmp_path, "Original.", "PENDING")
    replay = await register(tmp_path, "Original.", "PENDING")
    # Assert
    assert first.status == replay.status == "success"
    assert f" - {status.replace('_', ' ')} - " in roadmap.read_text()
    assert plan.read_bytes() == before
    graph = compute_artifact_graph(plans)
    assert graph.nodes["existing"].status.value == status
    assert graph.nodes["existing"].blocked_by == ["missing-repair"]


@pytest.mark.asyncio
async def test_explicit_progress_from_pending_cannot_override_dependency_block(
    tmp_path: Path,
    roadmap: Path,
) -> None:
    # Arrange
    plan = get_cortex_path(tmp_path, CortexResourceType.PLANS) / "existing.md"
    _ = plan.write_text(
        plan.read_text().replace(
            "status: PENDING", "status: PENDING\ndepends_on: [missing-repair]"
        )
    )
    # Act
    result = await register(tmp_path, "Revised.", "IN PROGRESS")
    # Assert
    assert result.status == "success"
    assert " - BLOCKED - Revised." in roadmap.read_text()
    assert "status: BLOCKED" in plan.read_text()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["DONE", "COMPLETED", "COMPLETE"])
async def test_completed_plan_cannot_be_registered_as_pending(
    tmp_path: Path,
    roadmap: Path,
    status: str,
) -> None:
    # Arrange
    plan = get_cortex_path(tmp_path, CortexResourceType.PLANS) / "existing.md"
    _ = plan.write_text(
        plan.read_text().replace("status: PENDING", f"status: {status}")
    )
    original_roadmap, original_plan = roadmap.read_bytes(), plan.read_bytes()
    # Act
    result = await register(tmp_path, "Revised.", "PENDING")
    # Assert
    assert result.status == "error"
    assert result.error is not None and "Completed plans" in result.error
    assert roadmap.read_bytes() == original_roadmap
    assert plan.read_bytes() == original_plan


@pytest.mark.asyncio
async def test_retry_waits_until_prior_registration_finishes_status_and_rollback(
    tmp_path: Path,
    roadmap: Path,
) -> None:
    # Arrange: A pauses after its row write; B must not consume that partial state.
    paused, retry_attempted, resume = asyncio.Event(), asyncio.Event(), asyncio.Event()
    observed_lock: list[bool] = []
    acquire = FileSystemManager.acquire_lock

    async def acquire_retry(manager: FileSystemManager, path: Path) -> None:
        if paused.is_set() and path == roadmap.with_suffix(".md.lock"):
            observed_lock.append(path.exists())
            retry_attempted.set()
        await acquire(manager, path)

    fail_first_status = partial(_fail_first_registration_status, paused, resume)

    # Act
    with (
        patch.object(FileSystemManager, "acquire_lock", new=acquire_retry),
        patch(
            "cortex.tools.plans.register_artifact_graph.persist_registered_status",
            new=fail_first_status,
        ),
        patch(
            "cortex.tools.plans.register.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=tmp_path,
        ),
    ):
        await _exercise_registration_retry(
            tmp_path, roadmap, paused, retry_attempted, resume, observed_lock
        )


async def _fail_first_registration_status(
    paused: asyncio.Event,
    resume: asyncio.Event,
    root: Path,
    path: Path,
    before: str,
    updated: str,
) -> None:
    if not paused.is_set():
        paused.set()
        _ = await resume.wait()
        raise OSError("first registration status failure")
    await persist_registered_status(root, path, before, updated)


async def _exercise_registration_retry(
    root: Path,
    roadmap: Path,
    paused: asyncio.Event,
    retry_attempted: asyncio.Event,
    resume: asyncio.Event,
    observed_lock: list[bool],
) -> None:
    first = asyncio.create_task(_invoke_registration("Revised.", "IN PROGRESS"))
    _ = await asyncio.wait_for(paused.wait(), timeout=2)
    retry = asyncio.create_task(_invoke_registration("Revised.", "IN PROGRESS"))
    _ = await asyncio.wait_for(retry_attempted.wait(), timeout=2)
    finished_early = retry.done()
    resume.set()
    failed, succeeded = await asyncio.gather(first, retry)
    # A rolls back before B merges; A cannot undo B's successful retry.
    assert observed_lock == [True]
    assert not finished_early
    assert failed.status == "error" and succeeded.status == "success"
    assert " - IN PROGRESS - Revised." in roadmap.read_text()
    plan = get_cortex_path(root, CortexResourceType.PLANS) / "existing.md"
    assert "status: IN_PROGRESS" in plan.read_text()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["COMPLETED (2026-10-20)", "COMPLETE (26-10-20)"])
async def test_requested_dated_completion_alias_is_rejected_before_mutation(
    tmp_path: Path,
    roadmap: Path,
    status: str,
) -> None:
    # Arrange
    plan = get_cortex_path(tmp_path, CortexResourceType.PLANS) / "existing.md"
    original_roadmap, original_plan = roadmap.read_bytes(), plan.read_bytes()
    # Act
    result = await register(tmp_path, "Revised.", status)
    # Assert
    assert result.status == "error"
    assert roadmap.read_bytes() == original_roadmap
    assert plan.read_bytes() == original_plan
