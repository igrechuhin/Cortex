"""Tests for the run_synapse_script helper."""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
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
from tests.helpers.spelling_fixtures import (
    SPELLING_CASES,
    cleanup_checker,
    configure_checker,
    install_spelling_script,
)


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


@pytest.mark.parametrize(("mode", "success", "diagnostic"), SPELLING_CASES)
def test_real_spelling_script_verdict_reaches_consumer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    success: bool,
    diagnostic: str,
) -> None:
    # Arrange: only the external executable boundary is controlled.
    _ = install_spelling_script(tmp_path)
    configure_checker(tmp_path, mode, monkeypatch)
    try:
        # Act: run the real script through the production aggregate consumer.
        result = run_synapse_script(tmp_path, "python", "check_spelling.py", "spelling")
        # Assert: operational failures cannot become successful finding counts.
        assert result.success is success, result
        assert diagnostic in result.output, result
        assert bool(result.errors) is not success
        assert "file(s)" not in result.output
        if mode in {"findings", "cli", "eacces", "transport"}:
            assert "checker stderr preserved" in result.output
        if mode == "preflight":
            assert "preflight stderr preserved" in result.output
    finally:
        cleanup_checker(tmp_path)


@pytest.mark.parametrize("mode", ["timeout", "preflight-timeout"])
def test_spelling_timeout_reaps_its_controlled_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    # Arrange: the checker creates and records its own child process.
    _ = install_spelling_script(tmp_path)
    configure_checker(tmp_path, mode, monkeypatch)
    try:
        # Act: exercise the same subprocess consumer used by the pipeline.
        result = run_synapse_script(tmp_path, "python", "check_spelling.py", "spelling")
        # Assert: timeout returns a failed verdict after cleanup, not an orphan.
        assert result.success is False, result
        assert "timed out after 0.5 seconds" in result.output
        assert (tmp_path / "child-reaped").read_text(encoding="utf-8") == "yes"
        pid = int((tmp_path / "checker-child.pid").read_text(encoding="utf-8"))
        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)
    finally:
        cleanup_checker(tmp_path)


@pytest.mark.parametrize(
    ("mode", "exit_code"),
    [("findings", 1), ("cli", 2), ("transport", 17), ("signal", 143)],
)
def test_standalone_spelling_script_preserves_nonzero_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str, exit_code: int
) -> None:
    # Arrange: invoke the standalone entrypoint, without a Python import/mock.
    script = install_spelling_script(tmp_path)
    configure_checker(tmp_path, mode, monkeypatch)
    try:
        # Act.
        result = subprocess.run(
            [sys.executable, str(script)], capture_output=True, text=True, timeout=8
        )
        # Assert: findings, CLI errors, transport errors and signals all fail.
        assert result.returncode == exit_code, result
        assert "All spelling checks passed" not in result.stdout
    finally:
        cleanup_checker(tmp_path)


def test_missing_required_spelling_script_fails(tmp_path: Path) -> None:
    # Arrange / Act: leave the required script absent in an isolated project.
    result = run_synapse_script(tmp_path, "python", "check_spelling.py", "spelling")
    # Assert: optional scripts may still skip, but spelling cannot.
    assert result.success is False
    assert "Required spelling script not found" in result.output
    assert result.errors


@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf", "invalid"])
@pytest.mark.parametrize(
    "variable", ["SPELL_CHECKER_TIMEOUT", "SPELL_CHECKER_PREFLIGHT_TIMEOUT"]
)
def test_spelling_rejects_unbounded_timeout_overrides(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, value: str, variable: str
) -> None:
    # Arrange.
    _ = install_spelling_script(tmp_path)
    configure_checker(tmp_path, "success", monkeypatch)
    monkeypatch.setenv(variable, value)
    # Act.
    result = run_synapse_script(tmp_path, "python", "check_spelling.py", "spelling")
    # Assert.
    assert result.success is False, result
    assert "Error configuring spell checker" in result.output


@pytest.mark.parametrize("override", ["", "  ", "'unterminated"])
def test_spelling_rejects_invalid_command_overrides(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, override: str
) -> None:
    # Arrange.
    _ = install_spelling_script(tmp_path)
    monkeypatch.setenv("SPELL_CHECKER_CMD", override)
    # Act.
    result = run_synapse_script(tmp_path, "python", "check_spelling.py", "spelling")
    # Assert.
    assert result.success is False
    assert "Error configuring spell checker" in result.output


