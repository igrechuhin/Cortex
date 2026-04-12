"""Per-extension quality check dispatcher."""

import os
import re
import subprocess
from pathlib import Path
from subprocess import CompletedProcess

from cortex.core.constants import (
    EXTENSION_SCRIPT_MAP,
    FILE_SIZE_EXCLUDED_FILENAMES,
)
from cortex.core.path_resolver import (
    CortexResourceType,
    get_cortex_path,
    get_venv_bin_path,
)
from cortex.services.framework_adapters.base import CheckResult
from cortex.tools.execution.pre_commit_helpers_models import (
    FileSizeViolation,
    FunctionLengthViolation,
)

_SKIP_DIRS: frozenset[str] = frozenset(
    {
        "__pycache__",
        ".git",
        "node_modules",
        ".venv",
        ".cortex",  # synapse tooling, not project source
        "venv",
        # Repo-wide scans should skip test suites by default; tests are still
        # checked when explicitly passed via `files=[...]`.
        "tests",
        "Tests",
        "build",
        "dist",
        ".tox",
        ".mypy_cache",
    }
)

_FILE_SIZE_VIOLATION_RE = re.compile(
    r"^\s+(\S.+?):\s+(\d+) lines \(max:\s*(\d+),\s*excess:\s*(\d+)\)"
)
_PY_FUNC_FILE_HEADER_RE = re.compile(r"^\s+(\S.+\.py):\s*$")
_PY_FUNC_LINE_RE = re.compile(
    r"^\s+(\w+)\(\) at line (\d+):\s+(\d+) lines \(max:\s*(\d+),\s*excess:\s*(\d+)\)"
)
_SWIFT_FUNC_LINE_RE = re.compile(
    r"^\s+(\S.+\.swift):(\d+):\s+(\w+)\(\)\s+—\s+(\d+) lines \(max:\s*(\d+),\s*excess:\s*(\d+)\)"
)


def route_files(
    files: list[Path],
    extension_map: dict[str, str] | None = None,
) -> dict[str, list[Path]]:
    """Group files by their language directory.

    Returns mapping of language dir → file list.
    Files with unknown extensions are silently omitted.
    extension_map overrides EXTENSION_SCRIPT_MAP (for testing).
    """
    mapping = extension_map if extension_map is not None else EXTENSION_SCRIPT_MAP
    result: dict[str, list[Path]] = {}
    for f in files:
        suffix = Path(f).suffix
        lang_dir = mapping.get(suffix)
        if lang_dir is None:
            continue
        result.setdefault(lang_dir, []).append(Path(f))
    return result


def collect_project_files(project_root: Path) -> list[Path]:
    """Return all checkable source files under project_root.

    Skips: __pycache__, .git, node_modules, .venv, build, dist, .cortex,
    tests/, Tests/ dirs.  Test files are still checked when passed explicitly
    via run_quality_checks_for_all_languages(files=[...]).
    Skips FILE_SIZE_EXCLUDED_FILENAMES (e.g. models.py) by name.
    Returns sorted list of absolute Paths.
    """
    root = project_root.resolve()
    excluded_names = frozenset(FILE_SIZE_EXCLUDED_FILENAMES)
    known_ext = frozenset(EXTENSION_SCRIPT_MAP.keys())
    found: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        if path.name in excluded_names:
            continue
        if path.suffix not in known_ext:
            continue
        found.append(path.resolve())
    return sorted(found, key=lambda p: str(p))


