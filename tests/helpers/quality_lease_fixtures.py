"""Harmless temporary-root processes for checkout quality-runner regressions."""

# cspell:words pgid getpgrp mkfifo

import json
import os
import shlex
import signal
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from enum import Enum
from multiprocessing.connection import Connection
from multiprocessing.synchronize import Barrier
from pathlib import Path
from types import FrameType
from unittest.mock import patch

from pydantic import BaseModel, Field, ValidationError

from cortex.core.execution_env import ExecutionEnvironment, LocalExecutionEnvironment

_READERS: dict[tuple[Path, str], int] = {}
_WAIT_SECONDS = 8.0
_SWIFT_TEST_TIMEOUT = 3


class ProcessIdentity(BaseModel):
    """IDs belong only to a process launched under this temporary fixture root."""

    pid: int = Field(gt=0)
    pgid: int = Field(gt=0)


class Control(str, Enum):
    RELEASE = "release"
    EXIT_SUPERVISOR = "exit-supervisor"
    RELEASE_SERVER = "release-server"
    ALLOW_WORKER = "allow-worker"
    SWIFT_INTERRUPT = "swift-interrupt"


def prepare_lifetimes(root: Path) -> None:
    for role in ("worker", "descendant"):
        path = root / f"{role}-lifetime.pipe"
        os.mkfifo(path, 0o600)
        _READERS[root, role] = os.open(path, os.O_RDONLY | os.O_NONBLOCK)


def claim_lifetime(root: Path, role: str) -> None:
    # AI: This raw descriptor is deliberately never closed by Python; only process
    # exit closes its writer, so a controller's EOF proves actual kernel exit.
    _ = os.open(root / f"{role}-lifetime.pipe", os.O_WRONLY | os.O_NONBLOCK)
    identity = ProcessIdentity(pid=os.getpid(), pgid=os.getpgrp())
    _publish_identity(root / f"{role}-{identity.pid}-ready.json", identity)


def publish_launch(root: Path, role: str, pid: int, pgid: int) -> None:
    _publish_identity(
        root / f"{role}-{pid}-launched.json", ProcessIdentity(pid=pid, pgid=pgid)
    )


def _publish_identity(path: Path, identity: ProcessIdentity) -> None:
    temporary = path.with_suffix(".tmp")
    _ = temporary.write_text(identity.model_dump_json())
    _ = temporary.replace(path)


def wait_control(root: Path, controls: tuple[Control, ...]) -> Control:
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        for control in controls:
            if (root / control.value).exists():
                return control
        time.sleep(0.01)
    raise TimeoutError("Owned synthetic process exceeded its cooperative deadline")


def request_release(root: Path) -> None:
    for control in Control:
        _ = (root / control.value).write_text("cooperative fixture release")


def lifetime_alive(root: Path, role: str) -> bool:
    try:
        data = os.read(_READERS[root, role], 1)
    except BlockingIOError:
        return True
    if data:
        raise AssertionError("Lifetime channel unexpectedly carried data")
    return False


def _identities(root: Path, role: str) -> tuple[list[ProcessIdentity], set[int]] | None:
    paths = sorted(root.glob(f"{role}-*-*.json"))
    if len(paths) > 32:
        raise AssertionError("Fixture exceeded its owned-process bound")
    identities: dict[int, ProcessIdentity] = {}
    ready: set[int] = set()
    try:
        for path in paths:
            identity = ProcessIdentity.model_validate_json(path.read_text())
            identities[identity.pid] = identity
            if path.name.endswith("-ready.json"):
                ready.add(identity.pid)
    except (OSError, ValidationError):
        return None
    return list(identities.values()), ready


def wait_exit(root: Path, role: str, require_group_gone: bool = True) -> None:
    from cortex.tools.execution.pre_commit_process import reap_detached_workers

    deadline = time.monotonic() + _WAIT_SECONDS
    while time.monotonic() < deadline:
        reap_detached_workers()
        snapshot = _identities(root, role)
        if snapshot is not None and _observed_exit(
            root, role, snapshot, require_group_gone
        ):
            return
        time.sleep(0.01)
    raise AssertionError(
        f"Fixture teardown: {role} did not exit without zombie/group residue"
    )


