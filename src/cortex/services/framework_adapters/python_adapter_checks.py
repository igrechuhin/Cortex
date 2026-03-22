"""Check execution helpers for Python framework adapter.

Runs format, lint, and type-check subprocesses. Uses project_root and
get_command to remain MCP-safe (no reliance on PATH).
"""

import subprocess
from collections.abc import Callable
from pathlib import Path

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.services.framework_adapters.base import CheckResult


def run_black_formatting(
    project_root: Path,
    get_command: Callable[[str], str],
    errors: list[str],
    output_parts: list[str],
) -> None:
    """Run black formatter on src/ and tests/ (matches CI workflow)."""
    try:
        result = subprocess.run(
            [get_command("black"), "src/", "tests/"],
            cwd=project_root,
            capture_output=True,
            text=True,
        )
        output_parts.append(result.stdout)
        if result.returncode != 0:
            errors.append("Black formatting failed")
    except subprocess.TimeoutExpired as e:
        errors.append(f"Black formatting timed out: {e}")
    except (OSError, subprocess.SubprocessError) as e:
        errors.append(f"Black formatting error: {e}")
    except Exception as e:
        errors.append(f"Unexpected black error: {e}")


def run_ruff_import_sorting(
    project_root: Path,
    get_command: Callable[[str], str],
    errors: list[str],
    output_parts: list[str],
) -> None:
    """Run ruff import sorting on src/ and tests/ (matches CI workflow)."""
    try:
        result = subprocess.run(
            [
                get_command("ruff"),
                "check",
                "--fix",
                "--select",
                "I",
                "src/",
                "tests/",
            ],
            cwd=project_root,
            capture_output=True,
            text=True,
        )
        output_parts.append(result.stdout)
        if result.returncode != 0:
            errors.append("Ruff import sorting failed")
    except subprocess.TimeoutExpired as e:
        errors.append(f"Ruff import sorting timed out: {e}")
    except (OSError, subprocess.SubprocessError) as e:
        errors.append(f"Ruff import sorting error: {e}")
    except Exception as e:
        errors.append(f"Unexpected ruff import sorting error: {e}")


def _run_type_check_script(
    project_root: Path,
    venv_bin: Path,
    script_path: Path,
    parse_errors: Callable[[str], list[str]],
) -> CheckResult:
    """Execute check_types.py and return a CheckResult (no exception handling)."""
    python_bin = (
        str(venv_bin / "python") if (venv_bin / "python").exists() else "python3"
    )
    result = subprocess.run(
        [python_bin, str(script_path)],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=300,
    )
    output = result.stdout + result.stderr
    errors = parse_errors(output) if result.returncode != 0 else []
    err_list = (
        errors if errors else ([output.strip()] if result.returncode != 0 else [])
    )
    return _type_check_result(result.returncode == 0, output, err_list)


def type_check_via_script(
    project_root: Path,
    venv_bin: Path,
    script_path: Path,
    parse_errors: Callable[[str], list[str]],
) -> CheckResult:
    """Run check_types.py so scope matches CI (src + tests + synapse scripts)."""
    try:
        return _run_type_check_script(project_root, venv_bin, script_path, parse_errors)
    except subprocess.TimeoutExpired:
        return _type_check_result(
            False, "check_types.py timed out (300s)", ["Type check script timed out"]
        )
    except (OSError, subprocess.SubprocessError) as e:
        return _type_check_result(False, str(e), [str(e)])
    except Exception as e:
        return _type_check_result(
            False, str(e), [f"Unexpected type-check runner error: {e}"]
        )


def _run_pyright(
    project_root: Path,
    get_command: Callable[[str], str],
    parse_errors: Callable[[str], list[str]],
) -> CheckResult:
    """Execute pyright and return a CheckResult (no exception handling)."""
    result = subprocess.run(
        [get_command("pyright"), "src/", "tests/"],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=300,
    )
    output = result.stdout + result.stderr
    errors = parse_errors(output)
    return CheckResult(
        check_type="type_check",
        success=len(errors) == 0,
        output=output,
        errors=errors,
        warnings=[],
        files_modified=[],
    )


