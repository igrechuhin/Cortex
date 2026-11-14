"""Approved job and protocol tests use only temporary harmless calculations."""

import asyncio
import hashlib
import json
import os
import sys
from unittest.mock import patch

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import Implementation, ListRootsResult, Root, TextContent
from pydantic import FileUrl

from cortex.tools.files.project_access.jobs import task_directory
from cortex.tools.files.project_access.models import Request
from cortex.tools.files.project_access.policy import load_access
from cortex.tools.files.project_access.worker import run
from tests.helpers.project_access_fixtures import (
    AccessFixture,
    Response,
    approve,
    call,
    terminal_outcome,
    wait_terminal,
)


@pytest.mark.asyncio
async def test_project_access_job_real_worker_and_duplicate(
    access_fixture: AccessFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FIXTURE_CREDENTIAL", "must-not-be-inherited")
    first = await call(
        access_fixture, action="start", job="prepare", parameters={"figi": "FIGI1"}
    )
    assert first.result.duplicate is False
    terminal = await wait_terminal(access_fixture)
    assert terminal_outcome(terminal) == "succeeded"
    second = await call(
        access_fixture, action="start", job="prepare", parameters={"figi": "FIGI1"}
    )
    assert second.result.duplicate is True
    result = await call(
        access_fixture,
        action="read_output",
        job="prepare",
        parameters={"figi": "FIGI1"},
        path="profile.txt",
    )
    assert result.result.text == "Original profile: FIGI1"
    env = await call(
        access_fixture,
        action="read_output",
        job="prepare",
        parameters={"figi": "FIGI1"},
        path="environment.txt",
    )
    assert env.result.text == "absent"
    run(access_fixture.root, first.result.task)


@pytest.mark.parametrize(
    "kind", ["unknown", "parameter", "tampered", "missing_output", "argv"]
)
@pytest.mark.asyncio
async def test_project_access_job_denials(
    access_fixture: AccessFixture, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    job = "prepare"
    parameters = {"figi": "FIGI1"}
    if kind == "unknown":
        job = "shell"
    elif kind == "parameter":
        parameters = {"figi": "FIGI1; echo forbidden"}
    elif kind == "tampered":
        _ = (access_fixture.root / "prepare.py").write_text("raise SystemExit(99)")
    elif kind == "missing_output":
        access_fixture.policy.jobs[job].arguments = []
        approve(access_fixture, monkeypatch)
    arguments: dict[str, object] = {
        "action": "start",
        "job": job,
        "parameters": parameters,
    }
    if kind == "argv":
        arguments["argv"] = ["sh", "-c", "forbidden"]
    assert (await call(access_fixture, **arguments)).status == "error"
    assert list((access_fixture.root / "artifacts").iterdir()) == []


@pytest.mark.asyncio
async def test_project_access_output_placeholder_is_reserved(
    access_fixture: AccessFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    job = access_fixture.policy.jobs["prepare"]
    job.parameters = {"output_directory": ["FIGI1"]}
    job.arguments = ["{output_directory}"]
    approve(access_fixture, monkeypatch)
    result = await call(
        access_fixture,
        action="start",
        job="prepare",
        parameters={"output_directory": "FIGI1"},
    )
    assert result.status == "error"
    assert list((access_fixture.root / "artifacts").iterdir()) == []


@pytest.mark.asyncio
async def test_project_access_uncertain_launch_never_retries(
    access_fixture: AccessFixture,
) -> None:
    with patch(
        "cortex.tools.files.project_access.jobs.subprocess.Popen", side_effect=OSError
    ):
        result = await call(
            access_fixture, action="start", job="prepare", parameters={"figi": "FIGI1"}
        )
    assert result.status == "error"
    retry = await call(
        access_fixture, action="start", job="prepare", parameters={"figi": "FIGI1"}
    )
    assert retry.result.duplicate is True
    assert terminal_outcome(retry.result) == "launch_failed"


@pytest.mark.parametrize(
    "source,outcome",
    [("raise SystemExit(7)", "failed"), ("import time; time.sleep(20)", "timed_out")],
)
@pytest.mark.asyncio
async def test_project_access_job_failure_and_timeout(
    access_fixture: AccessFixture,
    monkeypatch: pytest.MonkeyPatch,
    source: str,
    outcome: str,
) -> None:
    _ = (access_fixture.root / "prepare.py").write_text(source)
    job = access_fixture.policy.jobs["prepare"]
    job.sha256 = hashlib.sha256(source.encode()).hexdigest()
    job.timeout = 1
    approve(access_fixture, monkeypatch)
    _ = await call(
        access_fixture, action="start", job="prepare", parameters={"figi": "FIGI1"}
    )
    assert terminal_outcome(await wait_terminal(access_fixture)) == outcome


@pytest.mark.asyncio
async def test_project_access_concurrent_start_is_bounded(
    access_fixture: AccessFixture,
) -> None:
    results = await asyncio.gather(
        *[
            call(
                access_fixture,
                action="start",
                job="prepare",
                parameters={"figi": "FIGI1"},
            )
            for _ in range(5)
        ]
    )
    assert sum(r.result.duplicate is False for r in results) == 1
    assert terminal_outcome(await wait_terminal(access_fixture)) == "succeeded"


@pytest.mark.asyncio
@pytest.mark.timeout(60)
async def test_project_access_published_mcp_protocol(
    access_fixture: AccessFixture,
) -> None:
    async def roots(context: object) -> ListRootsResult:
        _ = context
        return ListRootsResult(roots=[Root(uri=FileUrl(access_fixture.root.as_uri()))])

    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "cortex.main"],
        cwd=str(access_fixture.root),
        env={
            **os.environ,
            "CORTEX_SKIP_SYNAPSE_UPDATE": "1",
            "CORTEX_USE_FALLBACK_ROOT": "0",
        },
    )
    async with stdio_client(parameters) as (reader, writer):
        async with ClientSession(
            reader,
            writer,
            list_roots_callback=roots,
            client_info=Implementation(name="codex-fixture", version="1"),
        ) as client:
            await exercise_protocol(client)


async def exercise_protocol(client: ClientSession) -> None:
    _ = await client.initialize()
    inventory = await client.list_tools()
    assert len(inventory.tools) == 14
    tool = next(t for t in inventory.tools if t.name == "manage_file")
    assert "project_access" in json.dumps(tool.inputSchema)
    response = await client.call_tool(
        "manage_file",
        {
            "operation": "project_access",
            "content": '{"action":"read","path":"contract.md"}',
        },
    )
    assert not response.isError
    data = Response.model_validate_json(
        "".join(c.text for c in response.content if isinstance(c, TextContent))
    )
    assert data.status == "success"
    assert data.result.text == "Full original contract: αβγ\n"


@pytest.mark.asyncio
async def test_project_access_output_paths_are_contained(
    access_fixture: AccessFixture,
) -> None:
    started = await call(
        access_fixture, action="start", job="prepare", parameters={"figi": "FIGI1"}
    )
    _ = await wait_terminal(access_fixture)
    output = access_fixture.root / started.result.task / "output"
    (output / "alias.txt").symlink_to(access_fixture.root / "contract.md")
    for path in ("../request.json", ".env", "alias.txt"):
        response = await call(
            access_fixture,
            action="read_output",
            job="prepare",
            parameters={"figi": "FIGI1"},
            path=path,
        )
        assert response.status == "error"


@pytest.mark.asyncio
async def test_project_access_empty_reservation_never_launches(
    access_fixture: AccessFixture,
) -> None:
    request = Request.model_validate_json(
        '{"action":"start","job":"prepare","parameters":{"figi":"FIGI1"}}'
    )
    task = task_directory(load_access(access_fixture.root), request)
    (access_fixture.root / task).mkdir()
    with patch("cortex.tools.files.project_access.jobs.subprocess.Popen") as spawn:
        response = await call(access_fixture, **request.model_dump(mode="json"))
        spawn.assert_not_called()
    assert response.result.duplicate is True
    assert response.result.state == "reserved_or_running"


@pytest.mark.asyncio
async def test_project_access_invalid_status_does_not_echo_content(
    access_fixture: AccessFixture,
) -> None:
    request = Request.model_validate_json(
        '{"action":"status","job":"prepare","parameters":{"figi":"FIGI1"}}'
    )
    task = access_fixture.root / task_directory(
        load_access(access_fixture.root), request
    )
    task.mkdir()
    _ = (task / "terminal.json").write_text('{"outcome":"fixture-sensitive-value"}')
    response = await call(access_fixture, **request.model_dump(mode="json"))
    assert response.status == "error"
    assert "fixture-sensitive-value" not in response.model_dump_json()
