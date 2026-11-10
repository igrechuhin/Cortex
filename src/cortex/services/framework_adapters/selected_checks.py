"""Non-mutating source checks for explicit selected-test quality gates."""

import subprocess
from pathlib import Path

from cortex.core.path_resolver import get_venv_bin_path

from .base import CheckResult, FrameworkAdapter
from .python_adapter import PythonAdapter
from .swift_adapter import SwiftAdapter
from .swift_formatting import run_swift_format


def _check_command(root: Path, command: list[str], check_type: str) -> CheckResult:
    """Capture command failures without applying source changes or skipping checks."""
    try:
        completed = subprocess.run(
            command,
            cwd=root,
            capture_output=True,
            text=True,
            timeout=300,
        )
        output = completed.stdout + completed.stderr
        errors = [] if completed.returncode == 0 else [output or f"{check_type} failed"]
    except (OSError, subprocess.SubprocessError) as exc:
        output = str(exc)
        errors = [output]
    return CheckResult(
        check_type=check_type,
        success=not errors,
        output=output,
        errors=errors,
        files_modified=[],
    )


def _python_checks(root: Path) -> tuple[CheckResult, CheckResult]:
    """Keep lint, formatting, and import-order validation without autofix."""
    bin_path = get_venv_bin_path(root)
    ruff = [str(bin_path / "ruff"), "check", "--no-fix", "--no-fix-only"]
    lint = _check_command(root, [*ruff, "src/", "tests/"], "lint")
    formatting = _check_command(
        root, [str(bin_path / "black"), "--check", "src/", "tests/"], "format"
    )
    imports = _check_command(root, [*ruff, "--select", "I", "src/", "tests/"], "format")
    formatting.success = formatting.success and imports.success
    formatting.output += "\n" + imports.output
    formatting.errors.extend(imports.errors)
    return lint, formatting


def selected_source_checks(
    adapter: FrameworkAdapter,
) -> tuple[CheckResult, CheckResult]:
    """Return read-only lint and format checks; never call mutating adapter methods."""
    root = adapter.project_root
    if isinstance(adapter, PythonAdapter):
        return _python_checks(root)
    if isinstance(adapter, SwiftAdapter):
        if not adapter.has_package_swift():
            raise ValueError("Selected source checks require Swift Package Manager")
        lint = _check_command(root, ["swift", "build"], "lint")
        formatting = run_swift_format(root, check=True)
        return lint, formatting
    raise ValueError("Selected source checks support only Python and SwiftPM adapters")
