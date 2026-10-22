"""Registration identity must not consume explanatory references or stale reads."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from cortex.core.artifact_graph import compute_artifact_graph
from cortex.core.exceptions import FileLockTimeoutError
from cortex.core.file_system import FileSystemManager
from cortex.core.models import PlanStatus
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.plans.completion_archive import (
    archive_plan_file,
    remove_roadmap_entry_for_plan,
)
from cortex.tools.plans.entries_removal import execute_roadmap_removal
from cortex.tools.plans.register import register_plan_in_roadmap
from cortex.tools.plans.register_helpers import register_plan_entry
from cortex.tools.plans.register_models import RegisterPlanResult

PLAN_REF = ".cortex/plans/diagnostic.md"
REGISTRATION = f"- **Diagnostic** - BLOCKED - Await repair. Plan: {PLAN_REF}"
REFERENCE = (
    f"- **Planning clarification.** Developed by `{PLAN_REF}`, "
    "with prerequisite `.cortex/plans/repair.md`; no work launched."
)


def test_registration_preserves_earlier_explanatory_reference() -> None:
    # Arrange: the incident's explanatory bullet precedes the real registration.
    original = (
        f"## Pending plans (from .cortex/plans)\n\n{REFERENCE}\n" f"{REGISTRATION}\n"
    )
    # Act
    updated, line = register_plan_entry(
        original,
        "Diagnostic",
        "Revised.",
        "BLOCKED",
        "pending",
        plan_relative_path=PLAN_REF,
    )
    # Assert
    assert REFERENCE in updated
    assert updated.count("- **Diagnostic**") == 1
    assert updated.splitlines()[line - 1 if line else 0].startswith("- **Diagnostic**")


@pytest.mark.parametrize("reference", [REFERENCE, f"See Plan: {PLAN_REF}"])
def test_reference_alone_does_not_count_as_registration(reference: str) -> None:
    # Arrange
    original = f"## Pending plans (from .cortex/plans)\n\n{reference}\n"
    # Act
    updated, _ = register_plan_entry(
        original,
        "Diagnostic",
        "Await repair.",
        "BLOCKED",
        "pending",
        plan_relative_path=PLAN_REF,
    )
    # Assert
    assert reference in updated
    assert REGISTRATION in updated


def test_registration_stays_out_of_unrecognized_sections() -> None:
    # Arrange
    original = (
        "## Pending plans (from .cortex/plans)\n\n- Earlier\n\n"
        "### Research\n\n- Research notes\n\n"
        "## Operator Queue\n\n- Operator notes\n\n## Future Enhancements\n"
    )
    # Act
    updated, _ = register_plan_entry(
        original,
        "Diagnostic",
        "Await repair.",
        "BLOCKED",
        "pending",
        plan_relative_path=PLAN_REF,
    )
    # Assert
    assert updated == original.replace("- Earlier\n", f"- Earlier\n{REGISTRATION}\n")


@pytest.mark.parametrize(
    "entry",
    [
        f"- Plan: {PLAN_REF}",
        "- [ ] Diagnostic (`plans/diagnostic.md`)",
        REGISTRATION,
    ],
)
def test_recognized_registration_forms_update_in_place(entry: str) -> None:
    # Arrange
    original = f"## Pending plans (from .cortex/plans)\n\n{entry}\n"
    # Act
    updated, line = register_plan_entry(
        original,
        "Diagnostic",
        "Await repair.",
        "BLOCKED",
        "pending",
        plan_relative_path=PLAN_REF,
    )
    # Assert
    assert updated == f"## Pending plans (from .cortex/plans)\n\n{REGISTRATION}\n"
    assert line == 3


@pytest.fixture
def blocked_workspace(tmp_path: Path) -> Path:
    plans = get_cortex_path(tmp_path, CortexResourceType.PLANS)
    memory = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
    plans.mkdir(parents=True)
    memory.mkdir(parents=True)
    _ = (plans / "repair.md").write_text(
        "---\ntitle: Repair\nstatus: IN_PROGRESS\nexecution: operator\n---\n"
    )
    _ = (plans / "diagnostic.md").write_text(
        "---\ntitle: Diagnostic\nstatus: BLOCKED\nexecution: agent\n"
        + "depends_on: [repair]\n---\n"
    )
    roadmap = memory / "roadmap.md"
    _ = roadmap.write_text(
        f"# Roadmap\n\n## Pending plans (from .cortex/plans)\n\n{REFERENCE}\n\n"
        + f"## Deferred Backup Work\n\n{REGISTRATION}\n"
    )
    return roadmap


async def register_diagnostic(root: Path) -> RegisterPlanResult:
    with patch(
        "cortex.tools.plans.register.resolve_project_root_async",
        new_callable=AsyncMock,
        return_value=root,
    ):
        raw = await register_plan_in_roadmap(
            plan_title="Diagnostic",
            description="Await repair.",
            status="PENDING",
            section="pending",
            plan_relative_path=PLAN_REF,
        )
    return RegisterPlanResult.model_validate_json(raw)


@pytest.mark.asyncio
async def test_pending_retry_keeps_dependency_blocked_registration(
    tmp_path: Path,
    blocked_workspace: Path,
) -> None:
    # Arrange
    before = blocked_workspace.read_bytes()
    plans = get_cortex_path(tmp_path, CortexResourceType.PLANS)
    diagnostic = (plans / "diagnostic.md").read_bytes()
    # Act
    result = await register_diagnostic(tmp_path)
    replay = await register_diagnostic(tmp_path)
    # Assert
    assert result.status == replay.status == "success"
    assert blocked_workspace.read_bytes() == before
    assert (plans / "diagnostic.md").read_bytes() == diagnostic
    assert result.line_inserted == replay.line_inserted == 9
    graph = compute_artifact_graph(plans)
    assert graph.nodes["diagnostic"].status == PlanStatus.BLOCKED
    assert graph.nodes["diagnostic"].blocked_by == ["repair"]


@pytest.mark.asyncio
async def test_registration_rejects_concurrent_roadmap_edit(
    tmp_path: Path,
    blocked_workspace: Path,
) -> None:
    # Arrange: a deterministic interleaving after merge and before disk write.
    concurrent = blocked_workspace.read_text() + "\n- Concurrent operator note\n"

    async def edit_during_lock_check(*_args: object) -> None:
        _ = blocked_workspace.write_text(concurrent)

    # Act
    with patch(
        "cortex.tools.plans.entries_io._roadmap_verify_write_lock",
        side_effect=edit_during_lock_check,
    ):
        result = await register_diagnostic(tmp_path)
    # Assert
    assert result.status == "error"
    assert result.error is not None and "changed" in result.error.lower()
    assert blocked_workspace.read_text() == concurrent


def test_global_identity_does_not_create_requested_missing_section() -> None:
    # Arrange
    original = f"## Deferred Backup Work\n\n{REGISTRATION}\n"
    # Act
    updated, line = register_plan_entry(
        original,
        "Diagnostic",
        "Await repair.",
        "BLOCKED",
        "pending",
        plan_relative_path=PLAN_REF,
    )
    # Assert
    assert updated == original
    assert line == 3


def test_duplicate_global_registrations_are_rejected_without_deduplication() -> None:
    # Arrange
    original = (
        f"## Pending plans (from .cortex/plans)\n\n{REGISTRATION}\n"
        f"## Deferred Backup Work\n\n- Plan: {PLAN_REF}\n"
    )
    # Act / Assert
    with pytest.raises(ValueError, match="Multiple canonical"):
        _ = register_plan_entry(
            original,
            "Diagnostic",
            "Revised.",
            "PENDING",
            "pending",
            plan_relative_path=PLAN_REF,
        )


def test_explicit_identity_is_not_replaced_by_description_reference() -> None:
    # Arrange
    other = "- **Repair** - PENDING - Work. Plan: .cortex/plans/repair.md"
    original = f"## Deferred Backup Work\n\n{other}\n{REGISTRATION}\n"
    description = "See `.cortex/plans/repair.md` and Plan: .cortex/plans/other.md"
    # Act
    updated, line = register_plan_entry(
        original,
        "Diagnostic",
        description,
        "BLOCKED",
        "pending",
        plan_relative_path=PLAN_REF,
    )
    # Assert
    assert other in updated
    assert line == 4
    assert updated.splitlines()[3].endswith(f"Plan: {PLAN_REF}")
    assert "## Pending plans" not in updated


@pytest.mark.asyncio
async def test_stale_merge_before_writer_read_is_rejected(
    tmp_path: Path,
    blocked_workspace: Path,
) -> None:
    # Arrange: competing bytes arrive immediately after the merge's only read.
    from cortex.tools.plans.entries_io import read_roadmap_file

    concurrent = blocked_workspace.read_text() + "\n- Competing note\n"

    def read_then_edit(path: Path) -> tuple[str | None, str | None]:
        snapshot = read_roadmap_file(path)
        _ = path.write_text(concurrent)
        return snapshot

    # Act
    with patch(
        "cortex.tools.plans.register.read_roadmap_file", side_effect=read_then_edit
    ) as read:
        result = await register_diagnostic(tmp_path)
    # Assert
    assert result.status == "error"
    assert result.error is not None and "changed" in result.error.lower()
    assert read.call_count == 1
    assert blocked_workspace.read_text() == concurrent


@pytest.mark.asyncio
async def test_merge_read_waits_for_existing_roadmap_lock_holder(
    tmp_path: Path,
    blocked_workspace: Path,
) -> None:
    # Arrange
    concurrent = blocked_workspace.read_text() + "\n- Lock holder note\n"
    acquire = FileSystemManager.acquire_lock

    async def acquire_then_edit(manager: FileSystemManager, path: Path) -> None:
        await acquire(manager, path)
        if path == blocked_workspace.with_suffix(".md.lock"):
            _ = blocked_workspace.write_text(concurrent)

    # Act
    with patch.object(FileSystemManager, "acquire_lock", new=acquire_then_edit):
        result = await register_diagnostic(tmp_path)
    # Assert
    assert result.status == "success"
    assert blocked_workspace.read_text() == concurrent


@pytest.mark.asyncio
async def test_duplicate_tool_registration_preserves_all_artifacts(
    tmp_path: Path,
    blocked_workspace: Path,
) -> None:
    # Arrange
    original = blocked_workspace.read_text() + f"\n- Plan: {PLAN_REF}\n"
    _ = blocked_workspace.write_text(original)
    plan = tmp_path / PLAN_REF
    before = plan.read_bytes()
    # Act
    result = await register_diagnostic(tmp_path)
    # Assert
    assert result.status == "error"
    assert result.error is not None and "Multiple canonical" in result.error
    assert blocked_workspace.read_text() == original
    assert plan.read_bytes() == before


@pytest.mark.asyncio
async def test_lock_denial_does_not_release_another_writers_lock(
    tmp_path: Path,
    blocked_workspace: Path,
) -> None:
    # Arrange
    before = blocked_workspace.read_bytes()
    denied = AsyncMock(side_effect=FileLockTimeoutError("roadmap.md.lock", 1))
    released = AsyncMock()
    # Act
    with (
        patch.object(FileSystemManager, "acquire_lock", new=denied),
        patch.object(FileSystemManager, "release_lock", new=released),
    ):
        result = await register_diagnostic(tmp_path)
    # Assert
    assert result.status == "error"
    assert blocked_workspace.read_bytes() == before
    released.assert_not_awaited()


@pytest.mark.asyncio
async def test_exact_crlf_replay_does_not_replace_files_or_emit_wal(
    tmp_path: Path,
    blocked_workspace: Path,
) -> None:
    # Arrange
    plan = tmp_path / PLAN_REF
    _ = blocked_workspace.write_bytes(
        blocked_workspace.read_bytes().replace(b"\n", b"\r\n")
    )
    _ = plan.write_bytes(plan.read_bytes().replace(b"\n", b"\r\n"))
    roadmap_before, plan_before = blocked_workspace.read_bytes(), plan.read_bytes()
    # Act
    with (
        patch.object(Path, "replace", autospec=True) as replace,
        patch("cortex.tools.plans.entries_io._wal_roadmap_maybe") as wal,
    ):
        first = await register_diagnostic(tmp_path)
        replay = await register_diagnostic(tmp_path)
    # Assert
    assert first.status == replay.status == "success"
    assert blocked_workspace.read_bytes() == roadmap_before
    assert plan.read_bytes() == plan_before
    replace.assert_not_called()
    wal.assert_not_called()


@pytest.mark.asyncio
async def test_line_ending_only_concurrent_edit_is_not_hidden(
    tmp_path: Path,
    blocked_workspace: Path,
) -> None:
    # Arrange
    concurrent = blocked_workspace.read_bytes().replace(b"\n", b"\r\n")

    async def change_line_endings(*_args: object) -> None:
        _ = blocked_workspace.write_bytes(concurrent)

    # Act
    with patch(
        "cortex.tools.plans.entries_io._roadmap_verify_write_lock",
        side_effect=change_line_endings,
    ):
        result = await register_diagnostic(tmp_path)
    # Assert
    assert result.status == "error"
    assert blocked_workspace.read_bytes() == concurrent


@pytest.mark.parametrize("separator", ["—", "–"])
def test_typographic_status_row_is_updated_in_its_unknown_section(
    separator: str,
) -> None:
    # Arrange
    canonical = REGISTRATION.replace(" - ", f" {separator} ")
    original = (
        f"## Pending plans (from .cortex/plans)\n\n{REFERENCE}\n\n"
        f"## Deferred Backup Work\n\n{canonical}\n"
    )
    # Act
    updated, line = register_plan_entry(
        original,
        "Diagnostic",
        "Revised.",
        "BLOCKED",
        "pending",
        plan_relative_path=PLAN_REF,
    )
    # Assert
    assert updated == original.replace(
        canonical, REGISTRATION.replace("Await repair.", "Revised.")
    )
    assert line == 7
    assert updated.count("- **Diagnostic**") == 1
    assert REFERENCE in updated


@pytest.mark.parametrize("fence", ["```", "~~~"])
@pytest.mark.parametrize("live_registration", [False, True])
def test_fenced_examples_never_count_as_live_registrations(
    fence: str,
    live_registration: bool,
) -> None:
    # Arrange
    example = f"{fence}markdown\n- Plan: {PLAN_REF}\n{fence}\n"
    live = f"## Deferred Backup Work\n\n{REGISTRATION}\n\n" if live_registration else ""
    original = (
        "## Pending plans (from .cortex/plans)\n\n"
        f"{live}## Registration examples\n\n{example}"
    )
    # Act
    updated, _ = register_plan_entry(
        original,
        "Diagnostic",
        "Revised.",
        "BLOCKED",
        "pending",
        plan_relative_path=PLAN_REF,
    )
    # Assert
    assert example in updated
    assert updated.count("- **Diagnostic**") == 1
    assert " - BLOCKED - Revised." in updated


@pytest.mark.parametrize(
    "heading",
    [
        "### Investigation Plans (Archive / Reference)",
        "## Recent Findings",
        "## Completed Milestones",
        "### Planned Phases",
    ],
)
def test_archive_reference_rows_are_not_live_identity_matches(heading: str) -> None:
    # Arrange
    history = (
        f"{heading}\n\n"
        f"- Plan: {PLAN_REF}\n\n#### Historical detail\n\n{REGISTRATION}\n"
    )
    original = f"## Pending plans (from .cortex/plans)\n\n{history}\n### Improvements\n"
    # Act
    updated, _ = register_plan_entry(
        original,
        "Diagnostic",
        "Revised.",
        "BLOCKED",
        "pending",
        plan_relative_path=PLAN_REF,
    )
    # Assert
    assert history in updated
    assert updated.startswith(
        "## Pending plans (from .cortex/plans)\n- **Diagnostic** - BLOCKED - Revised."
    )


@pytest.mark.asyncio
async def test_removal_guard_uses_canonical_plan_not_completed_description_reference(
    tmp_path: Path,
    blocked_workspace: Path,
) -> None:
    # Arrange
    repair = tmp_path / ".cortex/plans/repair.md"
    _ = repair.write_text("**Status:** COMPLETE\n")
    description = "Earlier work. Plan: .cortex/plans/repair.md"
    updated, _ = register_plan_entry(
        blocked_workspace.read_text(),
        "Diagnostic",
        description,
        "BLOCKED",
        "pending",
        plan_relative_path=PLAN_REF,
    )
    _ = blocked_workspace.write_text(updated)
    before = blocked_workspace.read_bytes()
    # Act
    result = await execute_roadmap_removal(tmp_path, "**Diagnostic**")
    # Assert
    assert result.status == "error"
    assert result.error is not None and "not marked COMPLETE" in result.error
    assert blocked_workspace.read_bytes() == before
    assert description in blocked_workspace.read_text()


@pytest.mark.parametrize("live_registration", [False, True])
def test_nested_history_retains_outermost_exclusion_until_live_section(
    live_registration: bool,
) -> None:
    # Arrange
    history = (
        "## Completed Milestones\n\n### Planned Phases\n\n"
        f"### Phase details\n\n{REGISTRATION}\n"
    )
    live = REGISTRATION + "\n" if live_registration else ""
    original = f"{history}\n## Pending plans (from .cortex/plans)\n\n{live}"
    # Act
    updated, _ = register_plan_entry(
        original,
        "Diagnostic",
        "Revised.",
        "BLOCKED",
        "pending",
        plan_relative_path=PLAN_REF,
    )
    # Assert
    assert history in updated
    pending = updated.split("## Pending plans (from .cortex/plans)", maxsplit=1)[1]
    assert pending.count("- **Diagnostic**") == 1
    assert " - BLOCKED - Revised." in pending


def test_archiving_completed_reference_preserves_incomplete_canonical_registration(
    tmp_path: Path,
    blocked_workspace: Path,
) -> None:
    # Arrange
    repair = tmp_path / ".cortex/plans/repair.md"
    _ = repair.write_text(repair.read_text().replace("IN_PROGRESS", "DONE"))
    description = "Completed prerequisite. Plan: `plans/repair.md`"
    updated, _ = register_plan_entry(
        blocked_workspace.read_text(),
        "Diagnostic",
        description,
        "BLOCKED",
        "pending",
        plan_relative_path=PLAN_REF,
    )
    repair_row = "- **Repair** - DONE - Completed. Plan: `plans/repair.md`\n"
    _ = blocked_workspace.write_text(updated + repair_row)
    diagnostic = tmp_path / PLAN_REF
    diagnostic_before = diagnostic.read_bytes()
    # Act
    archived, error = archive_plan_file(tmp_path, "repair.md")
    # Assert
    assert error is None and archived is not None
    assert Path(archived).is_file() and not repair.exists()
    assert blocked_workspace.read_text() == updated
    assert description in updated and REFERENCE in updated
    assert diagnostic.read_bytes() == diagnostic_before


@pytest.mark.parametrize(
    "reference",
    [
        "- Planning clarification. See Plan: .cortex/plans/repair.md",
        "## References\n\n- Plan: `.cortex/plans/repair.md`",
        "```markdown\n- Plan: .cortex/plans/repair.md\n```",
        "~~~markdown\n- Plan: .cortex/plans/repair.md\n~~~",
        "## Completed Milestones\n\n- **Repair** - DONE - Plan: .cortex/plans/repair.md",
    ],
)
def test_archive_identity_fix_does_not_expand_removal_into_narrative_or_examples(
    reference: str,
) -> None:
    # Arrange
    canonical = "- **Repair** - DONE - Completed. Plan: `plans/repair.md`\n"
    original = reference + "\n" + canonical
    # Act
    updated = remove_roadmap_entry_for_plan(original, "repair.md")
    # Assert
    assert updated == reference + "\n"


def _pending_fenced_insertion(
    fence: str, position: str, has_live_bullet: bool, with_heading: bool
) -> tuple[str, str, str]:
    heading = "## Pending plans (from .cortex/plans)\n"
    example = (
        f"{fence}markdown\n"
        + (heading if with_heading else "")
        + f"- Example bullet\n{fence}\n"
    )
    live = "- Existing work"
    if not has_live_bullet:
        original = heading + "\n" + example
        expected = heading + REGISTRATION + "\n\n" + example
    elif position == "first":
        original = heading + "\n" + example + "\n" + live + "\n"
        expected = original.replace(live, REGISTRATION + "\n" + live)
    else:
        original = heading + "\n" + live + "\n\n" + example
        expected = original.replace(live, live + "\n" + REGISTRATION)
    return original, expected, example


@pytest.mark.parametrize("fence", ["```", "~~~"])
@pytest.mark.parametrize("position", ["first", "last"])
@pytest.mark.parametrize("has_live_bullet", [False, True])
@pytest.mark.parametrize("with_heading", [False, True])
def test_registration_inserts_outside_same_section_fenced_example(
    fence: str,
    position: str,
    has_live_bullet: bool,
    with_heading: bool,
) -> None:
    # Arrange: no intervening heading separates Pending from its fenced example.
    original, expected, example = _pending_fenced_insertion(
        fence, position, has_live_bullet, with_heading
    )
    # Act
    updated, line = register_plan_entry(
        original,
        "Diagnostic",
        "Await repair.",
        "BLOCKED",
        "pending",
        position=position,
        plan_relative_path=PLAN_REF,
    )
    replay, replay_line = register_plan_entry(
        updated,
        "Diagnostic",
        "Await repair.",
        "BLOCKED",
        "pending",
        position=position,
        plan_relative_path=PLAN_REF,
    )
    # Assert: exact placement, unchanged example bytes, and byte-identical retry.
    assert updated == expected
    assert example.encode("utf-8") in updated.encode("utf-8")
    assert replay.encode("utf-8") == updated.encode("utf-8")
    assert replay_line == line


@pytest.mark.asyncio
async def test_policy_refusal_preserves_canonical_registration_artifacts(
    tmp_path: Path, blocked_workspace: Path
) -> None:
    # Arrange: the requested description update must not cross an owner refusal.
    _ = blocked_workspace.write_text(
        blocked_workspace.read_text().replace("Await repair.", "Original.")
    )
    plan = tmp_path / PLAN_REF
    before = blocked_workspace.read_bytes(), plan.read_bytes()
    denied = AsyncMock(return_value=(False, "Roadmap belongs to another owner"))
    # Act
    with patch(
        "cortex.tools.files.lock_guard.verify_lock_for_file_operation", new=denied
    ):
        result = await register_diagnostic(tmp_path)
    # Assert
    assert result.status == "error"
    assert result.error is not None and "Lock verification failed" in result.error
    assert (blocked_workspace.read_bytes(), plan.read_bytes()) == before