def _observed_exit(
    root: Path,
    role: str,
    snapshot: tuple[list[ProcessIdentity], set[int]],
    require_group_gone: bool,
) -> bool:
    from cortex.tools.execution.pre_commit_workspace import process_group_alive

    identities, ready = snapshot
    if any(
        identity.pid not in ready and process_group_alive(identity.pgid)
        for identity in identities
    ):
        return False
    if lifetime_alive(root, role):
        return False
    return not require_group_gone or all(
        not process_group_alive(identity.pgid) for identity in identities
    )


def finish_lifetimes(root: Path) -> None:
    request_release(root)
    failures: list[Exception] = []
    try:
        for role in ("descendant", "worker"):
            try:
                wait_exit(root, role)
            except Exception as exc:
                failures.append(exc)
    finally:
        for role in ("worker", "descendant"):
            os.close(_READERS.pop((root, role)))
    if failures:
        raise ExceptionGroup("Cooperative fixture teardown failed", failures)


def launch_stub_worker(
    project_root: Path,
    checks: list[str],
    timeout: int,
    coverage_threshold: float,
    strict_mode: bool,
    include_markdown_lint: bool,
    args_hash: str,
    env: ExecutionEnvironment,
    quality_gate: bool = False,
    test_filter: str | None = None,
) -> Path:
    """Keep the real guarded process launch and replace only the check payload."""
    from cortex.tools.execution.pre_commit_process import (
        pre_commit_result_path,
        publish_started_worker,
        spawn_detached_process,
    )
    from cortex.tools.execution.session_paths import session_dir

    _ = checks, timeout, coverage_threshold
    _ = strict_mode, include_markdown_lint, test_filter
    result_path = pre_commit_result_path(session_dir(project_root), args_hash)
    command = _worker_command(project_root, result_path)
    log = session_dir(project_root) / f"pre_commit_worker_{args_hash}.log"
    pid = spawn_detached_process(command, log, project_root, env)
    publish_launch(project_root, "worker", pid, pid)
    publish_started_worker(result_path, pid, quality_gate)
    return result_path


def _worker_command(root: Path, result_path: Path) -> list[str]:
    return [
        sys.executable,
        # Do not let tests/helpers/types.py shadow the standard library.
        "-P",
        str(Path(__file__).resolve()),
        "worker",
        str(root),
        str(result_path),
    ]


def start_stub(root: Path) -> dict[str, object]:
    """Exercise the actual Cortex start entry point without executing any check."""
    from cortex.tools.execution.pre_commit_detached import start_pre_commit_job_impl

    with patch(
        "cortex.tools.execution.pre_commit_detached.spawn_detached_worker",
        side_effect=launch_stub_worker,
    ):
        return start_pre_commit_job_impl(
            root,
            ["tests"],
            30,
            0.9,
            False,
            True,
            LocalExecutionEnvironment(),
            quality_gate=True,
        )


def run_server(
    root: str, barrier: Barrier | None, connection: Connection, stay: bool = False
) -> None:
    """A separate server process has its own owner even with identical arguments."""
    if barrier is not None:
        _ = barrier.wait(timeout=8)
    connection.send(start_stub(Path(root)))
    if stay:
        _ = wait_control(Path(root), (Control.RELEASE_SERVER,))
    connection.close()


def _wait_release(root: Path) -> None:
    _ = wait_control(root, (Control.RELEASE,))


def _descendant(root: Path) -> None:
    claim_lifetime(root, "descendant")
    _publish_identity(
        root / "descendant.json", ProcessIdentity(pid=os.getpid(), pgid=os.getpgrp())
    )
    if (root / "fixture-mode").read_text() == "swift_timeout_separate_group":
        control = wait_control(root, (Control.SWIFT_INTERRUPT, Control.RELEASE))
        if control is Control.SWIFT_INTERRUPT:
            # AI: Finish cancellation after the original one-second lineage
            # window. The launcher exits independently and has no pipes to drain.
            time.sleep(1.5)
    else:
        _wait_release(root)


