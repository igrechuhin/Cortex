"""Regression coverage for the built-in SwiftLint commit gate."""

import json
import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from cortex.services.framework_adapters.base import CheckResult
from cortex.tools.execution import pre_commit_swiftlint
from cortex.tools.execution.pre_commit_dirty_state import (
    PipelineDirtyTracker,
    compute_git_file_hash,
)
from cortex.tools.execution.pre_commit_synapse import run_synapse_script


@pytest.fixture
def project(tmp_path: Path) -> Path:
    _ = subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    return tmp_path


def _track(root: Path, name: str, content: str) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(content)
    _ = subprocess.run(["git", "add", "--", name], cwd=root, check=True)


def _gate(root: Path) -> CheckResult:
    return run_synapse_script(root, "swift", "check_linting.py", "synapse_lint")


def _run_fake_linter(
    root: Path,
    binary: str,
    version: str = "0.65.0",
    report: str = "[]",
    reported_exit: int = 0,
    strict_exit: int = 0,
) -> CheckResult:
    def _subprocess(cwd: Path, *argv: str) -> subprocess.CompletedProcess[str]:
        if argv[0] != binary:
            return subprocess.run(
                argv, cwd=cwd, capture_output=True, text=True, check=False
            )
        if "--version" in argv:
            return subprocess.CompletedProcess(argv, 0, version + "\n", "")
        if "--strict" in argv:
            if (root / ".swiftlint.yml").is_file():
                assert "--config" not in argv  # CI default discovers nested configs.
            message = "error: invalid SwiftLint YAML" if strict_exit else ""
            return subprocess.CompletedProcess(argv, strict_exit, "", message)
        assert "--reporter" in argv and "--baseline" in argv
        assert json.loads(Path(argv[-1]).read_text()) == []
        return subprocess.CompletedProcess(argv, reported_exit, report, "")

    with (
        patch.object(shutil, "which", return_value=binary),
        patch.object(pre_commit_swiftlint, "_run", side_effect=_subprocess),
    ):
        return _gate(root)


def test_unconfigured_project_keeps_optional_synapse_fallback(project: Path) -> None:
    result = _gate(project)
    assert result.success is True
    assert "skipped" in result.output


def test_tracked_config_without_pin_runs_strict_lint(project: Path) -> None:
    _track(project, ".swiftlint.yml", "included: [Sources]\n")
    result = _run_fake_linter(project, "/test/swiftlint")
    assert result.success is True
    assert "strict lint passed" in result.output


def test_configured_project_cannot_skip_missing_binary(project: Path) -> None:
    _track(project, ".swiftlint.yml", "included: [Sources]\n")
    with patch(
        "cortex.tools.execution.pre_commit_swiftlint.shutil.which", return_value=None
    ):
        result = _gate(project)
    assert result.success is False
    assert "not on PATH" in result.output


@pytest.mark.parametrize(
    "pin,message",
    [
        ("not a version", "Invalid SwiftLint version pin"),
        ("0.64.0", "version mismatch"),
    ],
)
def test_configured_project_rejects_invalid_or_mismatched_pin(
    project: Path, pin: str, message: str
) -> None:
    _track(project, "swiftlint.version", pin)
    result = _run_fake_linter(project, "/test/swiftlint")
    assert result.success is False
    assert message in result.output


def test_deleted_tracked_configuration_fails_closed(project: Path) -> None:
    _track(project, ".swiftlint.yml", "included: [Sources]\n")
    (project / ".swiftlint.yml").unlink()
    result = _run_fake_linter(project, "/test/swiftlint")
    assert result.success is False
    assert "missing or not a regular file" in result.output


def test_invalid_swiftlint_yaml_cannot_pass(project: Path) -> None:
    _track(project, ".swiftlint.yml", "invalid: [\n")
    result = _run_fake_linter(project, "/test/swiftlint", strict_exit=1)
    assert result.success is False
    assert "invalid SwiftLint YAML" in result.output


@pytest.mark.parametrize("path", ["Sources/A.swift", "Tests/A.swift"])
def test_absolute_gate_catches_errors_even_when_strict_with_baseline_passes(
    project: Path, path: str
) -> None:
    _track(project, ".swiftlint.yml", "included: [Sources, Tests]\n")
    _track(project, "swiftlint-baseline.json", "[]")
    report = json.dumps(
        [
            {
                "file": str(project / path),
                "line": 7,
                "severity": "Error",
                "reason": "Force cast",
                "rule_id": "force_cast",
            }
        ]
    )
    result = _run_fake_linter(
        project, "/test/swiftlint", report=report, reported_exit=2
    )
    assert result.success is False
    assert f"{path}:7: error" in result.output


@pytest.mark.parametrize(
    "exit_code,report", [(-6, "[]"), (2, ""), (2, "[]"), (0, "{}")]
)
def test_malformed_or_crashed_linter_cannot_pass(
    project: Path, exit_code: int, report: str
) -> None:
    _track(project, ".swiftlint.yml", "included: [Sources]\n")
    result = _run_fake_linter(
        project, "/test/swiftlint", report=report, reported_exit=exit_code
    )
    assert result.success is False


def test_final_gate_does_not_reuse_source_only_lint_fingerprint(project: Path) -> None:
    _track(project, ".swiftlint.yml", "included: [Sources]\n")
    tracker = PipelineDirtyTracker(project_root=project)
    tracker.record_phase_a(project, passed=True)
    fingerprint = tracker.phase_a_fingerprint
    assert fingerprint is not None
    assert fingerprint.source_hash == compute_git_file_hash(project).source_hash
    assert not tracker.can_skip_check("synapse_lint").can_skip


@pytest.mark.skipif(
    shutil.which("swiftlint") is None, reason="Native SwiftLint is not installed"
)
def test_real_swiftlint_blocks_swift_source_violation(project: Path) -> None:
    _track(project, ".swiftlint.yml", "included: [Sources]\nforce_cast: error\n")
    _track(project, "Sources/A.swift", "let result = 123 as! String\n")
    result = _gate(project)
    assert result.success is False
    assert "force_cast" in result.output


def test_staged_deletion_does_not_disable_configured_gate(project: Path) -> None:
    _track(project, "swiftlint.version", "0.65.0")
    _ = subprocess.run(
        [
            "git",
            "-c",
            "user.name=Cortex Test",
            "-c",
            "user.email=cortex@example.com",
            "commit",
            "-qm",
            "test",
        ],
        cwd=project,
        check=True,
    )
    _ = subprocess.run(
        ["git", "rm", "-q", "swiftlint.version"], cwd=project, check=True
    )
    result = _run_fake_linter(project, "/test/swiftlint")
    assert result.success is False
    assert "Tracked SwiftLint input is missing" in result.output


def test_baseline_rebase_helper_failure_cannot_pass(project: Path) -> None:
    _track(project, "swiftlint-baseline.json", "[]")
    _track(project, ".github/scripts/swiftlint-baseline.py", "raise SystemExit(3)\n")
    result = _run_fake_linter(project, "/test/swiftlint")
    assert result.success is False
    assert "SwiftLint baseline self-test exited 3" in result.output


@pytest.mark.skipif(
    shutil.which("swiftlint") is None, reason="Native SwiftLint is not installed"
)
def test_real_swiftlint_uses_nested_config_like_ci(project: Path) -> None:
    _track(project, ".swiftlint.yml", "included: [Sources]\nforce_cast: error\n")
    _track(project, "Sources/Nested/.swiftlint.yml", "disabled_rules: [force_cast]\n")
    _track(project, "Sources/Nested/A.swift", "let result = 123 as! String\n")
    result = _gate(project)
    assert result.success is True, result.output
