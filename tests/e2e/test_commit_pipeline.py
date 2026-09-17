"""Scheduled commit workflows assert public success, persistence, and validation."""

import json
from pathlib import Path

import pytest

from tests.e2e.public_workflow_helpers import call_public_tool
from tests.integration.resource_test_helpers import read_resource_text

pytestmark = [pytest.mark.slow, pytest.mark.asyncio, pytest.mark.timeout(180)]


async def test_commit_pipeline_manage_file_validate_pre_commit(
    quality_project: Path,
) -> None:
    # Arrange / Act
    read = await call_public_tool(
        "manage_file", operation="read", file_name="progress.md"
    )
    validation = json.loads(await read_resource_text("cortex://validation"))
    gate = await call_public_tool("run_quality_gate")

    # Assert: no no-op/error envelope can satisfy this workflow.
    assert read["status"] == "success", read
    assert "Decision: Preserve public workflow isolation." in str(read["content"])
    assert validation["status"] == "success", validation
    assert validation["results"]["progress.md"]["valid"] is True
    assert gate["preflight_passed"] is True, gate


async def test_commit_pipeline_write_then_validate(public_project: Path) -> None:
    # Arrange
    content = (
        "# Progress\n\n## What Works\n\n- E2E commit pipeline test.\n\n"
        "## What's Left\n\n- None.\n"
    )

    # Act
    written = await call_public_tool(
        "manage_file", operation="write", file_name="progress.md", content=content
    )
    read = await call_public_tool(
        "manage_file", operation="read", file_name="progress.md"
    )
    validation = json.loads(await read_resource_text("cortex://validation"))

    # Assert
    assert written["status"] == "success", written
    assert read["status"] == "success", read
    assert str(read["content"]).endswith(content)
    assert (public_project / ".cortex/memory-bank/progress.md").read_text() == read[
        "content"
    ]
    assert validation["status"] == "success", validation
    assert validation["results"]["progress.md"]["valid"] is True