def _wait_startup(root: Path, mode: str) -> None:
    if mode == "startup":
        _ = (root / "startup.json").write_text(
            json.dumps({"pid": os.getpid(), "pgid": os.getpgrp()})
        )
        control = wait_control(
            root, (Control.RELEASE, Control.ALLOW_WORKER, Control.EXIT_SUPERVISOR)
        )
        if control != Control.ALLOW_WORKER:
            os._exit(0)


def _spawn_descendant(root: Path, mode: str) -> subprocess.Popen[bytes] | None:
    if mode not in {
        "descendant",
        "escaped_descendant",
        "terminal_descendant",
        "receipt_descendant",
        "timeout_escaped_descendant",
    }:
        return None
    escaped = mode in {"escaped_descendant", "timeout_escaped_descendant"}
    child = subprocess.Popen(
        [sys.executable, "-P", str(Path(__file__).resolve()), "descendant", str(root)],
        close_fds=True,
        start_new_session=escaped,
    )
    publish_launch(
        root,
        "descendant",
        child.pid,
        child.pid if escaped else os.getpgrp(),
    )
    return child


def _worker(root: Path, result_path: Path) -> None:
    from cortex.tools.execution.pre_commit_worker import write_status
    from cortex.tools.execution.pre_commit_workspace import worker_lease

    claim_lifetime(root, "worker")
    mode = (root / "fixture-mode").read_text()
    _wait_startup(root, mode)
    with worker_lease(root):
        write_status(result_path, "running", os.getpid(), True)
        with (root / "executions.txt").open("a") as marker:
            _ = marker.write(f"{os.getpid()}\n")
        child = _spawn_descendant(root, mode)
        _ = (root / "worker.json").write_text(
            json.dumps({"pid": os.getpid(), "pgid": os.getpgrp()})
        )
        if mode.startswith("swift_timeout"):
            _publish_swift_timeout(root, result_path, mode)
            return
        if mode not in {"terminal_descendant", "receipt_descendant"}:
            control = wait_control(root, (Control.RELEASE, Control.EXIT_SUPERVISOR))
            if control == Control.EXIT_SUPERVISOR:
                if mode not in {"receipt", "timeout_escaped_descendant"}:
                    os._exit(71)
            elif child is not None:
                _ = child.wait(timeout=8)
        _publish_worker_receipt(result_path, mode)


def _publish_swift_timeout(root: Path, result_path: Path, mode: str) -> None:
    from cortex.tools.execution.pre_commit_worker import atomic_write

    swift = root / "swift"
    command = shlex.join([sys.executable, "-P", str(Path(__file__).resolve())])
    _ = swift.write_text(f'#!/bin/sh\nexec {command} "$@"\n')
    swift.chmod(0o700)
    _ = (root / "Package.swift").touch()
    with patch.dict(os.environ, {"PATH": f"{root}{os.pathsep}{os.environ['PATH']}"}):
        result = _execute_swift_timeout(root, mode)
    atomic_write(
        result_path,
        {
            "status": "completed",
            "version": 1,
            "pid": os.getpid(),
            "completed_at": time.time(),
            "quality_gate_pending": True,
            "result": {"status": "error", "results": {"tests": result}},
        },
    )


def _execute_swift_timeout(root: Path, mode: str) -> dict[str, object]:
    from cortex.services.framework_adapters.base import CheckResult, TestResult
    from cortex.services.framework_adapters.darwin_process_lineage import (
        DarwinProcessLineage,
    )
    from cortex.services.framework_adapters.swift_adapter import SwiftAdapter
    from cortex.tools.execution.pre_commit_helpers_models import (
        CheckStats,
        PreCommitCheck,
        QualityCheckResult,
    )
    from cortex.tools.execution.pre_commit_pipeline_processors import (
        process_tests_check,
    )

    results: dict[str, CheckResult | TestResult | QualityCheckResult] = {}

    probe = patch.object(
        DarwinProcessLineage,
        "_live_pids",
        side_effect=lambda: _swift_fixture_pids(root, mode),
    )
    with probe, _swift_timeout_after_runner_ready(root):
        process_tests_check(
            SwiftAdapter(str(root)),
            [PreCommitCheck.TESTS],
            _SWIFT_TEST_TIMEOUT,
            0.9,
            results,
            CheckStats(total_errors=0, total_warnings=0),
            test_filter="Synthetic",
        )
    return results["tests"].model_dump()


