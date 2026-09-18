"""Unit tests for execute_all_checks, the shared pre-commit check-execution engine.

execute_all_checks (pre_commit_tools_run_helpers.py) is invoked by the detached
pre-commit worker behind run_quality_gate()/autofix(). These tests exercise it
directly with a stub adapter instead of through any specific MCP tool wrapper.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from cortex.core.path_resolver import ProjectResourceType, get_project_path
from cortex.services.framework_adapters.base import CheckResult, TestResult
from cortex.tools.execution.pre_commit_helpers_models import (
    DEFAULT_CHECKS,
    PreCommitCheck,
)
from cortex.tools.execution.pre_commit_tools_run_helpers import execute_all_checks

_DEFAULT_CHECKS_NAMES_EXPECTED = frozenset(
    (
        "fix_errors",
        "format",
        "synapse_format",
        "synapse_lint",
        "type_check",
        "quality",
        "tests",
    )
)


def _minimal_python_project(project_root: Path) -> None:
    _ = (project_root / "pyproject.toml").write_text("[project]\nname = 'test'")
    get_project_path(project_root, ProjectResourceType.VENV).mkdir()


def _green_adapter(project_root: Path) -> MagicMock:
    """Adapter stub whose checks all succeed."""
    adapter = MagicMock()
    adapter.project_root = project_root
    mock_result = CheckResult(
        check_type="test",
        success=True,
        output="Success",
        errors=[],
        warnings=[],
        files_modified=[],
    )
    adapter.fix_errors.return_value = mock_result
    adapter.format_code.return_value = mock_result
    adapter.type_check.return_value = mock_result
    adapter.lint_code.return_value = mock_result
    adapter.run_tests.return_value = TestResult(
        success=True,
        tests_run=10,
        tests_passed=10,
        tests_failed=0,
        pass_rate=1.0,
        coverage=0.95,
        output="All tests passed",
        errors=[],
    )
    return adapter


def test_default_checks_all_run_and_succeed() -> None:
    """DEFAULT_CHECKS executes the standard 7-check set and all succeed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        _minimal_python_project(project_root)
        adapter = _green_adapter(project_root)
        results, stats = execute_all_checks(
            adapter,
            "python",
            DEFAULT_CHECKS,
            strict_mode=False,
            timeout=300,
            coverage_threshold=0.9,
        )
    assert set(stats.checks_performed) == _DEFAULT_CHECKS_NAMES_EXPECTED
    assert stats.total_errors == 0
    assert results["fix_errors"].success is True
    assert results["tests"].success is True


@pytest.mark.parametrize(
    "check",
    [
        PreCommitCheck.FORMAT_CI_PARITY,
        PreCommitCheck.TEST_NAMING,
        PreCommitCheck.CHECK_ASYNC_TESTS,
    ],
)
def test_script_based_check_skipped_when_synapse_script_missing(
    check: PreCommitCheck,
) -> None:
    """format_ci_parity/test_naming/check_async_tests skip cleanly with no synapse script."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        _minimal_python_project(project_root)
        adapter = _green_adapter(project_root)
        results, stats = execute_all_checks(
            adapter,
            "python",
            [check],
            strict_mode=False,
            timeout=300,
            coverage_threshold=0.9,
        )
    assert check.value in stats.checks_performed
    result = results[check.value]
    assert result.success is True
    assert "skipped" in str(result.output)