def run_quality_checks_for_all_languages(
    project_root: Path,
    files: list[Path] | None = None,
) -> tuple[list[FileSizeViolation], list[FunctionLengthViolation]]:
    """Dispatch quality checks to per-language synapse scripts.

    If files is None, calls collect_project_files(project_root).
    Returns (file_size_violations, function_length_violations) merged across all languages.
    Returns ([], []) when no files match known extensions — not an error.
    """
    resolved_root = project_root.resolve()
    file_list = files if files is not None else collect_project_files(project_root)
    grouped = route_files(file_list)
    file_size_violations: list[FileSizeViolation] = []
    function_violations: list[FunctionLengthViolation] = []
    for language, lang_files in sorted(grouped.items()):
        if not lang_files:
            continue
        if not _language_has_required_scripts(resolved_root, language):
            raise _missing_language_scripts_error(resolved_root, language)
        fs_result = _run_script_with_files(
            resolved_root, language, "check_file_sizes.py", lang_files
        )
        file_size_violations.extend(
            _parse_file_size_violations(fs_result.output, resolved_root)
        )
        fl_result = _run_script_with_files(
            resolved_root, language, "check_function_lengths.py", lang_files
        )
        function_violations.extend(
            _parse_function_length_violations(fl_result.output, resolved_root, language)
        )
    return file_size_violations, function_violations


def _files_env_value(files: list[Path]) -> str:
    """Return newline-separated absolute paths string for FILES env var."""
    return "\n".join(str(p.resolve()) for p in files)


def _resolve_synapse_python_bin(project_root: Path) -> Path:
    """Resolve Python binary for running synapse scripts."""
    venv_python = get_venv_bin_path(project_root) / "python"
    return venv_python if venv_python.exists() else Path("python3")


def _language_has_required_scripts(project_root: Path, language: str) -> bool:
    """Return True when both quality scripts exist for a language."""
    synapse_root = get_cortex_path(project_root, CortexResourceType.SYNAPSE)
    scripts_dir = synapse_root / "scripts" / language
    return (scripts_dir / "check_file_sizes.py").exists() and (
        scripts_dir / "check_function_lengths.py"
    ).exists()


def _missing_language_scripts_error(project_root: Path, language: str) -> RuntimeError:
    """Build a user-facing error when language scripts are not scaffolded."""
    synapse_root = get_cortex_path(project_root, CortexResourceType.SYNAPSE)
    scripts_dir = synapse_root / "scripts" / language
    missing: list[str] = []
    for script_name in ("check_file_sizes.py", "check_function_lengths.py"):
        if not (scripts_dir / script_name).exists():
            missing.append(script_name)
    missing_str = ", ".join(missing) if missing else "unknown scripts"
    message = (
        f"Missing required quality scripts for language '{language}': {missing_str}. "
        f"Expected under {scripts_dir}."
    )
    return RuntimeError(message)


def _synapse_script_skipped_result(check_type: str, language: str) -> CheckResult:
    """Return CheckResult when synapse script is missing (skipped)."""
    return CheckResult(
        check_type=check_type,
        success=True,
        output=f"No script for language {language} (skipped)",
        errors=[],
        warnings=[],
        files_modified=[],
    )


def _completed_process_to_check_result(
    result: CompletedProcess[str],
    check_type: str,
) -> CheckResult:
    """Build CheckResult from a completed subprocess run."""
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


def _prepend_src_to_pythonpath(env: dict[str, str], project_root: Path) -> None:
    """Ensure ``project_root/src`` is first on PYTHONPATH for Synapse script imports."""
    src_dir = project_root / "src"
    if not src_dir.is_dir():
        return
    prev = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(src_dir) if not prev else f"{src_dir}{os.pathsep}{prev}"


def _execute_synapse_with_files_env(
    python_bin: Path,
    script_path: Path,
    project_root: Path,
    files: list[Path],
    check_type: str,
) -> CheckResult:
    """Run synapse script with FILES merged into the process environment."""
    env = {**os.environ, "FILES": _files_env_value(files)}
    _prepend_src_to_pythonpath(env, project_root)
    try:
        completed = subprocess.run(
            [str(python_bin), str(script_path)],
            cwd=project_root,
            capture_output=True,
            text=True,
            env=env,
        )
    except OSError as exc:
        return CheckResult(
            check_type=check_type,
            success=False,
            output=str(exc),
            errors=[str(exc)],
            warnings=[],
            files_modified=[],
        )
    return _completed_process_to_check_result(completed, check_type)


