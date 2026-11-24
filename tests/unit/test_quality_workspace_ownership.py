"""Owned retries and foreign occupancy across synthetic Cortex server processes."""

# cspell:words pgid waitid WEXITED WNOWAIT WNOHANG

import asyncio
import json
import multiprocessing
import os
import time
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from cortex.core.context_logging import MCPContext
from cortex.core.execution_env import LocalExecutionEnvironment
from cortex.tools.execution.pre_commit_detached import (
    find_running_job,
)
from cortex.tools.execution.pre_commit_ownership import (
    current_owner,
    owned_request_id,
    request_owner,
)
from cortex.tools.execution.pre_commit_quality_gate_job import run_bounded_phase_a
from cortex.tools.execution.pre_commit_workspace import (
    LeaseState,
    WorkspaceBusy,
    WorkspaceLease,
    busy_response,
    process_group_alive,
    workspace_lease,
)
from cortex.tools.execution.session_paths import session_dir
from tests.helpers.quality_lease_fixtures import (
    Control,
    launch_stub_worker,
    lifetime_alive,
    request_release,
    run_server,
    start_stub,
    wait_exit,
)
from tests.helpers.quality_workspace_fixtures import (
    assert_foreign_busy,
    assert_next_foreign_launch,
    prepare_workspace,
    start_foreign,
    track_servers,
    wait_for_fixture_json,
)
from tests.helpers.quality_workspace_fixtures import (
    cooperative_lifetimes as cooperative_lifetimes,
)


def _cleanup(root: Path) -> None:
    request_release(root)


def test_same_owner_retry_returns_one_current_run(tmp_path: Path) -> None:
    prepare_workspace(tmp_path)
    try:
        first = start_stub(tmp_path)
        _ = wait_for_fixture_json(tmp_path / "worker.json")
        second = start_stub(tmp_path)

        assert first["status"] == "started"
        assert first["job_id"] == second["job_id"]
        assert "busy" not in second
        assert second["status"] in {"running", "already_running"}
        assert len((tmp_path / "executions.txt").read_text().splitlines()) == 1
    finally:
        _cleanup(tmp_path)


@pytest.mark.parametrize("matching_name", [False, True])
def test_foreign_running_envelope_never_returns_private_handle(
    tmp_path: Path, matching_name: bool
) -> None:
    request = owned_request_id("synthetic-arguments")
    name = request if matching_name else "f" * 12
    path = session_dir(tmp_path) / f"pre_commit_result_{name}.json"
    _ = path.write_text(
        json.dumps({"status": "running", "pid": os.getpid(), "owner": "foreign"})
    )

    result = find_running_job(tmp_path, path)

    assert result is not None
    assert_foreign_busy(result)
    assert "foreign" not in json.dumps(result)


def test_two_server_processes_atomically_start_only_one_worker(tmp_path: Path) -> None:
    prepare_workspace(tmp_path)
    context = multiprocessing.get_context("spawn")
    barrier = context.Barrier(2)
    channels = [context.Pipe() for _ in range(2)]
    servers = [
        context.Process(target=run_server, args=(str(tmp_path), barrier, child))
        for _, child in channels
    ]
    try:
        for server in servers:
            server.start()
        outcomes: list[dict[str, object]] = []
        for parent, _ in channels:
            assert parent.poll(10)
            outcomes.append(cast(dict[str, object], parent.recv()))
        _ = wait_for_fixture_json(tmp_path / "worker.json")

        assert sum(result["status"] == "started" for result in outcomes) == 1
        assert_foreign_busy(
            next(result for result in outcomes if result["status"] != "started")
        )
        assert len((tmp_path / "executions.txt").read_text().splitlines()) == 1
        assert_foreign_busy(start_stub(tmp_path))
    finally:
        track_servers(servers, channels)
        _cleanup(tmp_path)


