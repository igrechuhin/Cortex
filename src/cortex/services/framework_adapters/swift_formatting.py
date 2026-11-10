"""One project-selected Swift formatter for checks and scoped autofix."""

import re
import subprocess
from pathlib import Path

from cortex.core.quality_scope import filter_owned_files

from .base import CheckResult


def swift_source_files(root: Path) -> list[str]:
    """Bound formatting to owned sources, never dependency checkouts."""
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
        raise ValueError("No owned Swift sources found for formatting")
    return files


def _validate_swiftformat_version(root: Path) -> None:
    """Never silently substitute a different version for a project pin."""
    pin = root / "swiftformat.version"
    if not pin.exists():
        return
    expected = pin.read_text().strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", expected):
        raise ValueError("Invalid swiftformat.version: expected major.minor.patch")
    result = subprocess.run(
        ["swiftformat", "--version"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    actual = result.stdout.strip()
    if actual != expected:
        raise ValueError(
            f"SwiftFormat version mismatch: expected {expected}, got {actual}"
        )


def _format_command(root: Path, check: bool) -> list[str]:
    """Explicit project configuration wins over build-system defaults."""
    swiftformat = (root / ".swiftformat").exists() or (
        root / "swiftformat.version"
    ).exists()
    apple = (root / ".swift-format").exists()
    if swiftformat and apple:
        raise ValueError("Conflicting Swift formatter configurations")
    if swiftformat or (not apple and not (root / "Package.swift").exists()):
        _validate_swiftformat_version(root)
        command = ["swiftformat", "--lint"] if check else ["swiftformat"]
        if (root / ".swiftformat").exists():
            command.extend(["--config", str((root / ".swiftformat").resolve())])
        return command
    if check:
        return ["swift", "format", "lint", "--strict"]
    return ["swift", "format", "--in-place"]


def run_swift_format(root: Path, *, check: bool) -> CheckResult:
    """Run exactly one formatter on bounded batches; operational errors fail closed."""
    result = CheckResult(check_type="format", success=True, output="")
    try:
        files = swift_source_files(root)
        command = _format_command(root, check)
        # AI: Explicit bounded argv avoids E2BIG and recursive vendor mutation.
        for offset in range(0, len(files), 100):
            completed = subprocess.run(
                [*command, *files[offset : offset + 100]],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=300,
            )
            output = completed.stdout + completed.stderr
            result.output += output
            if completed.returncode != 0:
                result.errors.append(output or "Swift formatting failed")
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        result.output += str(exc)
        result.errors.append(str(exc))
    result.success = not result.errors
    return result
