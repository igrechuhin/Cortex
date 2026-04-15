"""Integration: update_memory_bank mutations append WAL entries."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from cortex.core.constants import MemoryBankFile
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.plans.update_memory_bank import update_memory_bank


def _minimal_roadmap() -> str:
    return (
        "# Roadmap: MCP Memory Bank\n\n"
        "## Blockers (ASAP Priority)\n\n"
        "## Active Work (in progress)\n\n"
        "## Future Enhancements\n\n"
        "## Pending plans (from .cortex/plans)\n\n"
        "- **Existing** - PENDING - Existing entry.\n"
    )


@pytest.mark.asyncio
async def test_roadmap_add_writes_wal_entry(tmp_path: Path) -> None:
    mem = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
    mem.mkdir(parents=True)
    _ = (mem / MemoryBankFile.ROADMAP).write_text(_minimal_roadmap(), encoding="utf-8")

    with patch(
        "cortex.tools.plans.entries.resolve_project_root_async",
        new_callable=AsyncMock,
        return_value=tmp_path,
    ):
        raw = await update_memory_bank(
            operation="roadmap_add",
            section="pending",
            entry_text="- **WAL roadmap probe** - PENDING - Plan: .cortex/plans/wal-probe.md",
        )
    result = json.loads(raw)
    assert result.get("status") == "success"

    wal_log = tmp_path / ".cortex" / "wal" / "write_log.jsonl"
    assert wal_log.is_file()
    lines = [
        ln for ln in wal_log.read_text(encoding="utf-8").splitlines() if ln.strip()
    ]
    assert lines
    entry = json.loads(lines[-1])
    assert entry["operation"] == "roadmap_add"
    assert "memory-bank/roadmap.md" in entry["file"].replace("\\", "/")


@pytest.mark.asyncio
async def test_progress_append_writes_wal_entry(tmp_path: Path) -> None:
    mem = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
    mem.mkdir(parents=True)
    _ = (mem / MemoryBankFile.PROGRESS).write_text(
        "# Progress Log\n\n## 2026-04-15\n\n- **Old** - COMPLETE.\n",
        encoding="utf-8",
    )

    with patch(
        "cortex.tools.plans.completion.resolve_project_root_async",
        new_callable=AsyncMock,
        return_value=tmp_path,
    ):
        raw = await update_memory_bank(
            operation="progress_append",
            date_str="2026-04-15",
            entry_text="**Wal progress** - COMPLETE. Logged.",
        )
    result = json.loads(raw)
    assert result.get("status") == "success"

    wal_log = tmp_path / ".cortex" / "wal" / "write_log.jsonl"
    assert wal_log.is_file()
    lines = [
        ln for ln in wal_log.read_text(encoding="utf-8").splitlines() if ln.strip()
    ]
    assert lines
    entry = json.loads(lines[-1])
    assert entry["operation"] == "progress_add"
    assert "memory-bank/progress.md" in entry["file"].replace("\\", "/")
