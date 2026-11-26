"""Public cancellation, archive inventory, and transaction recovery regressions."""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, patch

import pytest

from cortex.core.artifact_graph import compute_artifact_graph, resolve_upstream_plans
from cortex.core.canonical_project import sha256_bytes
from cortex.core.models import PlanStatus
from cortex.tools.plans import completion_transaction
from cortex.tools.plans.completion_transaction_io import completion_operations_root
from cortex.tools.plans.completion_transaction_models import CompletionOperationRecord
from cortex.tools.plans.plan import plan
from cortex.validation.roadmap_sync import validate_roadmap_sync

_PLAN = (
    b"\xef\xbb\xbf---\r\ntitle: Sample\r\nstatus: 'PENDING'  # former state\r\n"
    b"depends_on: [prerequisite]\r\n---\r\n\r\n"
    b"# Sample (retired by operator)\r\n\r\n"
    b"**Status**: Retired\r\n\r\n"
    b"[Prerequisite](prerequisite.md#decision)\r\n"
    b"[Roadmap](../memory-bank/roadmap.md)\r\n"
)
_ROADMAP = (
    b"# Roadmap\r\n\r\n## Pending plans (from .cortex/plans)\r\n\r\n"
    b"- **Sample** - PENDING - Original work. Plan: .cortex/plans/sample.md\r\n"
    b"- **Dependent** - PENDING - Plan: .cortex/plans/dependent.md\r\n"
    b"- **Prerequisite** - BLOCKED - Plan: .cortex/plans/prerequisite.md\r\n"
    b"\r\n## Historical Operator Decisions\r\n\r\n"
    b"- **Sample** - RETIRED - Original decision. Plan: `plans/sample.md`\r\n"
    b"- See [decision](../plans/sample.md#decision).\r\n"
)


@pytest.fixture
def root(tmp_path: Path) -> Iterator[Path]:
    """Bind every plan handler to one isolated fixture without a checkout."""
    root_path = tmp_path.resolve()
    plans = root_path / ".cortex/plans"
    plans.mkdir(parents=True)
    memory = root_path / ".cortex/memory-bank"
    memory.mkdir()
    _ = (plans / "sample.md").write_bytes(_PLAN)
    _ = (plans / "prerequisite.md").write_text(
        "---\nstatus: BLOCKED\n---\n\n# Prerequisite\n", encoding="utf-8"
    )
    _ = (plans / "dependent.md").write_text(
        "---\nstatus: PENDING\ndepends_on: [sample]\n---\n\n# Dependent\n",
        encoding="utf-8",
    )
    _ = (memory / "roadmap.md").write_bytes(_ROADMAP)
    with (
        patch(
            "cortex.core.project_root_resolver.resolve_project_root_async",
            new=AsyncMock(return_value=root_path),
        ),
        patch(
            "cortex.tools.plans.crud.resolve_project_root_async",
            new=AsyncMock(return_value=root_path),
        ),
        patch(
            "cortex.tools.plans.completion.resolve_project_root_async",
            new=AsyncMock(return_value=root_path),
        ),
        patch("cortex.core.mcp_stability_usage.get_current_managers", return_value={}),
    ):
        yield root_path


async def _cancel(data: bytes = _PLAN, /, **overrides: object) -> dict[str, object]:
    payload = {
        "expected_sha256": sha256_bytes(data),
        "reason": "Operator retired the work",
        "dry_run": False,
        **overrides,
    }
    return cast(
        dict[str, object],
        json.loads(
            await plan(
                operation="archive_cancelled",
                slug="sample",
                content=json.dumps(payload),
            )
        ),
    )


@pytest.mark.asyncio
async def test_preview_is_read_only(root: Path) -> None:
    before = {path: path.read_bytes() for path in root.rglob("*.md")}
    paths = set(root.rglob("*"))

    result = await _cancel(dry_run=True)

    assert result["status"] == "success", result
    assert result["dry_run"] is True
    assert result["plan_status"] == "CANCELLED"
    assert result["archive_path"] == str(
        root / ".cortex/plans/archive/Cancelled/sample.md"
    )
    assert set(root.rglob("*")) == paths
    assert all(path.read_bytes() == content for path, content in before.items())


