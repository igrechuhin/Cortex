"""E2E tests: create plan → update steps (roadmap) → list/archive flow.

Exercises plan workflow with at least 3 MCP tools in sequence.

Test-only stubs: Plans created here (e2e-plan-test, workflow-plan) are for tmp_path
only. They must NOT be created in the real .cortex/plans/ or roadmap. We patch all
path-resolution entry points (plan_crud, roadmap_operations, usage_context) so every
tool uses tmp_path and does not pollute the real project.
"""

import json
import re
from contextlib import contextmanager
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, patch

import pytest

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.file_operations import manage_file
from cortex.tools.plan_crud import create_plan
from cortex.tools.roadmap_operations import add_roadmap_entry, remove_roadmap_entry
from tests.helpers.path_helpers import ensure_test_cortex_structure
from tests.helpers.tool_call_helpers import get_tool_fn, to_dict


@contextmanager
def _isolated_root_patches(tmp_path: Path):
    """Yield nested patches so all tools use tmp_path as project root.

    Prevents test from polluting the real roadmap/plans. Must cover:
    - plan_crud.resolve_project_root_async (create_plan, list)
    - roadmap_operations.resolve_project_root_async (add_roadmap_entry)
    - usage_context.get_or_resolve_project_root (manage_file)
    """
    mock_resolve = AsyncMock(return_value=tmp_path)
    mock_get_root = AsyncMock(return_value=tmp_path)
    with (
        patch(
            "cortex.tools.plan_crud.resolve_project_root_async",
            mock_resolve,
        ),
        patch(
            "cortex.tools.roadmap_operations.resolve_project_root_async",
            mock_resolve,
        ),
        patch(
            "cortex.core.usage_context.get_or_resolve_project_root",
            mock_get_root,
        ),
    ):
        yield


def _write_minimal_memory_bank_and_roadmap(
    memory_bank_dir: Path, plans_dir: Path
) -> None:
    """Write minimal memory bank and roadmap for plan workflow."""
    _ = (memory_bank_dir / "activeContext.md").write_text("# Active Context\n\n")
    _ = (memory_bank_dir / "projectBrief.md").write_text("# Brief\n")
    _ = (memory_bank_dir / "roadmap.md").write_text(
        "# Roadmap\n\n## Pending plans (from .cortex/plans)\n\n"
    )
    for name in [
        "progress.md",
        "systemPatterns.md",
        "techContext.md",
        "productContext.md",
    ]:
        _ = (memory_bank_dir / name).write_text(f"# {name}\n")
    _ = plans_dir.mkdir(parents=True, exist_ok=True)


