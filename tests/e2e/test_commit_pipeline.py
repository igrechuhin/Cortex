"""E2E tests: code change → pre-commit checks → fix issues (workflow).

Exercises commit-pipeline workflow with at least 3 MCP tools in sequence.
Uses a temporary project root; pre-commit may no-op or report no files.
"""

import json
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, patch

import pytest

from cortex.tools.execution.pre_commit_tools import execute_pre_commit_checks
from cortex.tools.files.operations import manage_file
from cortex.tools.validation.operations import validate_impl as validate
from tests.helpers.path_helpers import ensure_test_cortex_structure
from tests.helpers.tool_call_helpers import get_tool_fn


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


async def _step_manage_file_read(file_name: str) -> dict[str, object]:
    """Read a memory bank file and assert success."""
    read_result = await manage_file(operation="read", file_name=file_name)
    read_data = json.loads(read_result) if isinstance(read_result, str) else read_result
    assert read_data.get("status") == "success"
    return cast(dict[str, object], read_data)


async def _step_validate_schema(file_name: str) -> object:
    """Run schema validation and assert non-None result."""
    validate_fn = get_tool_fn(validate)
    val_result = await validate_fn(check_type="schema", file_name=file_name, ctx=None)
    assert val_result is not None
    return val_result


@pytest.mark.slow
@pytest.mark.timeout(180)
@pytest.mark.asyncio
async def test_commit_pipeline_manage_file_validate_pre_commit(tmp_path: Path) -> None:
    """E2E: manage_file read -> validate -> execute_pre_commit_checks (3 tools)."""
    memory_bank_dir = ensure_test_cortex_structure(tmp_path)
    _write_minimal_memory_bank(memory_bank_dir)

    with patch(
        "cortex.core.project_root_resolver.resolve_project_root_async",
        new_callable=AsyncMock,
        return_value=tmp_path,
    ):
        _ = await _step_manage_file_read("activeContext.md")
        _ = await _step_validate_schema("activeContext.md")

        pre_commit_result = await execute_pre_commit_checks(
            checks=["format"],
            test_timeout=60,
            coverage_threshold=0.0,
            strict_mode=False,
            ctx=None,
        )
        result_dict = cast(dict[str, object], pre_commit_result)
        assert "status" in result_dict or "checks" in result_dict


@pytest.mark.slow
@pytest.mark.timeout(120)
@pytest.mark.asyncio
async def test_commit_pipeline_write_then_validate(tmp_path: Path) -> None:
    """E2E: manage_file write → manage_file read → validate (3 tools)."""
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
                "# Progress\n\n"
                "## What Works\n\n- E2E commit pipeline test.\n\n"
                "## What's Left\n\n- None.\n"
            ),
        )
        assert json.loads(write_result).get("status") == "success"

        # 2) manage_file read
        read_result = await manage_file(operation="read", file_name="progress.md")
        assert json.loads(read_result).get("status") == "success"

        # 3) validate
        validate_fn = get_tool_fn(validate)
        _ = await validate_fn(check_type="schema", file_name="progress.md", ctx=None)