@pytest.mark.parametrize("mode", ["descendant", "escaped_descendant"])
def test_worker_death_keeps_live_test_descendant_guarded(
    tmp_path: Path, mode: str
) -> None:
    prepare_workspace(tmp_path, mode)
    try:
        _ = start_stub(tmp_path)
        _ = wait_for_fixture_json(tmp_path / "worker.json")
        _ = wait_for_fixture_json(tmp_path / "descendant.json")
        _ = (tmp_path / Control.EXIT_SUPERVISOR.value).write_text(
            "cooperative supervisor exit"
        )
        wait_exit(tmp_path, "worker", require_group_gone=False)
        assert lifetime_alive(tmp_path, "descendant")

        assert_foreign_busy(start_foreign(tmp_path))
        assert len((tmp_path / "executions.txt").read_text().splitlines()) == 1
        _ = (tmp_path / Control.RELEASE.value).write_text("release descendant")
        wait_exit(tmp_path, "descendant")
        # AI: Exited fixtures do not authorize clearing abnormal RUNNING uncertainty.
        assert_foreign_busy(start_foreign(tmp_path))
    finally:
        _cleanup(tmp_path)


def test_terminal_result_does_not_release_live_group_descendant(tmp_path: Path) -> None:
    prepare_workspace(tmp_path, "terminal_descendant")
    try:
        _ = start_stub(tmp_path)
        _ = wait_for_fixture_json(tmp_path / "worker.json")
        _ = wait_for_fixture_json(tmp_path / "descendant.json")
        wait_exit(tmp_path, "worker", require_group_gone=False)

        assert lifetime_alive(tmp_path, "descendant")
        assert_foreign_busy(start_foreign(tmp_path))
        assert len((tmp_path / "executions.txt").read_text().splitlines()) == 1
        _ = (tmp_path / Control.RELEASE.value).write_text("release descendant")
        wait_exit(tmp_path, "descendant")
        wait_exit(tmp_path, "worker")
        assert_next_foreign_launch(tmp_path)
    finally:
        _cleanup(tmp_path)


@pytest.mark.parametrize("mode", ["normal", "startup"])
def test_server_death_does_not_release_worker_lease(tmp_path: Path, mode: str) -> None:
    prepare_workspace(tmp_path, mode)
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe()
    server = context.Process(target=run_server, args=(str(tmp_path), None, child, True))
    try:
        server.start()
        assert parent.poll(10)
        assert parent.recv()["status"] == "started"
        _ = wait_for_fixture_json(
            tmp_path / ("startup.json" if mode == "startup" else "worker.json")
        )
        _ = (tmp_path / Control.RELEASE_SERVER.value).write_text(
            "cooperative server exit"
        )
        server.join(timeout=8)
        assert not server.is_alive()

        assert_foreign_busy(start_foreign(tmp_path))
        if mode == "normal":
            assert len((tmp_path / "executions.txt").read_text().splitlines()) == 1
        else:
            assert not (tmp_path / "executions.txt").exists()
    finally:
        track_servers([server], [(parent, child)])
        _cleanup(tmp_path)


@pytest.mark.asyncio
async def test_cancelled_waiter_does_not_release_detached_worker(
    tmp_path: Path,
) -> None:
    prepare_workspace(tmp_path)
    with patch(
        "cortex.tools.execution.pre_commit_detached.spawn_detached_worker",
        side_effect=launch_stub_worker,
    ):
        waiter = asyncio.create_task(
            run_bounded_phase_a(
                tmp_path, 30, 0.9, False, None, LocalExecutionEnvironment(), 10
            )
        )
        try:
            _ = await asyncio.to_thread(wait_for_fixture_json, tmp_path / "worker.json")
            _ = waiter.cancel()
            with pytest.raises(asyncio.CancelledError):
                await waiter

            with pytest.raises(WorkspaceBusy):
                with workspace_lease(tmp_path, "b" * 12):
                    pytest.fail("A cancelled waiter released its live worker")
            assert len((tmp_path / "executions.txt").read_text().splitlines()) == 1
        finally:
            _ = waiter.cancel()
            _cleanup(tmp_path)


