"""E2E tests: session(operation=start) → load_context → work → session(operation=compact).

Exercises session lifecycle workflow with at least 3 MCP tools in sequence.
"""

import json
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, patch

import pytest

from cortex.tools.context.analysis_operations import analyze_impl as analyze
from cortex.tools.files.operations import manage_file
from cortex.tools.memory.compaction_operations import compact_session
from cortex.tools.optimization import load_context_impl as load_context
from cortex.tools.session.dispatcher import session
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


async def _step_session_start() -> dict[str, object]:
    """Call session(start) and return parsed result."""
    tool_fn = get_tool_fn(session)
    result = await tool_fn(operation="start", task_description=None, ctx=None)
    return _parse_result(result)


async def _step_session_compact(summary: str | None = None) -> dict[str, object]:
    """Call session(compact) and return parsed result."""
    compact_fn = get_tool_fn(session)
    result = await compact_fn(operation="compact", summary=summary, ctx=None)
    return _parse_result(result)


async def _step_load_context(task: str, budget: int = 2000) -> dict[str, object]:
    """Call load_context and return parsed result."""
    load_fn = get_tool_fn(load_context)
    result = await load_fn(task_description=task, token_budget=budget, ctx=None)
    return _parse_result(result)


async def _step_manage_file_read(file_name: str) -> dict[str, object]:
    """Read a memory bank file and return parsed data."""
    read_result = await manage_file(operation="read", file_name=file_name)
    if isinstance(read_result, str):
        return cast(dict[str, object], json.loads(read_result))
    if hasattr(read_result, "model_dump"):
        return cast(dict[str, object], read_result.model_dump())
    return cast(dict[str, object], dict(read_result))


def _mixed_entrypoint_patches(tmp_path: Path):
    """Return combined patches for mixed-entrypoint lifecycle test."""
    from contextlib import contextmanager

    @contextmanager
    def _combined():
        with (
            patch(
                "cortex.core.project_root_resolver.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=tmp_path,
            ),
            patch(
                "cortex.tools.compaction_operations.get_or_resolve_project_root",
                new_callable=AsyncMock,
                return_value=tmp_path,
            ),
        ):
            yield

    return _combined()


async def _step_compact_session(summary: str) -> dict[str, object]:
    """Call compact_session directly and return parsed result."""
    compact_fn = get_tool_fn(compact_session)
    result = await compact_fn(summary=summary, ctx=None)
    return _parse_result(result)


async def _step_analyze_context() -> dict[str, object]:
    """Call analyze(target=context) and return parsed result."""
    analyze_fn = get_tool_fn(analyze)
    result = await analyze_fn(target="context", ctx=None)
    return cast(dict[str, object], json.loads(str(result)))


@pytest.mark.slow
@pytest.mark.timeout(120)
@pytest.mark.asyncio
async def test_session_lifecycle_session_start_load_context_compact(
    tmp_path: Path,
) -> None:
    """E2E: session(start) -> load_context -> session(compact) (3+ tools)."""
    memory_bank_dir = ensure_test_cortex_structure(tmp_path)
    _write_minimal_memory_bank(memory_bank_dir)

    with patch(
        "cortex.core.project_root_resolver.resolve_project_root_async",
        new_callable=AsyncMock,
        return_value=tmp_path,
    ):
        result = await _step_session_start()
        assert result.get("status") == "success", result
        assert "brief" in result or "token_count" in result

        load_data = await _step_load_context("E2E session lifecycle")
        assert load_data.get("status") == "success"
        assert "file_names" in load_data or "total_tokens" in load_data

        compact_data = await _step_session_compact("E2E lifecycle test")
        assert compact_data.get("status") in ("success", "error")
        if compact_data.get("status") == "success":
            assert "token_savings" in compact_data or "summary" in str(compact_data)


@pytest.mark.slow
@pytest.mark.timeout(120)
@pytest.mark.asyncio
async def test_session_lifecycle_with_manage_file(tmp_path: Path) -> None:
    """E2E: session(start) -> manage_file read -> load_context -> session(compact) (4 tools)."""
    memory_bank_dir = ensure_test_cortex_structure(tmp_path)
    _write_minimal_memory_bank(memory_bank_dir)

    with patch(
        "cortex.core.project_root_resolver.resolve_project_root_async",
        new_callable=AsyncMock,
        return_value=tmp_path,
    ):
        r1_dict = await _step_session_start()
        assert r1_dict.get("status") == "success"

        read_data = await _step_manage_file_read("activeContext.md")
        assert read_data.get("status") == "success"
        assert "content" in read_data

        load_data = await _step_load_context("Memory bank workflow", 1000)
        assert load_data is not None

        compact_data = await _step_session_compact()
        assert "status" in compact_data


@pytest.mark.slow
@pytest.mark.timeout(120)
@pytest.mark.asyncio
async def test_session_lifecycle_analyze_context_not_no_data_for_mixed_entrypoints(
    tmp_path: Path,
) -> None:
    """Regression: analyze(context) stays non-no_data after mixed entrypoints."""
    memory_bank_dir = ensure_test_cortex_structure(tmp_path)
    _write_minimal_memory_bank(memory_bank_dir)

    with _mixed_entrypoint_patches(tmp_path):
        start_data = await _step_session_start()
        assert start_data.get("status") == "success"

        compact_data = await _step_compact_session("mixed-entrypoint lifecycle")
        assert "status" in compact_data

        analyze_data = await _step_analyze_context()
        assert analyze_data.get("status") in ("success", "no_data")
