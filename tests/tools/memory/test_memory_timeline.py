from __future__ import annotations

import json
from pathlib import Path

import pytest

from cortex.memory.temporal_store import (
    TemporalFact,
    TemporalFactCategory,
    TemporalMemoryStore,
)
from cortex.memory.timeline import MemoryTimelineInput, memory_timeline_handle
from cortex.tools.files.manage_file_helpers import (
    execute_file_operation,
    index_temporal_file,
)
from cortex.tools.files.operation_helpers import FileOperation
from cortex.tools.session import brief as session_brief


async def _invalidate_plan_x(root: Path) -> dict[str, object]:
    invalidate_payload = json.dumps(
        {
            "subject": "plan-x",
            "predicate": "status",
            "object": "PENDING",
            "ended": "2026-04-02",
        }
    )
    result = await execute_file_operation(
        root,
        "roadmap.md",
        FileOperation.INVALIDATE_FACT,
        invalidate_payload,
        False,
        None,
        None,
        None,
    )
    return json.loads(result)


def test_memory_timeline_returns_subject_facts(tmp_path: Path) -> None:
    root = tmp_path
    store = TemporalMemoryStore(root / ".cortex" / "temporal.db")
    store.add_fact(
        TemporalFact(
            category=TemporalFactCategory.STATUS,
            subject="fastmcp-v3-phase2",
            predicate="status",
            object="PENDING",
            valid_from="2026-04-01",
            source_file="roadmap.md",
            source_line=1,
        )
    )

    result = memory_timeline_handle(
        MemoryTimelineInput(subject="fastmcp-v3-phase2", as_of="2026-04-10"),
        root,
    )

    assert result.total == 1
    assert result.facts[0].subject == "fastmcp-v3-phase2"


def test_manage_file_write_indexes_temporal_facts(tmp_path: Path) -> None:
    root = tmp_path
    memory_bank = root / ".cortex" / "memory-bank"
    memory_bank.mkdir(parents=True)
    roadmap_file = memory_bank / "roadmap.md"
    roadmap_content = (
        "## Pending plans (from .cortex/plans)\n"
        "- **Temporal Memory** - PENDING - work. Plan: .cortex/plans/improve-temporal-memory.md\n"
    )
    _ = roadmap_file.write_text(roadmap_content, encoding="utf-8")
    index_temporal_file(root, roadmap_file, json.dumps({"status": "success"}))
    timeline = memory_timeline_handle(
        MemoryTimelineInput(subject="improve-temporal-memory"), root
    )
    assert timeline.total >= 1


@pytest.mark.asyncio
async def test_manage_file_invalidate_fact_operation(tmp_path: Path) -> None:
    root = tmp_path
    store = TemporalMemoryStore(root / ".cortex" / "temporal.db")
    store.add_fact(
        TemporalFact(
            category=TemporalFactCategory.STATUS,
            subject="plan-x",
            predicate="status",
            object="PENDING",
            valid_from="2026-04-01",
            source_file="roadmap.md",
            source_line=1,
        )
    )

    payload = await _invalidate_plan_x(root)

    assert payload["status"] == "success"
    assert payload["invalidated"] is True


@pytest.mark.asyncio
async def test_temporal_index_failure_does_not_raise() -> None:
    await session_brief.index_temporal_async(Path("/dev/null"))
