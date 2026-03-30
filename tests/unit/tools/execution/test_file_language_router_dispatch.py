"""Unit tests for run_quality_checks_for_all_languages(), execute_quality(),
and low-level helpers (_files_env_value, _execute_synapse_with_files_env,
_run_script_with_files, _rel_file_str).
"""

from __future__ import annotations

from functools import partial
from pathlib import Path
from subprocess import CompletedProcess
from typing import Final
from unittest.mock import MagicMock, patch

from cortex.services.framework_adapters.base import CheckResult
from cortex.tools.execution import file_language_router as flr
from cortex.tools.execution.file_language_router import (
    run_quality_checks_for_all_languages,
)
from cortex.tools.execution.pre_commit_helpers_models import (
    FileSizeViolation,
    QualityCheckResult,
)
from cortex.tools.execution.pre_commit_pipeline_quality import execute_quality

# ---------------------------------------------------------------------------
# run_quality_checks_for_all_languages()
# ---------------------------------------------------------------------------


def test_run_returns_empty_when_no_supported_files(tmp_path: Path) -> None:
    _ = (tmp_path / "foo.js").write_text("", encoding="utf-8")
    file_v, func_v = run_quality_checks_for_all_languages(tmp_path)
    assert file_v == []
    assert func_v == []


@patch("cortex.tools.execution.file_language_router._run_script_with_files")
def test_run_invokes_check_file_sizes_and_check_function_lengths(
    mock_run: MagicMock,
    tmp_path: Path,
) -> None:
    mock_run.return_value = CheckResult(
        check_type="test",
        success=True,
        output="ok",
        errors=[],
        warnings=[],
        files_modified=[],
    )
    (tmp_path / "src").mkdir()
    _ = (tmp_path / "src" / "foo.py").write_text("x = 1", encoding="utf-8")

    _ = run_quality_checks_for_all_languages(tmp_path)

    script_names = {c.args[2] for c in mock_run.call_args_list}
    assert "check_file_sizes.py" in script_names
    assert "check_function_lengths.py" in script_names


@patch("cortex.tools.execution.file_language_router._run_script_with_files")
def test_run_returns_violations_parsed_from_script_output(
    mock_run: MagicMock,
    tmp_path: Path,
) -> None:
    output = "  src/foo.py: 450 lines (max: 400, excess: 50)\n"
    mock_run.return_value = CheckResult(
        check_type="test",
        success=False,
        output=output,
        errors=[],
        warnings=[],
        files_modified=[],
    )
    (tmp_path / "src").mkdir()
    _ = (tmp_path / "src" / "foo.py").write_text("x = 1", encoding="utf-8")

    file_v, _ = run_quality_checks_for_all_languages(tmp_path)
    assert len(file_v) >= 1


@patch("cortex.tools.execution.file_language_router._run_script_with_files")
def test_run_merges_violations_across_languages(
    mock_run: MagicMock,
    tmp_path: Path,
) -> None:
    py_output = "  src/foo.py: 450 lines (max: 400, excess: 50)\n"
    swift_output = "  Sources/Bar.swift: 410 lines (max: 400, excess: 10)\n"

    mock_run.side_effect = partial(
        _multilang_side_effect,
        py_output=py_output,
        swift_output=swift_output,
    )

    (tmp_path / "src").mkdir()
    _ = (tmp_path / "src" / "foo.py").write_text("x = 1", encoding="utf-8")
    (tmp_path / "Sources").mkdir()
    _ = (tmp_path / "Sources" / "Bar.swift").write_text("// x", encoding="utf-8")

    file_v, _ = run_quality_checks_for_all_languages(tmp_path)
    assert len(file_v) == 2


