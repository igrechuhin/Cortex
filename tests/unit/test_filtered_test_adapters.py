"""Explicit adapter test selections preserve full-suite defaults."""

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from cortex.services.framework_adapters.python_adapter import PythonAdapter
from cortex.services.framework_adapters.swift_adapter import SwiftAdapter
from cortex.services.framework_adapters.test_selection import (
    selected_pytest_result,
    validate_test_filter,
)


@pytest.mark.parametrize("selection", ["", " ", "a\nb", "a\x00b", "a\tb"])
def test_filter_rejects_empty_and_control_characters(selection: str) -> None:
    with pytest.raises(ValueError, match="test_filter"):
        validate_test_filter(selection)


def test_python_filter_is_one_argv_element_without_global_coverage(
    tmp_path: Path,
) -> None:
    adapter = PythonAdapter(str(tmp_path))
    selection = "central_bank and not slow"
    completed = subprocess.CompletedProcess(["python3"], 0, "2 passed in 0.2s", "")
    with (
        patch.object(adapter, "_get_command", return_value="python3"),
        patch("subprocess.run", return_value=completed) as run,
    ):
        _ = adapter.run_tests(test_filter=selection)
    command = run.call_args.args[0]
    assert command[-4:] == ["-k", selection, "-m", "not slow"]
    assert "--no-cov" in command
    assert not any(arg.startswith("--cov") for arg in command)


def test_python_default_retains_coverage_threshold(tmp_path: Path) -> None:
    adapter = PythonAdapter(str(tmp_path))
    completed = subprocess.CompletedProcess(["python3"], 0, "2 passed in 0.2s", "")
    with (
        patch.object(adapter, "_get_command", return_value="python3"),
        patch.object(adapter, "_pytest_parallel_requested", return_value=False),
        patch("subprocess.run", return_value=completed) as run,
    ):
        _ = adapter.run_tests()
    command = run.call_args.args[0]
    assert "--cov-fail-under=90" in command
    assert "-k" not in command


def test_python_collection_uses_same_selection(tmp_path: Path) -> None:
    adapter = PythonAdapter(str(tmp_path))
    collected = subprocess.CompletedProcess(["python3"], 0, "2 tests collected", "")
    completed = subprocess.CompletedProcess(["python3"], 0, "2 passed in 0.2s", "")
    progress: list[tuple[int, int]] = []
    with (
        patch.object(adapter, "_get_command", return_value="python3"),
        patch("subprocess.run", side_effect=[collected, completed]) as run,
    ):
        _ = adapter.run_tests(
            test_filter="central_bank",
            progress_callback=lambda completed, total: progress.append(
                (completed, total)
            ),
        )
    assert run.call_count == 2
    assert "--collect-only" in run.call_args_list[0].args[0]
    for call in run.call_args_list:
        assert "central_bank" in call.args[0]
        assert "-k" in call.args[0]
    assert progress


def test_selected_python_success_does_not_require_coverage() -> None:
    result = selected_pytest_result("2 passed in 0.2s", 0)
    assert result.success
    assert result.tests_run == 2
    assert result.coverage is None


@pytest.mark.parametrize(
    ("output", "returncode"),
    [("2 passed in 0.2s", 4), ("0 selected", 5), ("1 failed, 1 passed", 1)],
)
def test_selected_python_errors_fail_closed(output: str, returncode: int) -> None:
    assert not selected_pytest_result(output, returncode).success


def test_python_run_passes_expression_without_shell(tmp_path: Path) -> None:
    adapter = PythonAdapter(str(tmp_path))
    completed = subprocess.CompletedProcess(["python3"], 0, "2 passed in 0.2s", "")
    with (
        patch.object(adapter, "_get_command", return_value="python3"),
        patch("subprocess.run", return_value=completed) as run,
    ):
        result = adapter.run_tests(test_filter="central_bank", timeout=9)
    assert result.success
    assert "central_bank" in run.call_args.args[0]
    assert run.call_args.kwargs["timeout"] == 9
    assert "shell" not in run.call_args.kwargs


def test_swift_filter_is_argv_and_does_not_collect_global_coverage(
    tmp_path: Path,
) -> None:
    adapter = SwiftAdapter(str(tmp_path))
    completed = subprocess.CompletedProcess(
        ["swift"], 0, "Executed 2 tests, with 0 failures", ""
    )
    with (
        patch.object(adapter, "has_package_swift", return_value=True),
        patch.object(adapter, "_run_swift", return_value=completed) as run,
        patch.object(adapter, "_log_swift_test_run"),
        patch.object(adapter, "_collect_line_coverage_fraction") as coverage,
    ):
        result = adapter.run_tests(test_filter="CentralBankTests/.*", timeout=9)
    assert run.call_args.args[0] == [
        "test",
        "--no-parallel",
        "--filter",
        "CentralBankTests/.*",
    ]
    coverage.assert_not_called()
    assert result.success
    assert result.coverage is None


def test_swift_filter_rejects_xcode(tmp_path: Path) -> None:
    adapter = SwiftAdapter(str(tmp_path))
    with patch.object(adapter, "has_package_swift", return_value=False):
        with pytest.raises(ValueError, match="Swift Package Manager"):
            _ = adapter.run_tests(test_filter="CentralBankTests")


def test_swift_filter_rejects_malformed_regex(tmp_path: Path) -> None:
    adapter = SwiftAdapter(str(tmp_path))
    with pytest.raises(ValueError, match="regular expression"):
        _ = adapter.run_tests(test_filter="[")


def test_swift_filter_rejects_no_matches(tmp_path: Path) -> None:
    adapter = SwiftAdapter(str(tmp_path))
    completed = subprocess.CompletedProcess(
        ["swift"], 0, "Executed 0 tests, with 0 failures", ""
    )
    with (
        patch.object(adapter, "has_package_swift", return_value=True),
        patch.object(adapter, "_run_swift", return_value=completed),
        patch.object(adapter, "_log_swift_test_run"),
    ):
        result = adapter.run_tests(test_filter="DoesNotExist")
    assert not result.success
    assert "test_filter selected no runnable tests" in result.errors
