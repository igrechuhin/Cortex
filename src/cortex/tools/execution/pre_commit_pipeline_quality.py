"""Quality check logic for the pre-commit pipeline.

Extracted from pre_commit_pipeline_processors to keep files under 400 lines.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from cortex.core.constants import (
    EXTENSION_SCRIPT_MAP,
    MAX_FILE_LINES,
    MAX_FUNCTION_LINES,
)
from cortex.services.framework_adapters.base import CheckResult, FrameworkAdapter
from cortex.tools.execution.file_language_router import (
    run_quality_checks_for_all_languages,
)
from cortex.tools.execution.pre_commit_cache_payload_audit import (
    check_cache_payload_stability,
)
from cortex.tools.execution.pre_commit_helpers_models import (
    FileSizeViolation,
    FunctionLengthViolation,
    QualityCheckResult,
)
from cortex.tools.execution.pre_commit_helpers_quality import (
    check_function_lengths_in_source,
)
from cortex.tools.execution.pre_commit_type_checking_audit import (
    check_type_checking_ban,
)


def _collect_git_delta_files(project_root: Path) -> list[Path] | None:
    """Return changed/untracked files for incremental quality checks.

    Returns None if git commands fail (caller decides fallback).
    """
    candidates: set[Path] = set()
    for args in (
        ["git", "diff", "--cached", "--name-only"],
        ["git", "diff", "--name-only"],
        ["git", "ls-files", "--others", "--exclude-standard"],
    ):
        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                cwd=str(project_root),
                timeout=10,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None
        if result.returncode != 0:
            return None
        for line in result.stdout.splitlines():
            rel = line.strip()
            if rel:
                candidates.add((project_root / rel).resolve())
    return sorted(candidates, key=lambda p: str(p))


def _filter_checkable_files(files: list[Path]) -> list[Path]:
    """Filter to existing files with extensions supported by the router."""
    known_ext = frozenset(EXTENSION_SCRIPT_MAP.keys())
    return [p for p in files if p.is_file() and p.suffix in known_ext]


def _collect_git_renames(project_root: Path) -> dict[str, str]:
    """Return rename map new_path -> old_path from staged/unstaged git diff."""
    renames: dict[str, str] = {}
    for args in (
        ["git", "diff", "--name-status", "-M"],
        ["git", "diff", "--cached", "--name-status", "-M"],
    ):
        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                cwd=str(project_root),
                timeout=10,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return renames
        if result.returncode != 0:
            continue
        for line in result.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) == 3 and parts[0].startswith("R"):
                old_path = parts[1].strip()
                new_path = parts[2].strip()
                if old_path and new_path:
                    renames[new_path] = old_path
    return renames


def run_git_diff_output(project_root: Path, args: list[str]) -> str | None:
    """Run git diff and return stdout on success."""
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=False,
            cwd=str(project_root),
            timeout=10,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.decode("utf-8", errors="replace")


def read_head_source(project_root: Path, rel_path: str) -> str | None:
    """Read source for rel_path from HEAD, returning None if missing."""
    check = subprocess.run(
        ["git", "cat-file", "-e", f"HEAD:{rel_path}"],
        capture_output=True,
        text=True,
        cwd=str(project_root),
        timeout=10,
    )
    if check.returncode != 0:
        return None
    show = subprocess.run(
        ["git", "show", f"HEAD:{rel_path}"],
        capture_output=True,
        text=False,
        cwd=str(project_root),
        timeout=10,
    )
    if show.returncode != 0:
        return None
    return show.stdout.decode("utf-8", errors="replace")


def _build_baseline_function_lines(
    project_root: Path, changed_rel: set[str], rename_map: dict[str, str]
) -> tuple[set[str], dict[str, dict[str, int]]]:
    """Collect tracked changed files and baseline oversized functions."""
    tracked: set[str] = set()
    baseline: dict[str, dict[str, int]] = {}
    for rel in changed_rel:
        head_source = read_head_source(project_root, rel)
        if head_source is None and rel in rename_map:
            head_source = read_head_source(project_root, rename_map[rel])
        if head_source is None:
            continue
        tracked.add(rel)
        functions = check_function_lengths_in_source(head_source)
        baseline[rel] = {
            name: lines
            for name, lines, _start in functions
            if lines > MAX_FUNCTION_LINES
        }
    return tracked, baseline


def filter_preexisting_structural_violations(
    project_root: Path,
    delta_files: list[Path],
    file_violations: list[FileSizeViolation],
    func_violations: list[FunctionLengthViolation],
) -> tuple[list[FileSizeViolation], list[FunctionLengthViolation]]:
    """Keep only newly introduced or worsened structural violations.

    For changed tracked files, compare current violations against HEAD.
    Untracked files are treated as new code and keep all violations.
    """
    changed_rel = changed_relative_files(project_root, delta_files)
    if not changed_rel:
        return file_violations, func_violations

    return _filter_with_baseline(
        project_root, changed_rel, file_violations, func_violations
    )


def changed_relative_files(project_root: Path, delta_files: list[Path]) -> set[str]:
    """Build set of changed relative file paths."""
    known_ext = frozenset(EXTENSION_SCRIPT_MAP.keys())
    return {
        path.relative_to(project_root).as_posix()
        for path in delta_files
        if path.is_file()
        and path.suffix in known_ext
        and path.is_relative_to(project_root)
    }


def _filter_with_baseline(
    project_root: Path,
    changed_rel: set[str],
    file_violations: list[FileSizeViolation],
    func_violations: list[FunctionLengthViolation],
) -> tuple[list[FileSizeViolation], list[FunctionLengthViolation]]:
    """Filter violations: file-size uses HEAD baseline; function-length uses no filtering."""
    rename_map = _collect_git_renames(project_root)
    tracked_files, _ = _build_baseline_function_lines(
        project_root, changed_rel, rename_map
    )
    filtered_files = _filter_file_violations(
        file_violations, changed_rel, tracked_files
    )
    filtered_functions = _filter_function_violations(
        func_violations, changed_rel, {}, {}
    )
    return filtered_files, filtered_functions


def _filter_file_violations(
    file_violations: list[FileSizeViolation],
    changed_rel: set[str],
    tracked_files: set[str],
) -> list[FileSizeViolation]:
    """Keep file-size violations for unchanged or newly added changed files."""
    return [
        violation
        for violation in file_violations
        if violation.file not in changed_rel or violation.file not in tracked_files
    ]


def _filter_function_violations(
    func_violations: list[FunctionLengthViolation],
    changed_rel: set[str],
    changed_line_ranges: dict[str, list[tuple[int, int]]],
    baseline_function_lines: dict[str, dict[str, int]],
) -> list[FunctionLengthViolation]:
    """Report all function violations in staged files — no hunk-boundary filtering.

    CI's check_function_lengths.py checks every function unconditionally. The
    local gate must match: any function exceeding the limit in a staged file is
    a violation, regardless of whether the def line or body additions are in the
    diff hunk.
    """
    return [v for v in func_violations if v.file in changed_rel]


def check_function_lengths(project_root: Path) -> list[FunctionLengthViolation]:
    """Compatibility shim that delegates function checks to the language router."""
    _, function_violations = run_quality_checks_for_all_languages(project_root)
    return function_violations


def execute_quality(adapter: FrameworkAdapter, language: str) -> QualityCheckResult:
    """Execute quality check: linting; file/function sizes via language router."""
    lint_result = adapter.lint_code()
    project_root = adapter.project_root
    delta_files = _collect_git_delta_files(project_root)
    # delta_files is None  → git unavailable; fall back to full scan.
    # delta_files is []    → clean working tree (nothing staged/changed/untracked);
    #                         also fall back to full scan so a clean tree is never
    #                         silently skipped (this was the root cause of the
    #                         false-green quality gate on TradeWing).
    checkable = _filter_checkable_files(delta_files) if delta_files else None
    file_violations, func_violations = _collect_structural_violations(
        project_root, checkable, delta_files
    )
    cache_violations = _cache_payload_violations_for_language(project_root, language)
    type_checking_violations = _type_checking_violations_for_language(
        project_root, language
    )
    return build_quality_check_result(
        lint_result,
        file_violations,
        func_violations,
        cache_violations,
        type_checking_violations,
    )


def build_quality_check_result(
    lint_result: CheckResult,
    file_violations: list[FileSizeViolation],
    func_violations: list[FunctionLengthViolation],
    cache_violations: list[str],
    type_checking_violations: list[str],
) -> QualityCheckResult:
    """Assemble QualityCheckResult from lint, structural, and source-audit findings."""
    errors = _build_quality_errors(lint_result.errors, file_violations, func_violations)
    output = _build_quality_output(lint_result.output, file_violations, func_violations)
    errors, output = _apply_all_source_audits(
        errors, output, cache_violations, type_checking_violations
    )
    success = (
        lint_result.success
        and len(file_violations) == 0
        and len(func_violations) == 0
        and not cache_violations
        and not type_checking_violations
    )
    return QualityCheckResult(
        check_type="quality",
        success=success,
        output=output,
        errors=errors,
        warnings=list(lint_result.warnings),
        files_modified=list(lint_result.files_modified),
        file_size_violations=file_violations,
        function_length_violations=func_violations,
    )


def _cache_payload_violations_for_language(
    project_root: Path, language: str
) -> list[str]:
    """Audit cache-payload stability once per language pass (Python-only target)."""
    # AI: Scoping to "python" avoids redundant rescans of the same two Python
    # source files when a project also runs Swift/JS/etc. framework adapters.
    if language != "python":
        return []
    return check_cache_payload_stability(project_root)


def _type_checking_violations_for_language(
    project_root: Path, language: str
) -> list[str]:
    """Audit the TYPE_CHECKING ban once per language pass (Python-only target)."""
    # AI: Python-only for the same reason as the cache-payload audit — the rule
    # and the scanned roots are Python-specific.
    if language != "python":
        return []
    return check_type_checking_ban(project_root)


def _apply_all_source_audits(
    errors: list[str],
    output: str,
    cache_violations: list[str],
    type_checking_violations: list[str],
) -> tuple[list[str], str]:
    """Fold every source-level audit's findings into quality errors/output."""
    errors, output = _apply_source_audit_violations(
        errors, output, cache_violations, "Cache-payload stability violation"
    )
    return _apply_source_audit_violations(
        errors, output, type_checking_violations, "TYPE_CHECKING ban violation"
    )