def test_failed_spawn_leaves_startup_lease_reusable(tmp_path: Path) -> None:
    prepare_workspace(tmp_path)
    with patch(
        "cortex.tools.execution.pre_commit_process.subprocess.Popen",
        side_effect=OSError("synthetic spawn failure"),
    ):
        with pytest.raises(OSError, match="synthetic spawn failure"):
            _ = start_stub(tmp_path)
    try:
        result = start_stub(tmp_path)
        _ = wait_for_fixture_json(tmp_path / "worker.json")
        assert result["status"] == "started"
    finally:
        _cleanup(tmp_path)


def test_normal_terminal_exit_permits_next_request(tmp_path: Path) -> None:
    prepare_workspace(tmp_path)
    try:
        # Exercise request-bound reaping if the background watcher could not start.
        with patch("cortex.tools.execution.pre_commit_process._watch_detached_worker"):
            _ = start_stub(tmp_path)
        worker = wait_for_fixture_json(tmp_path / "worker.json")
        _ = (tmp_path / "release").write_text("released")
        # Observe the child exit without consuming it. A retry would hide the
        # bug because the unsuccessful first request reaps in its busy handler.
        deadline = time.monotonic() + 8
        flags = os.WEXITED | os.WNOWAIT | os.WNOHANG
        while os.waitid(os.P_PID, worker["pid"], flags) is None:
            assert time.monotonic() < deadline, "Synthetic worker did not exit"
            time.sleep(0.01)
        assert process_group_alive(worker["pgid"])
        outcome = start_stub(tmp_path)
        assert outcome["status"] == "completed"
        assert not process_group_alive(worker["pgid"])
        assert len((tmp_path / "executions.txt").read_text().splitlines()) == 1
    finally:
        _cleanup(tmp_path)


def test_idle_owner_reaps_before_foreign_request(tmp_path: Path) -> None:
    prepare_workspace(tmp_path)
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe()
    server = context.Process(target=run_server, args=(str(tmp_path), None, child, True))
    try:
        server.start()
        assert parent.poll(8), "Owner server did not launch the fixture worker"
        assert parent.recv()["status"] == "started"
        _ = wait_for_fixture_json(tmp_path / "worker.json")
        _ = (tmp_path / Control.RELEASE.value).write_text("release worker only")
        # This process cannot reap the foreign server's child.
        wait_exit(tmp_path, "worker", require_group_gone=False)
        assert server.is_alive()
        wait_exit(tmp_path, "worker")
        assert server.is_alive()
        assert_next_foreign_launch(tmp_path)
    finally:
        track_servers([server], [(parent, child)])
        _cleanup(tmp_path)


def test_legacy_dead_supervisor_with_live_group_remains_busy(tmp_path: Path) -> None:
    prepare_workspace(tmp_path, "descendant")
    try:
        first = start_stub(tmp_path)
        worker = wait_for_fixture_json(tmp_path / "worker.json")
        _ = wait_for_fixture_json(tmp_path / "descendant.json")
        _ = (tmp_path / Control.EXIT_SUPERVISOR.value).write_text(
            "cooperative supervisor exit"
        )
        wait_exit(tmp_path, "worker", require_group_gone=False)
        # AI: Model an old detached worker without the new durable lease/owner fields.
        (session_dir(tmp_path) / "quality-worker-lease.json").unlink()
        path = session_dir(tmp_path) / f"pre_commit_result_{first['job_id']}.json"
        _ = path.write_text(json.dumps({"status": "running", "pid": worker["pid"]}))

        assert lifetime_alive(tmp_path, "descendant")
        assert_foreign_busy(start_foreign(tmp_path))
        assert len((tmp_path / "executions.txt").read_text().splitlines()) == 1
        _ = (tmp_path / Control.RELEASE.value).write_text("release descendant")
        wait_exit(tmp_path, "descendant")
        wait_exit(tmp_path, "worker")
        assert_next_foreign_launch(tmp_path)
    finally:
        _cleanup(tmp_path)


