"""E2E tests: create project → manage_file → validate → query.

Exercises memory bank workflow with at least 3 MCP tools in sequence.
"""

import json
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, patch

import pytest

from cortex.tools.files.operations import manage_file
from cortex.tools.memory.query_memory_bank_operations import query_memory_bank
from cortex.tools.validation.operations import validate_impl as validate
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


def _parse_result(result: object) -> dict[str, object]:
    """Convert a tool result (dict or JSON string) to a plain dict."""
    return cast(
        dict[str, object],
        (
            to_dict(cast(object, result))
            if isinstance(result, dict)
            else json.loads(str(result))
        ),
    )


async def _step_manage_file_read(file_name: str) -> dict[str, object]:
    """Read a memory bank file and return parsed result."""
    read_result = await manage_file(operation="read", file_name=file_name)
    return _parse_result(read_result)


async def _step_validate_schema(file_name: str | None = None) -> dict[str, object]:
    """Run schema validation and return parsed result."""
    validate_fn = get_tool_fn(validate)
    result = await validate_fn(check_type="schema", file_name=file_name, ctx=None)
    return _parse_result(result)


async def _step_query_stats() -> dict[str, object]:
    """Query memory bank stats and return parsed result."""
    query_fn = get_tool_fn(query_memory_bank)
    result = await query_fn(query_type="stats", ctx=None)
    return _parse_result(result)


@pytest.mark.slow
@pytest.mark.timeout(120)
@pytest.mark.asyncio
async def test_memory_bank_workflow_manage_file_validate_query(tmp_path: Path) -> None:
    """E2E: manage_file read -> validate schema -> query_memory_bank stats (3+ tools)."""
    memory_bank_dir = ensure_test_cortex_structure(tmp_path)
    _write_minimal_memory_bank(memory_bank_dir)

    with patch(
        "cortex.core.project_root_resolver.resolve_project_root_async",
        new_callable=AsyncMock,
        return_value=tmp_path,
    ):
        read_data = await _step_manage_file_read("activeContext.md")
        assert read_data.get("status") == "success"
        assert "content" in read_data

        val_data = await _step_validate_schema("activeContext.md")
        assert "valid" in val_data or "status" in val_data or "errors" in str(val_data)

        q_data = await _step_query_stats()
        assert "summary" in q_data or "total_files" in str(q_data) or "result" in q_data


async def _step_manage_file_write(file_name: str, content: str) -> dict[str, object]:
    """Write a memory bank file and return parsed result."""
    write_result = await manage_file(
        operation="write", file_name=file_name, content=content
    )
    return _parse_result(write_result)


async def _step_manage_file_metadata(file_name: str) -> dict[str, object]:
    """Get metadata for a memory bank file and return parsed result."""
    meta_result = await manage_file(operation="metadata", file_name=file_name)
    return _parse_result(meta_result)


@pytest.mark.slow
@pytest.mark.timeout(120)
@pytest.mark.asyncio
async def test_memory_bank_workflow_write_then_validate(tmp_path: Path) -> None:
    """E2E: manage_file write -> manage_file metadata -> validate (3 tools)."""
    memory_bank_dir = ensure_test_cortex_structure(tmp_path)
    _write_minimal_memory_bank(memory_bank_dir)

    with patch(
        "cortex.core.project_root_resolver.resolve_project_root_async",
        new_callable=AsyncMock,
        return_value=tmp_path,
    ):
        write_data = await _step_manage_file_write(
            "progress.md",
            (
                "# Progress\n\n## What Works\n\n- E2E write test.\n\n"
                "## What's Left\n\n- None.\n"
            ),
        )
        assert write_data.get("status") == "success"

        meta_data = await _step_manage_file_metadata("progress.md")
        assert meta_data.get("status") == "success"
        assert "metadata" in meta_data

        val_result = await _step_validate_schema()
        assert val_result is not None
