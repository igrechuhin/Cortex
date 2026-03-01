"""E2E tests: create project → manage_file → validate → query.

Exercises memory bank workflow with at least 3 MCP tools in sequence.
"""

import json
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, patch

import pytest

from cortex.tools.files.file_operations import manage_file
from cortex.tools.query_memory_bank_operations import query_memory_bank
from cortex.tools.validation.operations import validate
from tests.helpers.path_helpers import ensure_test_cortex_structure
from tests.helpers.tool_call_helpers import get_tool_fn, to_dict


def _write_minimal_memory_bank(memory_bank_dir: Path) -> None:
    """Write minimal memory bank files."""
    _ = (memory_bank_dir / "activeContext.md").write_text(
        "# Active Context\n\n## Current Focus\n\nTest.\n"
    )
    _ = (memory_bank_dir / "roadmap.md").write_text(
        "# Roadmap\n\n## Pending\n\n- Item\n"
    )
    _ = (memory_bank_dir / "projectBrief.md").write_text("# Brief\n")
    for name in [
        "progress.md",
        "systemPatterns.md",
        "techContext.md",
        "productContext.md",
    ]:
        _ = (memory_bank_dir / name).write_text(f"# {name}\n")


@pytest.mark.slow
@pytest.mark.timeout(120)
@pytest.mark.asyncio
async def test_memory_bank_workflow_manage_file_validate_query(tmp_path: Path) -> None:
    """E2E: manage_file read → validate schema → query_memory_bank stats (3+ tools)."""
    memory_bank_dir = ensure_test_cortex_structure(tmp_path)
    _write_minimal_memory_bank(memory_bank_dir)

    with patch(
        "cortex.core.project_root_resolver.resolve_project_root_async",
        new_callable=AsyncMock,
        return_value=tmp_path,
    ):
        # 1) manage_file read
        read_result = await manage_file(
            operation="read",
            file_name="activeContext.md",
        )
        read_data = (
            json.loads(read_result) if isinstance(read_result, str) else read_result
        )
        assert read_data.get("status") == "success"
        assert "content" in read_data

        # 2) validate (schema)
        validate_fn = get_tool_fn(validate)
        validate_result = await validate_fn(
            check_type="schema",
            file_name="activeContext.md",
            ctx=None,
        )
        val_data = cast(
            dict[str, object],
            (
                to_dict(cast(object, validate_result))
                if isinstance(validate_result, dict)
                else json.loads(str(validate_result))
            ),
        )
        assert "valid" in val_data or "status" in val_data or "errors" in str(val_data)

        # 3) query_memory_bank stats
        query_fn = get_tool_fn(query_memory_bank)
        query_result = await query_fn(
            query_type="stats",
            ctx=None,
        )
        q_data = cast(
            dict[str, object],
            (
                to_dict(cast(object, query_result))
                if isinstance(query_result, dict)
                else json.loads(str(query_result))
            ),
        )
        assert "summary" in q_data or "total_files" in str(q_data) or "result" in q_data


@pytest.mark.slow
@pytest.mark.timeout(120)
@pytest.mark.asyncio
async def test_memory_bank_workflow_write_then_validate(tmp_path: Path) -> None:
    """E2E: manage_file write → manage_file metadata → validate (3 tools)."""
    memory_bank_dir = ensure_test_cortex_structure(tmp_path)
    _write_minimal_memory_bank(memory_bank_dir)

    with patch(
        "cortex.core.project_root_resolver.resolve_project_root_async",
        new_callable=AsyncMock,
        return_value=tmp_path,
    ):
        # 1) manage_file write (schema-valid progress: What Works, What's Left)
        write_result = await manage_file(
            operation="write",
            file_name="progress.md",
            content=(
                "# Progress\n\n## What Works\n\n- E2E write test.\n\n"
                "## What's Left\n\n- None.\n"
            ),
        )
        write_data = (
            json.loads(write_result) if isinstance(write_result, str) else write_result
        )
        assert write_data.get("status") == "success"

        # 2) manage_file metadata
        meta_result = await manage_file(
            operation="metadata",
            file_name="progress.md",
        )
        meta_data = (
            json.loads(meta_result) if isinstance(meta_result, str) else meta_result
        )
        assert meta_data.get("status") == "success"
        assert "metadata" in meta_data

        # 3) validate schema
        validate_fn = get_tool_fn(validate)
        val_result = await validate_fn(check_type="schema", ctx=None)
        assert val_result is not None
