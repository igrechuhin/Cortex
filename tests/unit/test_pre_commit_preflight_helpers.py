"""Unit tests for compute_preflight_passed (shared by run_quality_gate())."""

from __future__ import annotations

from typing import cast

from cortex.core.models import JsonDict, ModelDict
from cortex.tools.execution.pre_commit_preflight_helpers import (
    compute_preflight_passed,
)


def test_compute_preflight_passed_success_no_markdown() -> None:
    """Passes when execute succeeds and markdown was not run."""
    result: ModelDict = {"status": "success"}
    assert compute_preflight_passed(result, None) is True


def test_compute_preflight_passed_exec_fails() -> None:
    """Fails when execute reports non-success status."""
    result: ModelDict = {"status": "error"}
    assert compute_preflight_passed(result, None) is False


def test_compute_preflight_passed_markdown_has_errors() -> None:
    """Fails when markdown lint has files_with_errors > 0."""
    exec_ok: ModelDict = {"status": "success"}
    md_bad = cast(
        JsonDict,
        {"status": "success", "files_with_errors": 2, "error_message": None},
    )
    assert compute_preflight_passed(exec_ok, md_bad) is False


def test_compute_preflight_passed_markdown_has_error_message() -> None:
    """Fails when markdown lint has an error_message."""
    exec_ok: ModelDict = {"status": "success"}
    md_err = cast(
        JsonDict,
        {
            "status": "success",
            "files_with_errors": 0,
            "error_message": "CLI not found",
        },
    )
    assert compute_preflight_passed(exec_ok, md_err) is False


def test_compute_preflight_passed_files_with_errors_as_string_zero() -> None:
    """Passes when files_with_errors is str '0' (boundary)."""
    exec_ok: ModelDict = {"status": "success"}
    md_ok = cast(
        JsonDict,
        {"status": "success", "files_with_errors": "0", "error_message": None},
    )
    assert compute_preflight_passed(exec_ok, md_ok) is True


def test_compute_preflight_passed_files_with_errors_as_string_positive() -> None:
    """Fails when files_with_errors is str '3'."""
    exec_ok: ModelDict = {"status": "success"}
    md_bad = cast(
        JsonDict,
        {"status": "success", "files_with_errors": "3", "error_message": None},
    )
    assert compute_preflight_passed(exec_ok, md_bad) is False


def test_compute_preflight_passed_markdown_status_error_fails() -> None:
    """Fails when markdown status is 'error' even if files_with_errors is 0."""
    exec_ok: ModelDict = {"status": "success"}
    md_err = cast(
        JsonDict,
        {"status": "error", "files_with_errors": 0, "error_message": None},
    )
    assert compute_preflight_passed(exec_ok, md_err) is False