@patch("cortex.tools.execution.file_language_router._run_script_with_files")
def test_run_accepts_explicit_files_list(
    mock_run: MagicMock,
    tmp_path: Path,
) -> None:
    """Explicit files= parameter bypasses collect_project_files."""
    mock_run.return_value = CheckResult(
        check_type="t",
        success=True,
        output="All ok",
        errors=[],
        warnings=[],
        files_modified=[],
    )

    explicit = [tmp_path / "Foo.swift"]
    _ = run_quality_checks_for_all_languages(tmp_path, files=explicit)

    calls = mock_run.call_args_list
    assert any(c.args[1] == "swift" for c in calls)


# ---------------------------------------------------------------------------
# execute_quality() regression tests
# ---------------------------------------------------------------------------


def _make_mock_adapter(project_root: Path) -> MagicMock:
    adapter = MagicMock()
    adapter.project_root = project_root
    adapter.lint_code.return_value = CheckResult(
        check_type="lint",
        success=True,
        output="ok",
        errors=[],
        warnings=[],
        files_modified=[],
    )
    return adapter


def test_execute_quality_calls_router_for_swift(tmp_path: Path) -> None:
    """Regression: quality gate must NOT be skipped for Swift projects."""
    adapter = _make_mock_adapter(tmp_path)
    with patch(
        "cortex.tools.execution.pre_commit_pipeline_quality.run_quality_checks_for_all_languages",
    ) as mock_router:
        mock_router.return_value = ([], [])
        result: QualityCheckResult = execute_quality(adapter, "swift")

    mock_router.assert_called_once_with(tmp_path, files=[])
    assert result.success


def test_execute_quality_calls_router_for_python(tmp_path: Path) -> None:
    """Regression: Python projects still go through the router."""
    adapter = _make_mock_adapter(tmp_path)
    with patch(
        "cortex.tools.execution.pre_commit_pipeline_quality.run_quality_checks_for_all_languages",
    ) as mock_router:
        mock_router.return_value = ([], [])
        _ = execute_quality(adapter, "python")

    mock_router.assert_called_once_with(tmp_path, files=[])


def test_execute_quality_fails_on_file_size_violation(tmp_path: Path) -> None:
    adapter = _make_mock_adapter(tmp_path)
    violation = FileSizeViolation(file="Foo.swift", lines=450, max_lines=400, excess=50)
    with patch(
        "cortex.tools.execution.pre_commit_pipeline_quality.run_quality_checks_for_all_languages",
        return_value=([violation], []),
    ):
        result: QualityCheckResult = execute_quality(adapter, "swift")

    assert not result.success
    assert len(result.file_size_violations) == 1
    assert result.file_size_violations[0].file == "Foo.swift"


def _multilang_side_effect(
    project_root: Path,
    language: str,
    script_name: str,
    files: list[Path],
    *,
    py_output: str,
    swift_output: str,
) -> CheckResult:
    """Return synthetic script output by language for routing tests."""
    del project_root, files
    if language == "python" and "file_sizes" in script_name:
        return _mock_check_result(success=False, output=py_output)
    if language == "swift" and "file_sizes" in script_name:
        return _mock_check_result(success=False, output=swift_output)
    return _mock_check_result(success=True, output="All ok")


def _mock_check_result(*, success: bool, output: str) -> CheckResult:
    """Create a standard CheckResult payload for test doubles."""
    return CheckResult(
        check_type="t",
        success=success,
        output=output,
        errors=[],
        warnings=[],
        files_modified=[],
    )


# ---------------------------------------------------------------------------
# _files_env_value()
# ---------------------------------------------------------------------------


def test_files_env_value_returns_newline_separated_resolved_paths(
    tmp_path: Path,
) -> None:
    a = tmp_path / "a.py"
    b = tmp_path / "b.py"
    _ = a.write_text("", encoding="utf-8")
    _ = b.write_text("", encoding="utf-8")

    result = flr._files_env_value([a, b])  # pyright: ignore[reportPrivateUsage]
    expected: Final[str] = f"{a.resolve()}\n{b.resolve()}"
    assert result == expected


# ---------------------------------------------------------------------------
# _execute_synapse_with_files_env()
# ---------------------------------------------------------------------------