def test_failed_publication_does_not_release_spawned_worker(tmp_path: Path) -> None:
    prepare_workspace(tmp_path)
    try:
        with patch(
            "cortex.tools.execution.pre_commit_process.publish_started_worker",
            side_effect=OSError("synthetic publication failure"),
        ):
            with pytest.raises(OSError, match="synthetic publication failure"):
                _ = start_stub(tmp_path)
        _ = wait_for_fixture_json(tmp_path / "worker.json")

        with pytest.raises(WorkspaceBusy):
            with workspace_lease(tmp_path, "a" * 12):
                pytest.fail("Publication failure released its spawned worker")
    finally:
        _cleanup(tmp_path)


@pytest.mark.parametrize("state", [LeaseState.RUNNING, LeaseState.TERMINAL])
def test_missing_process_group_in_worker_lease_is_rejected(state: LeaseState) -> None:
    with pytest.raises(ValidationError, match="process group"):
        _ = WorkspaceLease(owner=current_owner(), request_id="d" * 12, state=state)


def test_malformed_durable_record_fails_closed(tmp_path: Path) -> None:
    _ = (session_dir(tmp_path) / "quality-worker-lease.json").write_text("not-json")
    with pytest.raises(WorkspaceBusy):
        with workspace_lease(tmp_path, "e" * 12):
            pytest.fail("Malformed lease was ignored")


def test_busy_response_never_claims_a_gate_verdict() -> None:
    assert_foreign_busy(busy_response())


@pytest.mark.asyncio
async def test_distinct_mcp_sessions_in_one_server_do_not_share_ownership(
    tmp_path: Path,
) -> None:
    prepare_workspace(tmp_path)
    first_ctx = MagicMock(spec=MCPContext)
    first_ctx.session_id = "synthetic-first-session"
    second_ctx = MagicMock(spec=MCPContext)
    second_ctx.session_id = "synthetic-second-session"
    with patch(
        "cortex.tools.execution.pre_commit_detached.spawn_detached_worker",
        side_effect=launch_stub_worker,
    ):
        try:
            first = await run_bounded_phase_a(
                tmp_path, 30, 0.9, False, first_ctx, LocalExecutionEnvironment(), 0.03
            )
            _ = await asyncio.to_thread(wait_for_fixture_json, tmp_path / "worker.json")
            foreign = await run_bounded_phase_a(
                tmp_path, 30, 0.9, False, second_ctx, LocalExecutionEnvironment(), 0.03
            )
            own_retry = await run_bounded_phase_a(
                tmp_path, 30, 0.9, False, first_ctx, LocalExecutionEnvironment(), 0.03
            )

            assert first["job_id"] == own_retry["job_id"]
            assert_foreign_busy(foreign)
            assert len((tmp_path / "executions.txt").read_text().splitlines()) == 1
        finally:
            _cleanup(tmp_path)


def test_modern_stdio_quality_owner_survives_new_request_connections() -> None:
    first = MagicMock(spec=MCPContext)
    first.transport = "stdio"
    first.session.protocol_version = "2026-07-28"
    first.session_id = "first connection"
    second = MagicMock(spec=MCPContext)
    second.transport = "stdio"
    second.session.protocol_version = "2026-07-28"
    second.session_id = "second connection"

    with request_owner(first):
        owner = current_owner()
    with request_owner(second):
        assert current_owner() == owner


def test_modern_http_quality_owner_requires_legacy_session() -> None:
    ctx = MagicMock(spec=MCPContext)
    ctx.transport = "streamable-http"
    ctx.session.protocol_version = "2026-07-28"

    with pytest.raises(ValueError, match="legacy MCP session"), request_owner(ctx):
        pytest.fail(
            "An HTTP request without a session cannot adopt a detached quality job"
        )
