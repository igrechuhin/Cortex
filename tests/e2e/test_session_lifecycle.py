"""Scheduled session workflows use the registered tool and resource surface."""

import json
from pathlib import Path

import pytest

from tests.e2e.public_workflow_helpers import call_public_tool
from tests.integration.resource_test_helpers import read_resource_text

pytestmark = [pytest.mark.slow, pytest.mark.asyncio, pytest.mark.timeout(120)]


async def _compact_and_assert_handoff(root: Path, summary: str) -> None:
    compact = await call_public_tool("session", operation="compact", summary=summary)
    assert compact["status"] == "success", compact
    handoff = json.loads(
        (root / ".cortex/.cache/session/last_handoff.json").read_text(encoding="utf-8")
    )
    assert summary in handoff["next_actions"]


async def test_session_lifecycle_session_start_load_context_compact(
    public_project: Path,
) -> None:
    # Arrange / Act
    started = await call_public_tool(
        "session", operation="start", task_description="python"
    )
    context = json.loads(await read_resource_text("cortex://context"))

    # Assert: context contains this project's content and compaction persists handoff.
    assert started["status"] == "success", started
    assert context["status"] == "success", context
    assert "Decision: Preserve public workflow isolation." in json.dumps(context)
    await _compact_and_assert_handoff(public_project, "E2E lifecycle test")


async def test_session_lifecycle_with_manage_file(public_project: Path) -> None:
    # Arrange / Act
    started = await call_public_tool("session", operation="start")
    read = await call_public_tool(
        "manage_file", operation="read", file_name="activeContext.md"
    )
    context = json.loads(await read_resource_text("cortex://context"))

    # Assert
    assert started["status"] == "success", started
    assert read["status"] == "success", read
    assert "Python smoke." in str(read["content"])
    assert context["status"] == "success", context
    await _compact_and_assert_handoff(public_project, "Memory bank workflow complete")


async def test_session_lifecycle_analysis_after_public_compaction(
    public_project: Path,
) -> None:
    # Arrange: the removed direct compact helper is superseded by session(compact).
    started = await call_public_tool("session", operation="start")
    assert started["status"] == "success", started
    _ = await read_resource_text("cortex://context")
    await _compact_and_assert_handoff(public_project, "Public lifecycle complete")

    # Act / Assert: a real recorded load must not degrade to no_data.
    analysis = json.loads(await read_resource_text("cortex://analysis"))
    assert analysis["status"] == "success", analysis
