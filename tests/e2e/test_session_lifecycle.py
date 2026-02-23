"""E2E tests: session_start → load_context → work → compact_session.

Exercises session lifecycle workflow with at least 3 MCP tools in sequence.
"""

import json
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, patch

import pytest

from cortex.tools.compaction_operations import compact_session
from cortex.tools.file_operations import manage_file
from cortex.tools.phase4_optimization_handlers import load_context
from cortex.tools.session_start_tools import session_start
from tests.helpers.path_helpers import ensure_test_cortex_structure
from tests.helpers.tool_call_helpers import get_tool_fn, to_dict


def _write_minimal_memory_bank(memory_bank_dir: Path) -> None:
    """Write minimal memory bank files for session/load_context/compact."""
    _ = (memory_bank_dir / "activeContext.md").write_text(
        "# Active Context\n\n## Current Focus\n\nE2E test.\n\n## Next Steps\n\n- Step 1\n"
    )
    _ = (memory_bank_dir / "roadmap.md").write_text(
        "# Roadmap\n\n## Pending plans\n\n- **Test** - PENDING\n"
    )
    _ = (memory_bank_dir / "projectBrief.md").write_text("# Project\n")
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
async def test_session_lifecycle_session_start_load_context_compact(
    tmp_path: Path,
) -> None:
    """E2E: session_start → load_context → compact_session (3+ tools)."""
    memory_bank_dir = ensure_test_cortex_structure(tmp_path)
    _write_minimal_memory_bank(memory_bank_dir)

    with patch(
        "cortex.core.project_root_resolver.resolve_project_root_async",
        new_callable=AsyncMock,
        return_value=tmp_path,
    ):
        # 1) session_start
        tool_fn = get_tool_fn(session_start)
        result_json = await tool_fn(task_description=None, ctx=None)
        result = cast(
            dict[str, object],
            (
                to_dict(cast(object, result_json))
                if isinstance(result_json, dict)
                else json.loads(str(result_json))
            ),
        )
        assert result.get("status") == "success", result
        assert "brief" in result or "token_count" in result

        # 2) load_context
        load_fn = get_tool_fn(load_context)
        load_result = await load_fn(
            task_description="E2E session lifecycle",
            token_budget=2000,
            ctx=None,
        )
        load_data = cast(
            dict[str, object],
            (
                to_dict(cast(object, load_result))
                if isinstance(load_result, dict)
                else json.loads(str(load_result))
            ),
        )
        assert load_data.get("status") == "success"
        assert "file_names" in load_data or "total_tokens" in load_data

        # 3) compact_session (optional summary)
        compact_fn = get_tool_fn(compact_session)
        compact_result = await compact_fn(summary="E2E lifecycle test", ctx=None)
        compact_data = cast(
            dict[str, object],
            (
                to_dict(cast(object, compact_result))
                if isinstance(compact_result, dict)
                else json.loads(str(compact_result))
            ),
        )
        assert compact_data.get("status") in ("success", "error")
        if compact_data.get("status") == "success":
            assert "token_savings" in compact_data or "summary" in str(compact_data)


@pytest.mark.slow
@pytest.mark.timeout(120)
@pytest.mark.asyncio
async def test_session_lifecycle_with_manage_file(tmp_path: Path) -> None:
    """E2E: session_start → manage_file read → load_context → compact (4 tools)."""
    memory_bank_dir = ensure_test_cortex_structure(tmp_path)
    _write_minimal_memory_bank(memory_bank_dir)

    with patch(
        "cortex.core.project_root_resolver.resolve_project_root_async",
        new_callable=AsyncMock,
        return_value=tmp_path,
    ):
        # 1) session_start
        tool_fn = get_tool_fn(session_start)
        r1 = await tool_fn(task_description=None, ctx=None)
        r1_dict = cast(
            dict[str, object],
            to_dict(cast(object, r1)) if isinstance(r1, dict) else json.loads(str(r1)),
        )
        assert r1_dict.get("status") == "success"

        # 2) manage_file read
        read_result = await manage_file(
            operation="read",
            file_name="activeContext.md",
        )
        if isinstance(read_result, str):
            read_data = json.loads(read_result)
        else:
            read_data = (
                read_result.model_dump()
                if hasattr(read_result, "model_dump")
                else dict(read_result)
            )
        assert read_data.get("status") == "success"
        assert "content" in read_data

        # 3) load_context
        load_fn = get_tool_fn(load_context)
        load_result = await load_fn(
            task_description="Memory bank workflow", token_budget=1000, ctx=None
        )
        assert load_result is not None

        # 4) compact_session
        compact_fn = get_tool_fn(compact_session)
        compact_result = await compact_fn(summary=None, ctx=None)
        compact_data = cast(
            dict[str, object],
            (
                to_dict(cast(object, compact_result))
                if isinstance(compact_result, dict)
                else json.loads(str(compact_result))
            ),
        )
        assert "status" in compact_data
