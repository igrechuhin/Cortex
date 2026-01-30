"""Run Synapse scripts for format_ci_parity and test_naming checks.

Extracted from pre_commit_tools to keep that file under 400 lines.
"""

import subprocess
from pathlib import Path

from cortex.services.framework_adapters.base import CheckResult


def _synapse_script_skipped_result(check_type: str, language: str) -> CheckResult:
    """Return CheckResult when synapse script is missing (skipped)."""
    return CheckResult(
        check_type=check_type,
        success=True,
        output=f"No {check_type} script for language {language} (skipped)",
        errors=[],
        warnings=[],
        files_modified=[],
    )


def _resolve_synapse_python_bin(project_root: Path) -> Path:
    """Resolve Python binary for running synapse scripts."""
    venv_python = project_root / ".venv" / "bin" / "python"
    return venv_python if venv_python.exists() else Path("python3")


def _execute_synapse_script_subprocess(
    python_bin: Path,
    script_path: Path,
    project_root: Path,
    check_type: str,
) -> CheckResult:
    """Run synapse script via subprocess and return CheckResult."""
    result = subprocess.run(
        [str(python_bin), str(script_path)],
        cwd=project_root,
        capture_output=True,
        text=True,
    )
    output = result.stdout + result.stderr
    success = result.returncode == 0
    errors = [] if success else [output.strip() or f"Exit code {result.returncode}"]
    return CheckResult(
        check_type=check_type,
        success=success,
        output=output,
        errors=errors,
        warnings=[],
        files_modified=[],
    )


def _synapse_script_exception_result(check_type: str, e: Exception) -> CheckResult:
    """Return CheckResult when synapse script raises."""
    return CheckResult(
        check_type=check_type,
        success=False,
        output=str(e),
        errors=[str(e)],
        warnings=[],
        files_modified=[],
    )


def run_synapse_script(
    project_root: Path,
    language: str,
    script_name: str,
    check_type: str,
) -> CheckResult:
    """Run a synapse script and return CheckResult. Scripts are implementation detail."""
    script_path = (
        project_root / ".cortex" / "synapse" / "scripts" / language / script_name
    )
    if not script_path.exists():
        return _synapse_script_skipped_result(check_type, language)
    python_bin = _resolve_synapse_python_bin(project_root)
    try:
        return _execute_synapse_script_subprocess(
            python_bin, script_path, project_root, check_type
        )
    except Exception as e:
        return _synapse_script_exception_result(check_type, e)
