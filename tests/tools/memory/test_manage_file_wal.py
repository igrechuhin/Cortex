"""Integration tests: manage_file writes emit WAL entries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, patch

import pytest

from cortex.tools.files.operations import manage_file
from tests.helpers.path_helpers import ensure_test_cortex_structure


def _parse(result: object) -> dict[str, object]:
    if isinstance(result, dict):
        return cast(dict[str, object], result)
    return cast(dict[str, object], json.loads(str(result)))


@pytest.mark.asyncio
async def test_manage_file_write_creates_wal_line(tmp_path: Path) -> None:
    memory_bank_dir = ensure_test_cortex_structure(tmp_path)
    _ = (memory_bank_dir / "projectBrief.md").write_text("# Brief\n", encoding="utf-8")

    with (
        patch(
            "cortex.core.project_root_resolver.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=tmp_path,
        ),
        patch(
            "cortex.tools.files.manage_file_helpers.resolve_schema_validator",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        out = await manage_file(
            operation="write",
            file_name="projectBrief.md",
            content="# Project Brief\n\n## Overview\n\nWal integration.\n",
        )
    data = _parse(out)
    assert data.get("status") == "success"
    wal_log = tmp_path / ".cortex" / "wal" / "write_log.jsonl"
    assert wal_log.is_file()
    lines = [
        ln for ln in wal_log.read_text(encoding="utf-8").splitlines() if ln.strip()
    ]
    assert len(lines) >= 1
    entry = json.loads(lines[-1])
    assert entry["operation"] == "write"
    assert "memory-bank/projectBrief.md" in entry["file"].replace("\\", "/")


@pytest.mark.asyncio
async def test_wal_log_failure_does_not_block_write(tmp_path: Path) -> None:
    memory_bank_dir = ensure_test_cortex_structure(tmp_path)
    _ = (memory_bank_dir / "techContext.md").write_text("# Tech\n", encoding="utf-8")

    with (
        patch(
            "cortex.core.project_root_resolver.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=tmp_path,
        ),
        patch(
            "cortex.tools.files.manage_file_helpers.resolve_schema_validator",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "cortex.memory.wal.MemoryWAL.log",
            side_effect=OSError("disk full"),
        ),
    ):
        out = await manage_file(
            operation="write",
            file_name="techContext.md",
            content="# Tech\n\n## Stack\n\nPython\n",
        )
    data = _parse(out)
    assert data.get("status") == "success"