def _swift_fixture_pids(root: Path, mode: str) -> list[int]:
    if mode == "swift_timeout_unavailable":
        raise PermissionError
    # AI: Keep kernel identity checks for the owned processes. Unrelated
    # processes starting and exiting during parallel tests cannot affect
    # the fixture's inventory.
    pids = [os.getpid()]
    runner = ProcessIdentity.model_validate_json(
        (root / "descendant.json").read_bytes()
    )
    try:
        os.kill(runner.pid, 0)
    except ProcessLookupError:
        return pids
    return [*pids, runner.pid]


@contextmanager
def _swift_timeout_after_runner_ready(root: Path) -> Iterator[None]:
    from cortex.services.framework_adapters import swift_test_process

    communicate = subprocess.Popen[bytes].communicate

    def communicate_after_start(
        process: subprocess.Popen[bytes],
        input: bytes | None = None,
        timeout: float | None = None,
    ) -> tuple[bytes, bytes]:
        if timeout == _SWIFT_TEST_TIMEOUT:
            # AI: Deliver the real subprocess timeout after runner startup so
            # scheduler delays cannot turn a teardown test into a startup test.
            deadline = time.monotonic() + _WAIT_SECONDS
            ready = root / "descendant.json"
            while not ready.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            timeout = 0
        return communicate(process, input, timeout)

    with (
        patch.object(subprocess.Popen, "communicate", communicate_after_start),
        patch.object(swift_test_process, "_INTERRUPT_GRACE_SECONDS", 4),
    ):
        yield


def _swift_test(root: Path) -> None:
    def interrupt(_signum: int, _frame: FrameType | None) -> None:
        (root / Control.SWIFT_INTERRUPT.value).touch()

    _ = signal.signal(signal.SIGINT, interrupt)
    mode = (root / "fixture-mode").read_text()
    role = "swift-orphan" if mode == "swift_timeout_escaped" else "descendant"
    child = _start_swift_fixture_child(
        root, role, detached=mode == "swift_timeout_separate_group"
    )
    if role == "swift-orphan":
        _ = child.wait(timeout=8)
    _ = wait_control(root, (Control.SWIFT_INTERRUPT,))
    if mode in {"swift_timeout", "swift_timeout_unavailable"}:
        (root / Control.RELEASE.value).touch()
        _ = child.wait(timeout=8)


def _start_swift_fixture_child(
    root: Path, role: str, *, detached: bool = False
) -> subprocess.Popen[bytes]:
    child = subprocess.Popen(
        [sys.executable, "-P", str(Path(__file__).resolve()), role, str(root)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=detached,
    )
    if role == "descendant":
        publish_launch(root, role, child.pid, child.pid if detached else os.getpgrp())
    return child


def _publish_worker_receipt(result_path: Path, mode: str) -> None:
    from cortex.tools.execution.pre_commit_worker import atomic_write
    from cortex.tools.execution.pre_commit_workspace import mark_worker_uncertain

    if mode == "timeout_escaped_descendant":
        mark_worker_uncertain()
    atomic_write(
        result_path,
        {
            "version": 1,
            "status": "completed",
            "quality_gate_pending": True,
            "pid": os.getpid(),
            "completed_at": time.time(),
            "result": (
                {
                    "status": "error",
                    "results": {"tests": {"execution_uncertain": True}},
                }
                if mode == "timeout_escaped_descendant"
                else {"status": "success"}
            ),
        },
    )
    if mode in {"receipt", "receipt_descendant", "timeout_escaped_descendant"}:
        # AI: Reproduce a worker interrupted after publishing its result
        # and before recording TERMINAL under the workspace mutex.
        os._exit(71)


if __name__ == "__main__":
    if sys.argv[1] == "worker":
        _worker(Path(sys.argv[2]), Path(sys.argv[3]))
    elif sys.argv[1] == "descendant":
        _descendant(Path(sys.argv[2]))
    elif sys.argv[1] == "test":
        _swift_test(Path.cwd())
    elif sys.argv[1] == "swift-orphan":
        _ = _start_swift_fixture_child(Path(sys.argv[2]), "descendant", detached=True)
    else:
        raise ValueError("Unknown synthetic fixture mode")
    os._exit(0)