def _write_checker_launcher(path: Path, command: list[str]) -> None:
    wrapper = (
        f"#!{sys.executable}\nimport os\nimport sys\n"
        + f"os.execv({command[0]!r}, {command!r} + sys.argv[1:])\n"
    )
    _ = path.write_text(wrapper, encoding="utf-8")
    path.chmod(0o755)


@pytest.mark.parametrize("local", [True, False])
def test_spelling_resolves_installed_checker_without_npx(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, local: bool
) -> None:
    # Arrange: a PATH npx trap must never be selected or invoked.
    _ = install_spelling_script(tmp_path)
    configure_checker(tmp_path, "success", monkeypatch)
    command = shlex.split(os.environ["SPELL_CHECKER_CMD"])
    directory = tmp_path / ("node_modules/.bin" if local else "bin")
    directory.mkdir(parents=True)
    _write_checker_launcher(directory / "cspell", command)
    trap = directory / "npx"
    _ = trap.write_text("#!/bin/sh\nexit 99\n", encoding="utf-8")
    trap.chmod(0o755)
    monkeypatch.delenv("SPELL_CHECKER_CMD")
    monkeypatch.setenv("PATH", str(directory))
    # Act / Assert.
    with patch(
        "cortex.tools.execution.pre_commit_synapse._resolve_synapse_python_bin",
        return_value=Path(sys.executable),
    ):
        result = run_synapse_script(tmp_path, "python", "check_spelling.py", "spelling")
    assert result.success is True, result


def test_missing_checker_does_not_fall_back_to_npx(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange: npx exists but no cspell is installed.
    _ = install_spelling_script(tmp_path)
    binary = tmp_path / "bin"
    binary.mkdir()
    npx = binary / "npx"
    _ = npx.write_text("#!/bin/sh\necho unexpected-network-attempt\n", encoding="utf-8")
    npx.chmod(0o755)
    monkeypatch.setenv("PATH", str(binary))
    monkeypatch.delenv("SPELL_CHECKER_CMD", raising=False)
    # Act.
    with patch(
        "cortex.tools.execution.pre_commit_synapse._resolve_synapse_python_bin",
        return_value=Path(sys.executable),
    ):
        result = run_synapse_script(tmp_path, "python", "check_spelling.py", "spelling")
    # Assert.
    assert result.success is False
    assert "cspell 8.6.1 not found" in result.output
    assert "unexpected-network-attempt" not in result.output


@pytest.mark.parametrize("selection", ["override", "project-local"])
def test_failed_selected_checker_cannot_fall_back_to_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, selection: str
) -> None:
    # Arrange: a valid PATH checker must not hide the selected checker's failure.
    _ = install_spelling_script(tmp_path)
    configure_checker(tmp_path, "preflight", monkeypatch)
    command = shlex.split(os.environ["SPELL_CHECKER_CMD"])
    binary = tmp_path / "bin"
    binary.mkdir()
    fallback = tmp_path / "fallback-used"
    checker = binary / "cspell"
    _ = checker.write_text(
        f"#!{sys.executable}\nfrom pathlib import Path\n"
        + f"Path({str(fallback)!r}).touch()\nprint('8.6.1')\n",
        encoding="utf-8",
    )
    checker.chmod(0o755)
    monkeypatch.setenv("PATH", str(binary))
    if selection == "project-local":
        local = tmp_path / "node_modules" / ".bin" / "cspell"
        local.parent.mkdir(parents=True)
        _write_checker_launcher(local, command)
        monkeypatch.delenv("SPELL_CHECKER_CMD")
    # Act / Assert: execute the real consumer with the host Python, not PATH Python.
    with patch(
        "cortex.tools.execution.pre_commit_synapse._resolve_synapse_python_bin",
        return_value=Path(sys.executable),
    ):
        result = run_synapse_script(tmp_path, "python", "check_spelling.py", "spelling")
    assert result.success is False
    assert "version probe failed" in result.output
    assert not fallback.exists()
