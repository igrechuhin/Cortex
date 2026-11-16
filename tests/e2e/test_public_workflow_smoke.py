"""Bounded PR smoke through the registered MCP tools and resources."""

import asyncio
import json
from pathlib import Path
from typing import cast

import pytest
from fastmcp import Client
from fastmcp.client.transports import FastMCPTransport
from fastmcp.exceptions import ToolError
from mcp.types import Implementation
from tiktoken.registry import get_encoding

from cortex.server import mcp
from tests.e2e.public_workflow_helpers import call_public_tool, public_tool_client
from tests.helpers.spelling_fixtures import (
    SPELLING_CASES,
    cleanup_checker,
    configure_checker,
)
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


async def test_removed_project_access_keeps_file_contract(public_project: Path) -> None:
    async with public_tool_client() as client:
        tools = await client.list_tools()
        manage = next(tool for tool in tools if tool.name == "manage_file")
        assert "project_access" not in json.dumps(manage.inputSchema)
        with pytest.raises(ToolError, match="validation error for call"):
            _ = await call_public_tool(
                "manage_file",
                client=client,
                operation="project_access",
                content='{"action":"read","path":"outside.md"}',
            )
        read = await call_public_tool(
            "manage_file",
            client=client,
            operation="read",
            file_name="projectBrief.md",
        )
        assert read["status"] == "success", read
        assert "Python public workflow smoke" in str(read["content"])
        filed = await call_public_tool(
            "manage_file",
            client=client,
            operation="file_artifact",
            artifact_type="review_report",
            title="File contract check",
            content="# Report",
        )
        assert filed["status"] == "success", filed
        assert Path(str(filed["path"])).parent == public_project / ".cortex" / "reviews"


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
    async with public_tool_client() as client:
        result = await call_public_tool("run_quality_gate", client=client)
        return await _poll_quality_gate(client, result)


async def _poll_quality_gate(
    client: Client[FastMCPTransport], result: dict[str, object]
) -> dict[str, object]:
    owned_handle: tuple[str, str] | None = None
    while result.get("status") == "running":
        if result.get("busy") is True:
            # Detached workers can still be releasing the workspace lease after
            # the previous verdict. A busy response does not disclose a job.
            assert result.get("preflight_passed") is False, result
            assert "job_id" not in result and "result_file" not in result, result
            await asyncio.sleep(0.05)
        else:
            job_id, result_file = result.get("job_id"), result.get("result_file")
            assert isinstance(job_id, str) and job_id, result
            assert isinstance(result_file, str) and result_file, result
            handle = (job_id, result_file)
            if owned_handle is not None:
                assert handle == owned_handle, result
            owned_handle = handle
        result = await call_public_tool("run_quality_gate", client=client)
    return result


async def test_foreign_public_session_waits_without_adopting_job(
    quality_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "cortex.tools.execution.pre_commit_zero_arg_tools.QUALITY_GATE_WAIT_SECONDS",
        0.02,
    )
    async with public_tool_client() as owner, public_tool_client() as foreign:
        running = await call_public_tool("run_quality_gate", client=owner)
        assert running["status"] == "running", running
        busy = await call_public_tool("run_quality_gate", client=foreign)
        assert busy["status"] == "running", busy
        assert busy["busy"] is True, busy
        assert "job_id" not in busy
        assert "result_file" not in busy
        completed = await _poll_quality_gate(owner, running)
    assert completed["preflight_passed"] is True, completed


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
    assert "spelling" in cast(list[str], passed["checks_performed"]), passed

    # Deliberately break behavior, not the tool response or adapter.
    source = quality_project / "src/cortex/smoke_subject.py"
    _ = source.write_text("def answer() -> int:\n    return 0\n", encoding="utf-8")
    failed = await _quality_gate_outcome()

    # Assert: a failed actual assertion cannot be reported as a passing gate.
    assert failed["preflight_passed"] is False, failed
    assert "test_answer" in json.dumps(failed), failed
    assert "failed" in json.dumps(failed).lower(), failed


@pytest.mark.parametrize(("mode", "success", "diagnostic"), SPELLING_CASES)
async def test_quality_gate_preserves_real_spelling_subprocess_verdicts(
    quality_project: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    success: bool,
    diagnostic: str,
) -> None:
    # Arrange: replace only the installed checker boundary, not the detached worker.
    configure_checker(quality_project, mode, monkeypatch)
    monkeypatch.setattr(
        "cortex.tools.execution.pre_commit_zero_arg_tools.QUALITY_GATE_WAIT_SECONDS",
        2.0,
    )
    try:
        # Act: invoke the registered MCP tool through the real job/result path.
        result = await _quality_gate_outcome()
        # Assert: the aggregate public verdict includes the actual spelling result.
        assert result["preflight_passed"] is success, result
        assert "spelling" in cast(list[str], result["checks_performed"]), result
        if not success:
            assert diagnostic in json.dumps(result), result
        if mode in {"timeout", "preflight-timeout"}:
            assert (quality_project / "child-reaped").exists()
    finally:
        cleanup_checker(quality_project)


async def test_quality_gate_fails_when_required_spelling_script_is_missing(
    quality_project: Path,
) -> None:
    # Arrange: remove only the required script from this test-owned project copy.
    script = quality_project / ".cortex/synapse/scripts/python/check_spelling.py"
    script.unlink()
    # Act: keep the registered tool, detached worker, and all other checks real.
    result = await _quality_gate_outcome()
    # Assert: absence must not be reported as a successful skip.
    assert result["preflight_passed"] is False, result
    assert "spelling" in cast(list[str], result["checks_performed"]), result
    assert "Required spelling script not found" in json.dumps(result), result


async def test_quality_gate_reports_real_installed_checker_findings(
    quality_project: Path,
) -> None:
    # Arrange: use the installed checker and unchanged project dictionary.
    source = quality_project / "src/cortex/smoke_subject.py"
    _ = source.write_text(
        # cspell:disable-next-line
        "def answer() -> int:\n    # mispellledwordzz\n    return 42\n",
        encoding="utf-8",
    )
    # Act: the real checker runs inside the real detached public worker.
    result = await _quality_gate_outcome()
    # Assert: source findings reach the public verdict, without breaking behavior.
    assert result["preflight_passed"] is False, result
    assert "spelling" in cast(list[str], result["checks_performed"]), result
    # cspell:disable-next-line
    assert "mispellledwordzz" in json.dumps(result), result


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
