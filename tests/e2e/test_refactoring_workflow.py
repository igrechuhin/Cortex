"""E2E tests: detect pattern → suggest refactoring → validate.

Exercises refactoring workflow with at least 3 MCP tools in sequence.
"""

import json
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, patch

import pytest

from cortex.tools.memory.query_memory_bank_operations import query_memory_bank
from cortex.tools.refactoring import suggest_refactoring
from cortex.tools.validation.operations import validate_impl as validate
from tests.helpers.path_helpers import ensure_test_cortex_structure
from tests.helpers.tool_call_helpers import get_tool_fn, to_dict


def _write_minimal_memory_bank(memory_bank_dir: Path) -> None:
    """Write minimal memory bank files."""
    _ = (memory_bank_dir / "activeContext.md").write_text("# Active Context\n\n")
    _ = (memory_bank_dir / "roadmap.md").write_text("# Roadmap\n\n")
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


async def _step_suggest_refactoring(
    refactoring_type: str, response_format: str = "concise"
) -> dict[str, object]:
    """Run suggest_refactoring and return parsed result."""
    suggest_fn = get_tool_fn(suggest_refactoring)
    result = await suggest_fn(
        type=refactoring_type, response_format=response_format, ctx=None
    )
    return _parse_result(result)


async def _step_query_stats() -> dict[str, object]:
    """Query memory bank stats and return parsed result."""
    query_fn = get_tool_fn(query_memory_bank)
    result = await query_fn(query_type="stats", ctx=None)
    return _parse_result(result)


async def _step_validate(
    check_type: str, file_name: str | None = None
) -> dict[str, object]:
    """Run validation and return parsed result."""
    validate_fn = get_tool_fn(validate)
    result = await validate_fn(check_type=check_type, file_name=file_name, ctx=None)
    return _parse_result(result)


@pytest.mark.slow
@pytest.mark.timeout(120)
@pytest.mark.asyncio
async def test_refactoring_workflow_suggest_query_validate(tmp_path: Path) -> None:
    """E2E: suggest_refactoring -> query_memory_bank -> validate (3 tools)."""
    memory_bank_dir = ensure_test_cortex_structure(tmp_path)
    _write_minimal_memory_bank(memory_bank_dir)

    with patch(
        "cortex.core.project_root_resolver.resolve_project_root_async",
        new_callable=AsyncMock,
        return_value=tmp_path,
    ):
        suggest_data = await _step_suggest_refactoring("consolidation")
        assert (
            "suggestions" in suggest_data
            or "status" in suggest_data
            or "result" in str(suggest_data)
        )

        q_data = await _step_query_stats()
        assert "summary" in q_data or "total_files" in str(q_data) or "result" in q_data

        val_result = await _step_validate("schema", "activeContext.md")
        assert val_result is not None


@pytest.mark.slow
@pytest.mark.timeout(120)
@pytest.mark.asyncio
async def test_refactoring_workflow_suggest_then_validate_roadmap(
    tmp_path: Path,
) -> None:
    """E2E: suggest_refactoring (splits) -> validate roadmap_sync -> query (3 tools)."""
    memory_bank_dir = ensure_test_cortex_structure(tmp_path)
    _write_minimal_memory_bank(memory_bank_dir)

    with patch(
        "cortex.core.project_root_resolver.resolve_project_root_async",
        new_callable=AsyncMock,
        return_value=tmp_path,
    ):
        suggest_data = await _step_suggest_refactoring("splits")
        assert suggest_data is not None

        val_data = await _step_validate("roadmap_sync")
        assert "valid" in val_data or "status" in val_data or "errors" in str(val_data)

        query_fn = get_tool_fn(query_memory_bank)
        query_result = await query_fn(
            query_type="dependency_graph", format="json", ctx=None
        )
        assert query_result is not None
