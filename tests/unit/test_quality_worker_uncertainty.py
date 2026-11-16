"""Authored lifetime regressions using mocked execution only; no process signals."""

# cspell:words pgid

import argparse
import subprocess
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cortex.services.framework_adapters.base import (
    FrameworkAdapter,
)
from cortex.services.framework_adapters.base import (
    TestResult as AdapterTestResult,
)
from cortex.services.framework_adapters.python_adapter import PythonAdapter
from cortex.services.framework_adapters.swift_adapter import SwiftAdapter
from cortex.tools.execution import pre_commit_fix_worker as fixer
from cortex.tools.execution import pre_commit_worker as worker
from cortex.tools.execution.pre_commit_helpers_models import CheckStats, PreCommitCheck
from cortex.tools.execution.pre_commit_ownership import current_owner
from cortex.tools.execution.pre_commit_pipeline_processors import process_tests_check
from cortex.tools.execution.pre_commit_workspace import (
    LEASE_FD_ENV,
    LeaseState,
    WorkspaceLease,
    mark_worker_uncertain,
    worker_lease,
)


def _result(uncertain: bool = False) -> AdapterTestResult:
    return AdapterTestResult(
        success=False,
        execution_uncertain=uncertain,
        tests_run=1,
        tests_passed=0,
        tests_failed=1,
        pass_rate=0.0,
        coverage=None,
        output="synthetic assertion failure",
        errors=["assertion"],
    )


@contextmanager
def _observe_exit(exits: list[type[BaseException] | None]) -> Iterator[None]:
    try:
        yield
    except BaseException as exc:
        exits.append(type(exc))
        raise
    else:
        exits.append(None)


@pytest.mark.parametrize(
    "entry,parser,executor,lease",
    [
        (
            worker.main,
            "pre_commit_worker._parse_worker_args",
            "pre_commit_worker._execute_worker",
            "pre_commit_worker.worker_lease",
        ),
        (
            fixer.main,
            "pre_commit_fix_worker._parse_fix_worker_args",
            "pre_commit_fix_worker._execute_worker",
            "pre_commit_fix_worker.worker_lease",
        ),
    ],
)
def test_unexpected_handled_worker_error_exits_inside_lease(
    tmp_path: Path,
    entry: Callable[[], None],
    parser: str,
    executor: str,
    lease: str,
) -> None:
    exits: list[type[BaseException] | None] = []
    prefix = "cortex.tools.execution."
    with (
        patch(
            prefix + parser, return_value=argparse.Namespace(project_root=str(tmp_path))
        ),
        patch(prefix + executor, return_value=True),
        patch(prefix + lease, return_value=_observe_exit(exits)),
        pytest.raises(SystemExit),
    ):
        entry()
    assert exits == [SystemExit]


@pytest.mark.parametrize("code,uncertain", [(0, False), (1, False), (-9, True)])
def test_only_signal_end_marks_completed_process_uncertain(
    code: int, uncertain: bool
) -> None:
    result = _result().with_process_returncode(code)
    assert result.execution_uncertain is uncertain


@pytest.mark.parametrize(
    "outcome,uncertain",
    [("timeout", True), ("signal", True), ("assertion", False), ("missing", False)],
)
def test_python_test_command_distinguishes_interruption_from_normal_failure(
    tmp_path: Path,
    outcome: str,
    uncertain: bool,
) -> None:
    completed = subprocess.CompletedProcess(
        [], -9 if outcome == "signal" else 1, "1 failed in 0.1s", ""
    )
    error = (
        subprocess.TimeoutExpired("synthetic", 1)
        if outcome == "timeout"
        else (
            FileNotFoundError("synthetic missing tool")
            if outcome == "missing"
            else None
        )
    )
    with patch(
        "cortex.services.framework_adapters.python_adapter.subprocess.run",
        return_value=completed,
        side_effect=error,
    ):
        result = PythonAdapter(str(tmp_path)).run_tests(
            test_filter="synthetic", timeout=1
        )
    assert result.execution_uncertain is uncertain


def test_swift_started_test_timeout_is_uncertain(tmp_path: Path) -> None:
    _ = (tmp_path / "Package.swift").write_text("// synthetic package marker\n")
    with patch(
        "cortex.services.framework_adapters.swift_adapter.SwiftAdapter._run_swift",
        side_effect=subprocess.TimeoutExpired("synthetic swift test", 1),
    ):
        result = SwiftAdapter(str(tmp_path)).run_tests(
            test_filter="SyntheticTests", timeout=1
        )
    assert result.execution_uncertain is True


@pytest.mark.parametrize("uncertain", [False, True])
def test_pipeline_blocks_only_uncertain_test_completion(uncertain: bool) -> None:
    result = _result(uncertain)
    adapter = MagicMock(spec=FrameworkAdapter)
    adapter.run_tests.return_value = result
    stats = CheckStats(total_errors=0, total_warnings=0)
    with patch(
        "cortex.tools.execution.pre_commit_workspace.mark_worker_uncertain"
    ) as marked:
        process_tests_check(adapter, [PreCommitCheck.TESTS], 1, 0.9, {}, stats)
    assert marked.call_count == int(uncertain)
    assert len(result.errors) == 1 + int(uncertain)
    assert result.success is False


@pytest.mark.parametrize("uncertain", [False, True])
def test_lease_retains_uncertainty_without_claiming_descendant_completion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    uncertain: bool,
) -> None:
    monkeypatch.setenv(LEASE_FD_ENV, "23")
    record = WorkspaceLease(
        owner=current_owner(), request_id="a" * 12, state=LeaseState.RUNNING, pgid=123
    )
    prefix = "cortex.tools.execution.pre_commit_workspace."
    with (
        patch(prefix + "_adopt_worker_lease", return_value=record),
        patch(prefix + "_write_record") as written,
        patch(prefix + "os.close"),
    ):
        with worker_lease(tmp_path):
            if uncertain:
                mark_worker_uncertain()
    assert written.call_count == int(not uncertain)
    assert record.state == (LeaseState.RUNNING if uncertain else LeaseState.TERMINAL)
