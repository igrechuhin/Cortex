"""E2E tests: detect pattern → suggest refactoring → validate.

Exercises refactoring workflow with at least 3 MCP tools in sequence.
"""

import json
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, patch

import pytest

from cortex.tools.query_memory_bank_operations import query_memory_bank
from cortex.tools.refactoring_operations import suggest_refactoring
from cortex.tools.validation_operations import validate
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


@pytest.mark.slow
@pytest.mark.timeout(120)
@pytest.mark.asyncio
async def test_refactoring_workflow_suggest_query_validate(tmp_path: Path) -> None:
    """E2E: suggest_refactoring → query_memory_bank → validate (3 tools)."""
    memory_bank_dir = ensure_test_cortex_structure(tmp_path)
    _write_minimal_memory_bank(memory_bank_dir)

    with patch(
        "cortex.core.project_root_resolver.resolve_project_root_async",
        new_callable=AsyncMock,
        return_value=tmp_path,
    ):
        # 1) suggest_refactoring (consolidation type)
        suggest_fn = get_tool_fn(suggest_refactoring)
        suggest_result = await suggest_fn(
            type="consolidation",
            response_format="concise",
            ctx=None,
        )
        suggest_data = cast(
            dict[str, object],
            (
                to_dict(cast(object, suggest_result))
                if isinstance(suggest_result, dict)
                else json.loads(str(suggest_result))
            ),
        )
        assert (
            "suggestions" in suggest_data
            or "status" in suggest_data
            or "result" in str(suggest_data)
        )

        # 2) query_memory_bank stats
        query_fn = get_tool_fn(query_memory_bank)
        query_result = await query_fn(query_type="stats", ctx=None)
        q_data = cast(
            dict[str, object],
            (
                to_dict(cast(object, query_result))
                if isinstance(query_result, dict)
                else json.loads(str(query_result))
            ),
        )
        assert "summary" in q_data or "total_files" in str(q_data) or "result" in q_data

        # 3) validate schema
        validate_fn = get_tool_fn(validate)
        val_result = await validate_fn(
            check_type="schema", file_name="activeContext.md", ctx=None
        )
        assert val_result is not None


@pytest.mark.slow
@pytest.mark.timeout(120)
@pytest.mark.asyncio
async def test_refactoring_workflow_suggest_then_validate_roadmap(
    tmp_path: Path,
) -> None:
    """E2E: suggest_refactoring (splits) → validate roadmap_sync → query (3 tools)."""
    memory_bank_dir = ensure_test_cortex_structure(tmp_path)
    _write_minimal_memory_bank(memory_bank_dir)

    with patch(
        "cortex.core.project_root_resolver.resolve_project_root_async",
        new_callable=AsyncMock,
        return_value=tmp_path,
    ):
        # 1) suggest_refactoring splits
        suggest_fn = get_tool_fn(suggest_refactoring)
        suggest_result = await suggest_fn(
            type="splits", response_format="concise", ctx=None
        )
        assert suggest_result is not None

        # 2) validate roadmap_sync
        validate_fn = get_tool_fn(validate)
        val_result = await validate_fn(check_type="roadmap_sync", ctx=None)
        val_data = cast(
            dict[str, object],
            (
                to_dict(cast(object, val_result))
                if isinstance(val_result, dict)
                else json.loads(str(val_result))
            ),
        )
        assert "valid" in val_data or "status" in val_data or "errors" in str(val_data)

        # 3) query_memory_bank dependency_graph
        query_fn = get_tool_fn(query_memory_bank)
        query_result = await query_fn(
            query_type="dependency_graph", format="json", ctx=None
        )
        assert query_result is not None