def _run_script_with_files(
    project_root: Path,
    language: str,
    script_name: str,
    files: list[Path],
) -> CheckResult:
    """Run a synapse script passing FILES env var.

    Resolves script path via get_cortex_path(project_root, CortexResourceType.SYNAPSE).
    Returns skipped CheckResult if script does not exist.
    Merges FILES into os.environ: env={**os.environ, "FILES": _files_env_value(files)}.
    """
    check_type = f"{language}_{script_name}"
    synapse_root = get_cortex_path(project_root, CortexResourceType.SYNAPSE)
    script_path = synapse_root / "scripts" / language / script_name
    if not script_path.exists():
        return _synapse_script_skipped_result(check_type, language)
    python_bin = _resolve_synapse_python_bin(project_root)
    return _execute_synapse_with_files_env(
        python_bin, script_path, project_root, files, check_type
    )


def _rel_file_str(rel: str, project_root: Path) -> str:
    """Normalize parsed relative path string for violation models."""
    try:
        p = Path(rel)
        if p.is_absolute():
            return str(p.resolve().relative_to(project_root))
        return rel.replace("\\", "/")
    except ValueError:
        return rel.replace("\\", "/")


def _parse_file_size_violations(
    output: str, project_root: Path
) -> list[FileSizeViolation]:
    """Parse check_file_sizes.py stderr into FileSizeViolation objects.

    Handles both Python and Swift output formats (same line format):
      "  path/to/file.ext: 450 lines (max: 400, excess: 50)"
    Silently skips unrecognised lines (forward-compatible).
    """
    violations: list[FileSizeViolation] = []
    for line in output.splitlines():
        try:
            m = _FILE_SIZE_VIOLATION_RE.match(line)
            if not m:
                continue
            rel, lines_s, max_s, excess_s = m.groups()
            violations.append(
                FileSizeViolation(
                    file=_rel_file_str(rel, project_root),
                    lines=int(lines_s),
                    max_lines=int(max_s),
                    excess=int(excess_s),
                )
            )
        except Exception:
            continue
    return violations


def _parse_function_length_violations(
    output: str,
    project_root: Path,
    language: str,
) -> list[FunctionLengthViolation]:
    """Parse check_function_lengths.py stderr into FunctionLengthViolation objects.

    Python format (two-line: file header, then function):
      "  src/cortex/foo.py:"
      "    my_func() at line 42: 35 lines (max: 30, excess: 5)"

    Swift format (one-line):
      "  Sources/Foo/Bar.swift:42: myFunc() — 35 lines (max: 30, excess: 5)"

    Silently skips unrecognised lines.
    """
    if language == "swift":
        return _parse_swift_function_lines(output, project_root)
    return _parse_python_function_lines(output, project_root)


def _parse_swift_function_lines(
    output: str,
    project_root: Path,
) -> list[FunctionLengthViolation]:
    violations: list[FunctionLengthViolation] = []
    for line in output.splitlines():
        try:
            m = _SWIFT_FUNC_LINE_RE.match(line)
            if not m:
                continue
            rel, line_no, func_name, lines_s, max_s, excess_s = m.groups()
            violations.append(
                FunctionLengthViolation(
                    file=_rel_file_str(rel, project_root),
                    function=func_name,
                    line=int(line_no),
                    lines=int(lines_s),
                    max_lines=int(max_s),
                    excess=int(excess_s),
                )
            )
        except Exception:
            continue
    return violations


def _parse_python_function_lines(
    output: str,
    project_root: Path,
) -> list[FunctionLengthViolation]:
    violations: list[FunctionLengthViolation] = []
    current_file: str | None = None
    for line in output.splitlines():
        try:
            fh = _PY_FUNC_FILE_HEADER_RE.match(line)
            if fh:
                current_file = fh.group(1)
                continue
            m = _PY_FUNC_LINE_RE.match(line)
            if m and current_file is not None:
                func_name, line_no, lines_s, max_s, excess_s = m.groups()
                violations.append(
                    FunctionLengthViolation(
                        file=_rel_file_str(current_file, project_root),
                        function=func_name,
                        line=int(line_no),
                        lines=int(lines_s),
                        max_lines=int(max_s),
                        excess=int(excess_s),
                    )
                )
        except Exception:
            continue
    return violations
