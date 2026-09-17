"""Bounded PR smoke through the registered MCP tools and resources."""

import json
from pathlib import Path
from typing import cast

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError
from mcp.types import Implementation
from tiktoken.registry import get_encoding

from cortex.server import mcp
from tests.e2e.public_workflow_helpers import call_public_tool
from tests.integration.resource_test_helpers import read_resource_text
from tests.integration.test_hybrid_rules_delivery import DeliveredRulesPayload

pytestmark = [pytest.mark.asyncio, pytest.mark.timeout(180)]


async def test_shared_rules_and_complete_context_budget(public_project: Path) -> None:
    # Arrange / Act: real manifest files and real managers behind registered resources.
    rules = DeliveredRulesPayload.model_validate_json(
        await read_resource_text("cortex://rules")
    )
    serialized = await read_resource_text("cortex://context")
    context = json.loads(serialized)

    # Assert: an empty/local-only fallback cannot pass this smoke.
    assert any(rule.content == "python common generic policy" for rule in rules.rules)
    assert any(
        rule.content == "python formatting language policy" for rule in rules.rules
    )
    assert context["status"] == "success", context
    assert context["total_tokens"] == len(
        get_encoding("cl100k_base").encode(serialized)
    )
    assert context["total_tokens"] <= 12000
    assert sum(context["token_accounting"].values()) == context["total_tokens"]
    assert "Decision: Preserve public workflow isolation." in serialized


async def _create_plan(slug: str, dependencies: list[str]) -> None:
    content = (
        f"---\ntitle: {slug}\nstatus: PENDING\n"
        f"depends_on: {json.dumps(dependencies)}\n---\n\n# {slug}\n\n"
        "## Goal\n\nVerify public completion.\n"
    )
    result = await call_public_tool(
        "plan", operation="create", title=slug, slug=slug, content=content
    )
    assert result["status"] == "success", result
    registered = await call_public_tool(
        "plan",
        operation="register",
        plan_title=slug,
        description="Verify public completion.",
        plan_file_name=f"{slug}.md",
    )
    assert registered["status"] == "success", registered


async def test_plan_completion_archives_and_unblocks_dependency(
    public_project: Path,
) -> None:
    # Arrange: both documents originate through the published plan tool.
    await _create_plan("foundation", [])
    await _create_plan("dependent", ["foundation"])
    before = await call_public_tool("plan", operation="graph")
    assert "dependent" in cast(dict[str, object], before["blocked"])

    # Act: no fixture-side status rewrite or direct completion helper.
    completed = await call_public_tool(
        "plan",
        operation="complete",
        plan_title="foundation",
        summary="Public completion verified.",
        plan_file_name="foundation.md",
    )
    after = await call_public_tool("plan", operation="graph")

    # Assert: archived DONE nodes satisfy active dependencies.
    assert completed["status"] == "success", completed
    assert completed["plans_unblocked"] == 1
    archive = completed["archive_path"]
    assert isinstance(archive, str)
    archived = Path(archive)
    assert archived.is_relative_to(public_project)
    assert "status: DONE" in archived.read_text(encoding="utf-8")
    assert not (public_project / ".cortex/plans/foundation.md").exists()
    assert "dependent" in cast(list[str], after["ready"])
    assert "dependent" not in cast(dict[str, object], after["blocked"])


async def _quality_gate_outcome() -> dict[str, object]:
    result = await call_public_tool("run_quality_gate")
    while result.get("status") == "running":
        previous = result
        result = await call_public_tool("run_quality_gate")
        if result.get("status") == "running":
            assert result["job_id"] == previous["job_id"], result
            assert result["result_file"] == previous["result_file"], result
    return result


async def test_quality_gate_reports_real_success_and_failure(
    quality_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange / Act: real detached gate executes a one-test Python project.
    monkeypatch.setattr(
        "cortex.tools.execution.pre_commit_zero_arg_tools.QUALITY_GATE_WAIT_SECONDS",
        2.0,
    )
    passed = await _quality_gate_outcome()
    assert passed["preflight_passed"] is True, passed
    assert "tests" in cast(list[str], passed["checks_performed"]), passed

    # Deliberately break behavior, not the tool response or adapter.
    source = quality_project / "src/cortex/smoke_subject.py"
    _ = source.write_text("def answer() -> int:\n    return 0\n", encoding="utf-8")
    failed = await _quality_gate_outcome()

    # Assert: a failed actual assertion cannot be reported as a passing gate.
    assert failed["preflight_passed"] is False, failed
    assert "test_answer" in json.dumps(failed), failed
    assert "failed" in json.dumps(failed).lower(), failed


async def test_file_tool_visibility_preserves_client_boundary(
    public_project: Path,
) -> None:
    # Arrange / Act: exercise the negotiated identity, not a fabricated AuthContext.
    read = await call_public_tool(
        "manage_file", operation="read", file_name="progress.md"
    )
    assert read["status"] == "success"
    assert "Decision: Preserve public workflow isolation." in str(read["content"])
    identity = Implementation(name="untrusted-smoke", version="1")
    async with Client(mcp, client_info=identity) as client:
        tools = await client.list_tools()
        assert "manage_file" not in {tool.name for tool in tools}
        with pytest.raises(ToolError):
            _ = await client.call_tool(
                "manage_file", {"operation": "read", "file_name": "progress.md"}
            )
