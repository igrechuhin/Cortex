"""Non-mutating source checks for explicit selected-test quality gates."""

import subprocess
from pathlib import Path

from cortex.core.path_resolver import get_venv_bin_path
from cortex.core.quality_scope import filter_owned_files

from .base import CheckResult, FrameworkAdapter
from .python_adapter import PythonAdapter
from .swift_adapter import SwiftAdapter


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


def _swift_source_files(root: Path) -> list[str]:
    """Bound formatting to version-controlled project sources, never build checkouts."""
    completed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    paths = [
        root / name
        for name in completed.stdout.split("\x00")
        if name.endswith(".swift") and ".build" not in Path(name).parts
    ]
    owned = filter_owned_files(root, paths)
    if any(not path.resolve().is_relative_to(root.resolve()) for path in owned):
        raise ValueError("Swift source scope contains a path outside the project")
    files = sorted({str(path.resolve()) for path in owned if path.is_file()})
    if not files:
        raise ValueError("No owned Swift sources found for selected source checks")
    return files


def _swift_format_check(root: Path) -> CheckResult:
    """Use the adapter's swift-format configuration on explicit owned source files."""
    try:
        files = _swift_source_files(root)
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        return CheckResult(
            check_type="format", success=False, output=str(exc), errors=[str(exc)]
        )
    result = CheckResult(check_type="format", success=True, output="")
    # AI: Bounded argv avoids E2BIG without recursing into dependency checkouts.
    for offset in range(0, len(files), 100):
        batch = _check_command(
            root,
            ["swift", "format", "lint", "--strict", *files[offset : offset + 100]],
            "format",
        )
        result.success = result.success and batch.success
        result.output += batch.output
        result.errors.extend(batch.errors)
    return result


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
        formatting = _swift_format_check(root)
        return lint, formatting
    raise ValueError("Selected source checks support only Python and SwiftPM adapters")