@pytest.mark.asyncio
async def test_archive_preserves_body_links_and_history(root: Path) -> None:
    plans = root / ".cortex/plans"
    memory = root / ".cortex/memory-bank"
    with patch(
        "cortex.tools.plans.plan._append_plan_complete_log", new=AsyncMock()
    ) as log:
        result = await _cancel()
    assert result["status"] == "success", result
    log.assert_not_called()
    assert not (plans / "sample.md").exists()
    assert not (memory / "activeContext.md").exists()
    assert not (memory / "progress.md").exists()
    archived = plans / "archive/Cancelled/sample.md"
    assert archived.read_bytes() == (
        _PLAN.replace(b"'PENDING'", b"'CANCELLED'", 1)
        .replace(b"](prerequisite.md", b"](../../prerequisite.md")
        .replace(b"](../memory-bank", b"](../../../memory-bank")
    )
    roadmap = (memory / "roadmap.md").read_bytes()
    assert b"Original work" not in roadmap
    assert (
        b"**Sample** - RETIRED - Original decision. "
        + b"Plan: `plans/archive/Cancelled/sample.md`"
        in roadmap
    )
    assert b"[decision](../plans/archive/Cancelled/sample.md#decision)" in roadmap
    assert validate_roadmap_sync(root, roadmap.decode()).valid


@pytest.mark.asyncio
async def test_archived_inventory_and_dependencies(root: Path) -> None:
    plans = root / ".cortex/plans"
    assert (await _cancel())["status"] == "success"

    active = json.loads(await plan(operation="list"))
    history = json.loads(await plan(operation="list", include_archive=True))
    archived = json.loads(
        await plan(operation="get", slug="sample", response_format="metadata")
    )
    repair = json.loads(
        await plan(
            operation="repair_status",
            slug="sample",
            status="DONE",
            include_archive=True,
        )
    )
    public_graph = json.loads(await plan(operation="graph"))
    graph = compute_artifact_graph(plans)

    assert "sample" not in [row["slug"] for row in active["plans"]]
    assert any(row["slug"] == "sample" and row["archived"] for row in history["plans"])
    assert archived["plan_status"] == "CANCELLED"
    assert repair["status"] == "error"
    assert public_graph["cancelled"] == ["sample"]
    assert "sample" not in public_graph["done"]
    assert public_graph["blocked"]["dependent"] == ["sample"]
    assert graph.edges == [("dependent", "sample"), ("sample", "prerequisite")]
    assert graph.nodes["sample"].blocked_by == ["prerequisite"]
    assert resolve_upstream_plans("dependent", plans) == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "previous", ["READY", "IN_PROGRESS", "BLOCKED", "CANCELED", "RETIRED"]
)
async def test_supported_source_statuses(root: Path, previous: str) -> None:
    source = root / ".cortex/plans/sample.md"
    body = _PLAN.replace(b"'PENDING'", previous.encode(), 1)
    _ = source.write_bytes(body)

    result = await _cancel(body)

    assert result["status"] == "success", result
    assert result["plan_status"] == "CANCELLED"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overrides",
    [{"expected_sha256": "0" * 64}, {"reason": " "}, {"dry_run": "false"}],
)
async def test_stale_or_invalid_request_leaves_files_untouched(
    root: Path, overrides: dict[str, object]
) -> None:
    result = await _cancel(**overrides)

    assert result["status"] == "error", result
    assert (root / ".cortex/plans/sample.md").read_bytes() == _PLAN
    assert (root / ".cortex/memory-bank/roadmap.md").read_bytes() == _ROADMAP