def _apply_source_audit_violations(
    errors: list[str], output: str, violations: list[str], label: str
) -> tuple[list[str], str]:
    """Fold source-audit violations into quality errors/output under ``label``."""
    errors = [*errors, *(f"{label}: {v}" for v in violations)]
    if violations:
        output = f"{output}\n\n{label}s:\n" + "\n".join(violations)
    return errors, output


def _collect_structural_violations(
    project_root: Path,
    checkable: list[Path] | None,
    delta_files: list[Path] | None,
) -> tuple[list[FileSizeViolation], list[FunctionLengthViolation]]:
    """Collect and optionally filter structural violations for quality checks."""
    file_violations, func_violations = run_quality_checks_for_all_languages(
        project_root,
        files=checkable,
    )
    if not delta_files:
        return file_violations, func_violations
    return filter_preexisting_structural_violations(
        project_root,
        delta_files,
        file_violations,
        func_violations,
    )


def _build_quality_errors(
    lint_errors: list[str],
    file_violations: list[FileSizeViolation],
    func_violations: list[FunctionLengthViolation],
) -> list[str]:
    """Build error messages for quality check."""
    errors = list(lint_errors)
    for v in file_violations:
        msg = f"File size violation: {v.file} has {v.lines} lines "
        msg += f"(max: {v.max_lines}, excess: {v.excess})"
        errors.append(msg)
    for v in func_violations:
        msg = f"Function length violation: {v.file}:{v.function}() at line "
        msg += f"{v.line} has {v.lines} lines "
        msg += f"(max: {v.max_lines}, excess: {v.excess})"
        errors.append(msg)
    return errors


def _build_quality_output(
    lint_output: str,
    file_violations: list[FileSizeViolation],
    func_violations: list[FunctionLengthViolation],
) -> str:
    """Build output message for quality check."""
    parts = [lint_output]
    if file_violations:
        parts.append(
            f"\nFile size violations: {len(file_violations)} file(s) "
            + f"exceed {MAX_FILE_LINES} lines"
        )
    if func_violations:
        parts.append(
            f"\nFunction length violations: {len(func_violations)} "
            + f"function(s) exceed {MAX_FUNCTION_LINES} lines"
        )
    return "\n".join(parts)
