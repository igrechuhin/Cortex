"""Tests for run_synapse_script helper extracted from pre_commit_tools suite."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cortex.core.path_resolver import (
    CortexResourceType,
    ProjectResourceType,
    get_cortex_path,
    get_project_path,
    get_venv_bin_path,
)
from cortex.managers.initialization import get_project_root
from cortex.tools.execution.pre_commit_synapse import run_synapse_script


def _install_synapse_parity_script_fixtures(root: Path) -> None:
    scripts_dir = (
        get_cortex_path(root, CortexResourceType.SYNAPSE) / "scripts" / "python"
    )
    scripts_dir.mkdir(parents=True)
    script_path = scripts_dir / "check_formatting_ci_parity.py"
    _ = script_path.write_text("#!/usr/bin/env python3\n")
    get_project_path(root, ProjectResourceType.VENV).mkdir()
    get_venv_bin_path(root).mkdir(parents=True)
    python_bin = get_venv_bin_path(root) / "python"
    _ = python_bin.write_text("")
    python_bin.chmod(0o755)


class TestRunSynapseScript:
    def test_run_synapse_script_when_script_missing_returns_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            result = run_synapse_script(
                root, "python", "check_formatting_ci_parity.py", "format_ci_parity"
            )
            assert result.success is True

    def test_run_synapse_script_check_async_tests_when_script_exists_runs(self) -> None:
        project_root = get_project_root()
        script_path = (
            get_cortex_path(project_root, CortexResourceType.SYNAPSE)
            / "scripts"
            / "python"
            / "check_async_tests.py"
        )
        if not script_path.exists():
            pytest.skip(
                "check_async_tests.py not present (e.g. in minimal tree) (ref: cleanup-skipped-legacy-tests)"
            )
        result = run_synapse_script(
            project_root, "python", "check_async_tests.py", "check_async_tests"
        )
        assert result.check_type == "check_async_tests"

    def test_run_synapse_script_when_script_fails_with_empty_output_uses_exit_code(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _install_synapse_parity_script_fixtures(root)
            with patch(
                "cortex.tools.execution.pre_commit_synapse.subprocess.run"
            ) as mock_run:
                mock_run.return_value = MagicMock(returncode=2, stdout="", stderr="")
                result = run_synapse_script(
                    root, "python", "check_formatting_ci_parity.py", "format_ci_parity"
                )
            assert result.success is False