def type_check_pyright_only(
    project_root: Path,
    get_command: Callable[[str], str],
    parse_errors: Callable[[str], list[str]],
) -> CheckResult:
    """Fallback: pyright on src/ and tests/ when check_types.py is missing."""
    try:
        return _run_pyright(project_root, get_command, parse_errors)
    except subprocess.TimeoutExpired as e:
        return _type_check_result(
            False,
            str(e),
            [f"Pyright timed out: {e}"],
        )
    except (OSError, subprocess.SubprocessError) as e:
        return _type_check_result(False, str(e), [str(e)])
    except Exception as e:
        return _type_check_result(False, str(e), [f"Unexpected pyright error: {e}"])


def _type_check_result(success: bool, output: str, errors: list[str]) -> CheckResult:
    """Build a type_check CheckResult."""
    return CheckResult(
        check_type="type_check",
        success=success,
        output=output,
        errors=errors,
        warnings=[],
        files_modified=[],
    )


def execute_ruff_fix_command(
    project_root: Path,
    get_command: Callable[[str], str],
) -> str:
    """Execute ruff check with --fix to auto-fix errors."""
    result = subprocess.run(
        [
            get_command("ruff"),
            "check",
            "--fix",
            "src/",
            "tests/",
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=300,
    )
    return result.stdout + result.stderr


def execute_ruff_verify_command(
    project_root: Path,
    get_command: Callable[[str], str],
) -> str:
    """Execute ruff check without --fix to verify no errors remain."""
    result = subprocess.run(
        [
            get_command("ruff"),
            "check",
            "src/",
            "tests/",
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        error_msg = (
            f"Ruff verification failed (exit code {result.returncode}). "
            "Unfixable errors remain after auto-fix."
        )
        return f"{result.stdout}{result.stderr}\n{error_msg}"
    return result.stdout + result.stderr


def run_ruff_fix(
    project_root: Path,
    get_command: Callable[[str], str],
    parse_lint_errors_fn: Callable[[str], list[str]],
) -> CheckResult:
    """Run ruff with auto-fix, then verify no errors remain."""
    try:
        fix_output = execute_ruff_fix_command(project_root, get_command)
        verify_output = execute_ruff_verify_command(project_root, get_command)
        verify_errors = parse_lint_errors_fn(verify_output)

        combined_output = (
            f"{fix_output}\n\n--- Verification (matches CI) ---\n{verify_output}"
        )

        if verify_errors:
            return _create_lint_result(combined_output, verify_errors)
        return _create_lint_result(combined_output, [])
    except subprocess.TimeoutExpired as e:
        return _create_lint_error_result(f"Ruff fix/verify timed out (300s): {e}")
    except (OSError, subprocess.SubprocessError) as e:
        return _create_lint_error_result(str(e))
    except Exception as e:
        return _create_lint_error_result(f"Unexpected ruff fix error: {e}")


def _create_lint_result(output: str, errors: list[str]) -> CheckResult:
    """Create lint check result from output and errors."""
    return CheckResult(
        check_type="lint",
        success=len(errors) == 0,
        output=output,
        errors=errors,
        warnings=[],
        files_modified=[],
    )


def _create_lint_error_result(error_msg: str) -> CheckResult:
    """Create lint check result for error case."""
    return CheckResult(
        check_type="lint",
        success=False,
        output=error_msg,
        errors=[error_msg],
        warnings=[],
        files_modified=[],
    )


def get_type_check_script_path(project_root: Path) -> Path:
    """Return path to check_types.py when present."""
    return (
        get_cortex_path(project_root, CortexResourceType.SYNAPSE)
        / "scripts"
        / "python"
        / "check_types.py"
    )
