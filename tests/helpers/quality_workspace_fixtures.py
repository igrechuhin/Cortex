"""Shared pytest fixtures for quality workspace ownership and recovery."""

import json
import multiprocessing
import time
from collections.abc import Iterator, Mapping, Sequence
from multiprocessing.connection import Connection
from multiprocessing.process import BaseProcess
from pathlib import Path
from typing import cast

import pytest

from tests.helpers.quality_lease_fixtures import (
    Control,
    finish_lifetimes,
    prepare_lifetimes,
    request_release,
    run_server,
)

_OWNED_SERVERS: list[tuple[BaseProcess, tuple[Connection, Connection]]] = []


@pytest.fixture(autouse=True)
def cooperative_lifetimes(tmp_path: Path) -> Iterator[None]:
    """Pytest attributes teardown failures separately from the test assertion."""
    prepare_lifetimes(tmp_path)
    yield
    request_release(tmp_path)
    failures = _finish_servers()
    try:
        finish_lifetimes(tmp_path)
    except Exception as exc:
        failures.append(exc)
    if failures:
        raise ExceptionGroup("Owned process fixture teardown failed", failures)


def _finish_servers() -> list[Exception]:
    failures: list[Exception] = []
    for server, channels in _OWNED_SERVERS:
        if server.pid is not None:
            server.join(timeout=8)
            if server.is_alive():
                failures.append(
                    AssertionError(
                        "Fixture teardown: owned server did not exit cooperatively"
                    )
                )
        for channel in channels:
            channel.close()
    _OWNED_SERVERS.clear()
    return failures


def prepare_workspace(root: Path, mode: str = "normal") -> None:
    _ = (root / "fixture-mode").write_text(mode)


def wait_for_fixture_json(path: Path) -> dict[str, int]:
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        try:
            return json.loads(path.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            time.sleep(0.01)
    raise AssertionError(f"Synthetic process did not publish {path.name}")


def assert_foreign_busy(result: Mapping[str, object]) -> None:
    assert result["status"] == "running"
    assert result["busy"] is True
    assert result["reason"] == "workspace_occupied"
    assert result["preflight_passed"] is False
    assert "job_id" not in result and "result_file" not in result


def track_servers(
    servers: Sequence[BaseProcess], channels: Sequence[tuple[Connection, Connection]]
) -> None:
    _OWNED_SERVERS.extend(zip(servers, channels, strict=True))


def start_foreign(root: Path) -> dict[str, object]:
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe()
    server = context.Process(target=run_server, args=(str(root), None, child))
    try:
        server.start()
        assert parent.poll(8), "Foreign Cortex fixture did not return its request"
        return cast(dict[str, object], parent.recv())
    finally:
        track_servers([server], [(parent, child)])


def assert_next_foreign_launch(root: Path) -> None:
    _ = (root / "fixture-mode").write_text("normal")
    for name in (Control.RELEASE.value, Control.EXIT_SUPERVISOR.value, "worker.json"):
        (root / name).unlink(missing_ok=True)
    assert start_foreign(root)["status"] == "started"
    _ = wait_for_fixture_json(root / "worker.json")
    assert len((root / "executions.txt").read_text().splitlines()) == 2