@pytest.mark.asyncio
@pytest.mark.parametrize("location", ["archive/Cancelled", "archive/Other", "nested"])
async def test_collision_or_duplicate_is_nonmutating(root: Path, location: str) -> None:
    duplicate = root / ".cortex/plans" / location / "sample.md"
    duplicate.parent.mkdir(parents=True)
    _ = duplicate.write_bytes(b"# Different plan\n")

    result = await _cancel()

    assert result["status"] == "error", result
    assert (root / ".cortex/plans/sample.md").read_bytes() == _PLAN
    assert duplicate.read_bytes() == b"# Different plan\n"
    assert (root / ".cortex/memory-bank/roadmap.md").read_bytes() == _ROADMAP


@pytest.mark.asyncio
async def test_exact_retry_succeeds_and_changed_intent_is_rejected(root: Path) -> None:
    first = await _cancel()
    assert first["status"] == "success", first
    roadmap = root / ".cortex/memory-bank/roadmap.md"
    _ = roadmap.write_bytes(roadmap.read_bytes() + b"\r\nUnrelated edit.\r\n")

    retry = await _cancel()
    changed = await _cancel(reason="Another reason")

    assert retry["status"] == "success", retry
    assert retry["idempotent_replay"] is True
    assert retry["operation_id"] == first["operation_id"]
    assert changed["status"] == "error"
    assert roadmap.read_bytes().endswith(b"Unrelated edit.\r\n")


@pytest.mark.asyncio
async def test_interrupted_hardlink_move_recovers_on_identical_retry(
    root: Path,
) -> None:
    class Interrupted(BaseException):
        """Model loss of the process between creating the archive link and unlinking."""

    def interrupt(project: Path, record: CompletionOperationRecord) -> None:
        assert record.archive_source and record.archive_destination
        source = project / record.archive_source
        destination = project / record.archive_destination
        destination.parent.mkdir(parents=True)
        destination.hardlink_to(source)
        raise Interrupted

    with patch.object(completion_transaction, "_archive", new=interrupt):
        with pytest.raises(Interrupted):
            _ = await _cancel()
    records = completion_operations_root(root)
    assert len(list(records.glob("*.json"))) == 1

    result = await _cancel()

    assert result["status"] == "success", result
    assert result["idempotent_replay"] is False
    assert not (root / ".cortex/plans/sample.md").exists()


@pytest.mark.asyncio
async def test_late_archive_collision_restores_owned_files(root: Path) -> None:
    destination = root / ".cortex/plans/archive/Cancelled/sample.md"
    hardlink = Path.hardlink_to

    def competing_archive(target: Path, source: Path) -> None:
        if target == destination:
            _ = destination.write_bytes(b"# Competing archival record\n")
        hardlink(target, source)

    with patch.object(Path, "hardlink_to", new=competing_archive):
        result = await _cancel()

    assert result["status"] == "error"
    assert result["recovery_required"] is False
    assert destination.read_bytes() == b"# Competing archival record\n"
    assert (root / ".cortex/plans/sample.md").read_bytes() == _PLAN
    assert (root / ".cortex/memory-bank/roadmap.md").read_bytes() == _ROADMAP


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["CANCELLED", "CANCELED", "RETIRED"])
async def test_existing_cancellation_cannot_be_completed(
    root: Path, status: str
) -> None:
    source = root / ".cortex/plans/sample.md"
    content = (
        _PLAN.replace(b"'PENDING'", status.encode(), 1) + b"\r\nstatus: COMPLETE\r\n"
    )
    _ = source.write_bytes(content)
    legacy = source.with_name("legacy.md")
    _ = legacy.write_text("---\nstatus: COMPLETE\n---\n\n# Legacy\n", encoding="utf-8")

    completed = json.loads(
        await plan(
            operation="complete",
            plan_title="Sample",
            summary="Done",
            plan_file_name="sample.md",
        )
    )
    bulk = json.loads(await plan(operation="archive_completed"))

    assert completed["status"] == "error"
    assert bulk["archived"] == ["legacy.md"]
    assert source.read_bytes() == content
    assert not legacy.exists()
    graph = compute_artifact_graph(source.parent)
    assert graph.nodes["sample"].status == PlanStatus.CANCELLED
