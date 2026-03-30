"""Quality check logic for the pre-commit pipeline.

Extracted from pre_commit_pipeline_processors to keep files under 400 lines.
"""

from pathlib import Path

from cortex.core.constants import (
    FUNCTION_LENGTH_EXCLUDED_PATHS,
    MAX_FILE_LINES,
    MAX_FUNCTION_LINES,
)
from cortex.services.framework_adapters.base import FrameworkAdapter
from cortex.tools.execution.file_language_router import (
    run_quality_checks_for_all_languages,
)
from cortex.tools.execution.pre_commit_helpers_models import (
    FileSizeViolation,
    FunctionLengthViolation,
    QualityCheckResult,
)
from cortex.tools.execution.pre_commit_helpers_quality import (
    check_function_lengths_in_file,
)


def _collect_violations_from_file(
    py_file: Path, project_root: Path
) -> list[FunctionLengthViolation]:
    """Collect function length violations from a single file."""
    violations: list[FunctionLengthViolation] = []
    file_violations = check_function_lengths_in_file(py_file)
    for func_name, logical_lines, start_line in file_violations:
        try:
            relative_path = str(py_file.relative_to(project_root))
        except ValueError:
            relative_path = str(py_file)
        violations.append(
            FunctionLengthViolation(
                file=relative_path,
                function=func_name,
                line=start_line,
                lines=logical_lines,
                max_lines=MAX_FUNCTION_LINES,
                excess=logical_lines - MAX_FUNCTION_LINES,
            )
        )
    return violations


def check_function_lengths(project_root: Path) -> list[FunctionLengthViolation]:
    """Check all Python files for function length violations.

    TODO: migrate callers to file_language_router / synapse scripts when tests
    are updated to use the router path exclusively.
    """
    violations: list[FunctionLengthViolation] = []
    src_dir = project_root / "src"

    if not src_dir.exists():
        return violations

    excluded = frozenset(FUNCTION_LENGTH_EXCLUDED_PATHS)
    for py_file in src_dir.glob("**/*.py"):
        if "__pycache__" in str(py_file) or py_file.name.startswith("test_"):
            continue
        try:
            rel = py_file.relative_to(project_root).as_posix()
        except ValueError:
            rel = str(py_file)
        if rel in excluded:
            continue
        violations.extend(_collect_violations_from_file(py_file, project_root))

    return violations


def execute_quality(adapter: FrameworkAdapter, language: str) -> QualityCheckResult:
    """Execute quality check: linting; file/function sizes via language router."""
    lint_result = adapter.lint_code()
    project_root = adapter.project_root
    file_violations, func_violations = run_quality_checks_for_all_languages(
        project_root
    )

    errors = _build_quality_errors(lint_result.errors, file_violations, func_violations)
    output = _build_quality_output(lint_result.output, file_violations, func_violations)
    success = (
        lint_result.success and len(file_violations) == 0 and len(func_violations) == 0
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