@patch("cortex.tools.execution.file_language_router.subprocess.run")
def test_execute_synapse_with_files_env_calls_subprocess_with_files_env(
    mock_run: MagicMock,
    tmp_path: Path,
) -> None:
    # Arrange
    python_bin = Path("python3")
    script_path = tmp_path / "script.py"
    _ = script_path.write_text("print('x')", encoding="utf-8")
    f1 = tmp_path / "a.py"
    _ = f1.write_text("x = 1", encoding="utf-8")

    completed = CompletedProcess(
        args=[str(python_bin), str(script_path)],
        returncode=0,
        stdout="OK",
        stderr="",
    )
    mock_run.return_value = completed

    # Act
    result = flr._execute_synapse_with_files_env(  # pyright: ignore[reportPrivateUsage]
        python_bin=python_bin,
        script_path=script_path,
        project_root=tmp_path,
        files=[f1],
        check_type="swift_check_file_sizes.py",
    )

    # Assert
    assert result.success
    mock_run.assert_called_once()
    kwargs = mock_run.call_args.kwargs
    assert kwargs["cwd"] == tmp_path
    env = kwargs["env"]
    assert env["FILES"] == str(f1.resolve())


# ---------------------------------------------------------------------------
# _rel_file_str()
# ---------------------------------------------------------------------------


def test_rel_file_str_normalizes_absolute_paths(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    abs_path = tmp_path / "src" / "a.py"
    _ = abs_path.write_text("", encoding="utf-8")

    result = flr._rel_file_str(  # pyright: ignore[reportPrivateUsage]
        str(abs_path), tmp_path
    )
    assert result == "src/a.py"


# ---------------------------------------------------------------------------
# _run_script_with_files()
# ---------------------------------------------------------------------------


@patch("cortex.tools.execution.file_language_router.get_cortex_path")
def test_run_script_with_files_returns_skipped_when_missing_script(
    mock_get_cortex_path: MagicMock,
    tmp_path: Path,
) -> None:
    synapse_root = tmp_path / "cortex" / "synapse"
    mock_get_cortex_path.return_value = synapse_root

    f1 = tmp_path / "a.swift"
    _ = f1.write_text("", encoding="utf-8")
    result = flr._run_script_with_files(  # pyright: ignore[reportPrivateUsage]
        project_root=tmp_path,
        language="swift",
        script_name="check_file_sizes.py",
        files=[f1],
    )

    assert result.success
    assert result.check_type == "swift_check_file_sizes.py"
    assert "skipped" in result.output


@patch("cortex.tools.execution.file_language_router._execute_synapse_with_files_env")
@patch("cortex.tools.execution.file_language_router._resolve_synapse_python_bin")
@patch("cortex.tools.execution.file_language_router.get_cortex_path")
def test_run_script_with_files_calls_execute_when_script_exists(
    mock_get_cortex_path: MagicMock,
    mock_resolve_python: MagicMock,
    mock_execute: MagicMock,
    tmp_path: Path,
) -> None:
    synapse_root = tmp_path / "synapse"
    mock_get_cortex_path.return_value = synapse_root
    mock_resolve_python.return_value = Path("python3")
    mock_execute.return_value = CheckResult(
        check_type="swift_check_file_sizes.py",
        success=True,
        output="ok",
        errors=[],
        warnings=[],
        files_modified=[],
    )

    script_path = synapse_root / "scripts" / "swift" / "check_file_sizes.py"
    script_path.parent.mkdir(parents=True)
    _ = script_path.write_text("print('x')", encoding="utf-8")

    f1 = tmp_path / "a.swift"
    _ = f1.write_text("", encoding="utf-8")
    result = flr._run_script_with_files(  # pyright: ignore[reportPrivateUsage]
        project_root=tmp_path,
        language="swift",
        script_name="check_file_sizes.py",
        files=[f1],
    )

    assert result.success
    mock_execute.assert_called_once()
    assert mock_execute.call_args.args[3] == [f1]
