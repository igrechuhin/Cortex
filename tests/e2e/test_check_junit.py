"""Regression tests for the fail-closed GitHub Actions JUnit acceptance command."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

CASE = "test_artifact_migration_stdio_protocol[editable]"
SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_junit.py"


@pytest.mark.parametrize(
    ("names", "require_case", "skipped", "expected"),
    [
        (["unrelated"], False, False, 0),
        ([CASE], True, False, 0),
        (["unrelated"], True, False, 1),
        ([CASE, CASE], True, False, 1),
        ([CASE], True, True, 1),
    ],
)
def test_public_junit_acceptance(
    tmp_path: Path,
    names: list[str],
    require_case: bool,
    skipped: bool,
    expected: int,
) -> None:
    """The new requirement cannot be satisfied by missing, duplicate or skipped tests."""
    report = tmp_path / "report.xml"
    cases = "".join(
        f'<testcase name="{name}">{"<skipped/>" if skipped else ""}</testcase>'
        for name in names
    )
    _ = report.write_text(
        f'<testsuite tests="{len(names)}" failures="0" errors="0" '
        + f'skipped="{int(skipped)}">{cases}</testsuite>',
        encoding="utf-8",
    )
    command = [sys.executable, str(SCRIPT), str(report)]
    if require_case:
        command.extend(["--require-case", CASE])
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    assert completed.returncode == expected, completed.stderr