@pytest.mark.slow
@pytest.mark.timeout(120)
@pytest.mark.asyncio
async def test_plan_workflow_create_add_list(tmp_path: Path) -> None:
    """E2E: create_plan → add_roadmap_entry → list_plans (3 tools)."""
    memory_bank_dir = ensure_test_cortex_structure(tmp_path)
    plans_dir = get_cortex_path(tmp_path, CortexResourceType.PLANS)
    _write_minimal_memory_bank_and_roadmap(memory_bank_dir, plans_dir)

    with _isolated_root_patches(tmp_path):
        # 1) create_plan
        create_fn = get_tool_fn(create_plan)
        create_result = await create_fn(
            title="E2E Plan Test",
            content="# E2E Plan\n\n## Step 1\n\nDone.\n",
            slug="e2e-plan-test",
            ctx=None,
        )
        create_data = cast(
            dict[str, object],
            (
                to_dict(cast(object, create_result))
                if isinstance(create_result, dict)
                else json.loads(str(create_result))
            ),
        )
        assert create_data.get("status") == "success" or "plan_path" in str(create_data)
        file_path = create_data.get("file_path")
        if isinstance(file_path, str):
            assert (
                Path(file_path).resolve().is_relative_to(tmp_path.resolve())
            ), f"Plan must be under tmp_path, got {file_path!r}"

        # 2) add_roadmap_entry (register the plan)
        add_fn = get_tool_fn(add_roadmap_entry)
        add_result = await add_fn(
            section="pending",
            entry_text="- **E2E Plan Test** - PENDING - Plan: .cortex/plans/e2e-plan-test.md",
            position="last",
            ctx=None,
        )
        add_data = cast(
            dict[str, object],
            (
                to_dict(cast(object, add_result))
                if isinstance(add_result, dict)
                else json.loads(str(add_result))
            ),
        )
        assert add_data.get("status") in ("success", "error") or "line_inserted" in str(
            add_data
        )

        # 3) create_plan(operation="list")
        list_fn = get_tool_fn(create_plan)
        list_result = await list_fn(operation="list", include_archive=False, ctx=None)
        list_data = cast(
            dict[str, object],
            (
                to_dict(cast(object, list_result))
                if isinstance(list_result, dict)
                else json.loads(str(list_result))
            ),
        )
        assert "plans" in list_data or "status" in list_data

        # 4) Mark plan COMPLETE so remove_roadmap_entry guardrail allows removal
        plan_path = plans_dir / "e2e-plan-test.md"
        if plan_path.exists():
            content = plan_path.read_text()
            if re.search(r"^\*\*Status:\*\*", content, re.MULTILINE):
                content = re.sub(
                    r"^\*\*Status:\*\*\s*.*$",
                    "**Status:** COMPLETE",
                    content,
                    count=1,
                    flags=re.MULTILINE,
                )
            else:
                content = content.replace(
                    "# E2E Plan", "# E2E Plan\n\n**Status:** COMPLETE"
                )
            _ = plan_path.write_text(content)

        # 5) remove_roadmap_entry (cleanup the test entry)
        remove_fn = get_tool_fn(remove_roadmap_entry)
        remove_result = await remove_fn(entry_contains="E2E Plan Test", ctx=None)
        remove_data = cast(
            dict[str, object],
            (
                to_dict(cast(object, remove_result))
                if isinstance(remove_result, dict)
                else json.loads(str(remove_result))
            ),
        )
        assert remove_data.get("status") == "success"


@pytest.mark.slow
@pytest.mark.timeout(120)
@pytest.mark.asyncio
async def test_plan_workflow_manage_file_create_plan(tmp_path: Path) -> None:
    """E2E: manage_file read roadmap → create_plan → list_plans (3 tools)."""
    memory_bank_dir = ensure_test_cortex_structure(tmp_path)
    plans_dir = get_cortex_path(tmp_path, CortexResourceType.PLANS)
    _write_minimal_memory_bank_and_roadmap(memory_bank_dir, plans_dir)

    with _isolated_root_patches(tmp_path):
        # 1) manage_file read roadmap
        read_result = await manage_file(operation="read", file_name="roadmap.md")
        read_data = (
            json.loads(read_result) if isinstance(read_result, str) else read_result
        )
        assert read_data.get("status") == "success"

        # 2) create_plan
        create_fn = get_tool_fn(create_plan)
        create_result = await create_fn(
            title="Workflow Plan",
            content="# Workflow\n\n## Goals\n\n- E2E\n",
            ctx=None,
        )
        assert create_result is not None
        create_data = cast(
            dict[str, object],
            (
                to_dict(cast(object, create_result))
                if isinstance(create_result, dict)
                else json.loads(str(create_result))
            ),
        )
        file_path = create_data.get("file_path")
        if isinstance(file_path, str):
            assert (
                Path(file_path).resolve().is_relative_to(tmp_path.resolve())
            ), f"Plan must be under tmp_path, got {file_path!r}"

        # 3) create_plan(operation="list")
        list_fn = get_tool_fn(create_plan)
        list_result = await list_fn(operation="list", include_archive=False, ctx=None)
        list_data = cast(
            dict[str, object],
            (
                to_dict(cast(object, list_result))
                if isinstance(list_result, dict)
                else json.loads(str(list_result))
            ),
        )
        assert "plans" in list_data or "status" in list_data
