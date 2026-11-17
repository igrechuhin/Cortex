"""Run the SwiftLint quality gate for projects that opt in via tracked settings."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from enum import Enum
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

from pydantic import BaseModel, Field

from cortex.services.framework_adapters.base import CheckResult

_CONFIG_NAMES = (".swiftlint.yml", ".swiftlint.yaml")
_VERSION = "swiftlint.version"
_BASELINE = "swiftlint-baseline.json"
_REBASE = ".github/scripts/swiftlint-baseline.py"
_INPUTS = (*_CONFIG_NAMES, _VERSION, _BASELINE)
_ERROR_ROOTS = frozenset({"Sources", "Tests"})
_CHECK = "synapse_lint"
_TIMEOUT = 120


class _Severity(str, Enum):
    ERROR = "Error"
    WARNING = "Warning"


class _Violation(BaseModel):
    file: str
    line: int | None = Field(default=None)
    severity: _Severity
    reason: str
    rule_id: str


def _run(root: Path, *argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv, cwd=root, capture_output=True, text=True, timeout=_TIMEOUT, check=False
    )


def _require_success(result: subprocess.CompletedProcess[str], label: str) -> str:
    output = (result.stdout + result.stderr).strip()
    if result.returncode:
        raise ValueError(f"{label} exited {result.returncode}: {output or 'no output'}")
    return output


def _tracked_setup(root: Path) -> set[str]:
    if not (root / ".git").exists():
        return set()
    inputs = (*_INPUTS, _REBASE)
    git = ("git", "-c", "core.fsmonitor=false")
    tracked = _run(root, *git, "ls-files", "-z", "--", *inputs)
    deleted = _run(
        root,
        *git,
        "diff",
        "--cached",
        "--no-renames",
        "--name-only",
        "--diff-filter=D",
        "-z",
        "--",
        *inputs,
    )
    for result in (tracked, deleted):
        _ = _require_success(result, "SwiftLint settings discovery")
    # Keep deleted index entries visible so deleting a tracked pin or baseline
    # cannot silently downgrade the required check.
    return set((tracked.stdout + deleted.stdout).split("\0")) - {""}


def swiftlint_required_for_final_gate(root: Path) -> bool:
    """Keep lint live even when sources are unchanged or input discovery fails."""
    try:
        return bool(_tracked_setup(root).intersection(_INPUTS))
    except (OSError, ValueError, subprocess.SubprocessError):
        return True


def _check_input(root: Path, name: str) -> Path:
    path = root / name
    if path.is_symlink() or not path.is_file():
        raise ValueError(
            f"Tracked SwiftLint input is missing or not a regular file: {name}"
        )
    return path


def _verify_version(root: Path, binary: str, tracked: set[str]) -> str:
    actual = _require_success(
        _run(root, binary, "--version"), "SwiftLint version check"
    )
    if _VERSION in tracked:
        expected = _check_input(root, _VERSION).read_text().strip()
        if not re.fullmatch(r"\d+\.\d+\.\d+", expected):
            raise ValueError(
                f"Invalid SwiftLint version pin in {_VERSION}: {expected!r}"
            )
        if actual != expected:
            raise ValueError(
                f"SwiftLint version mismatch: expected {expected}, got {actual!r}"
            )
    return actual


def _baseline_args(root: Path, tracked: set[str], temporary: Path) -> list[str]:
    if _BASELINE not in tracked:
        return []
    source = _check_input(root, _BASELINE)
    if _REBASE in tracked:
        script = _check_input(root, _REBASE)
        _ = _require_success(
            _run(root, sys.executable, str(script), "self-test"),
            "SwiftLint baseline self-test",
        )
        target = temporary / "baseline.json"
        _ = _require_success(
            _run(
                root,
                sys.executable,
                str(script),
                "rebase",
                str(source),
                str(target),
                str(root),
            ),
            "SwiftLint baseline rebase",
        )
    else:
        target = source
    if not isinstance(json.loads(target.read_text()), list):
        raise ValueError("SwiftLint baseline must be a JSON array")
    return ["--baseline", str(target)]


def _reports(result: subprocess.CompletedProcess[str], root: Path) -> list[str]:
    # SwiftLint exits 2 for normal lint findings; other exits are not a report.
    if result.returncode not in {0, 2}:
        _ = _require_success(result, "SwiftLint check without baseline")
    data: object = json.loads(result.stdout)
    if not isinstance(data, list) or (result.returncode == 2 and not data):
        raise ValueError("SwiftLint did not return a usable JSON violation report")
    findings: list[str] = []
    for item in cast(list[object], data):
        violation = _Violation.model_validate(item)
        path = Path(violation.file)
        relative = (root / path).resolve().relative_to(root)
        if (
            relative.parts
            and relative.parts[0] in _ERROR_ROOTS
            and violation.severity == _Severity.ERROR
        ):
            findings.append(
                f"{relative}:{violation.line}: error: {violation.reason} ({violation.rule_id})"
            )
    return findings


def _lint_arguments(root: Path, tracked: set[str]) -> tuple[str, list[str]]:
    configs = [_check_input(root, name) for name in _CONFIG_NAMES if name in tracked]
    if len(configs) > 1:
        raise ValueError(
            "SwiftLint configuration is ambiguous: both YAML files are tracked"
        )
    binary = shutil.which("swiftlint")
    if binary is None:
        raise FileNotFoundError(
            "SwiftLint is required for this project but not on PATH"
        )
    version = _verify_version(root, binary, tracked)
    args = [binary, "lint", "--quiet", "--no-cache"]
    # Default discovery preserves nested configurations, like CI.
    if configs and configs[0].name != _CONFIG_NAMES[0]:
        args += ["--config", str(configs[0])]
    return version, args


def _lint(root: Path, tracked: set[str]) -> str:
    version, args = _lint_arguments(root, tracked)
    with TemporaryDirectory(prefix="cortex-swiftlint-") as work:
        temporary = Path(work)
        baseline = _baseline_args(root, tracked, temporary)
        _ = _require_success(
            _run(root, *args, "--strict", *baseline), "SwiftLint strict check"
        )
        empty = temporary / "empty-baseline.json"
        _ = empty.write_text("[]\n")
        findings = _reports(
            _run(root, *args, "--reporter", "json", "--baseline", str(empty)), root
        )
    if findings:
        raise ValueError(
            f"SwiftLint found {len(findings)} error-severity violations in Sources/ or Tests/:\n"
            + "\n".join(findings)
        )
    return (
        f"SwiftLint {version}: strict lint passed; Sources/ and Tests/ have zero errors"
    )


def run_swiftlint_if_configured(project_root: Path) -> CheckResult | None:
    """Enforce strict and absolute SwiftLint policies without modifying the project."""
    root = project_root.resolve()
    try:
        tracked = _tracked_setup(root)
        if not tracked.intersection(_INPUTS):
            return None
        return CheckResult(check_type=_CHECK, success=True, output=_lint(root, tracked))
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        message = str(exc)
        return CheckResult(
            check_type=_CHECK, success=False, output=message, errors=[message]
        )
