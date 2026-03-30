"""Unit tests for `file_language_router`.

This suite follows the roadmap plan for QG-S7: per-extension routing,
project-file collection, output parsing, mocked synapse dispatch, and a
regression guard for `execute_quality()`.
"""

from __future__ import annotations

from pathlib import Path
from subprocess import CompletedProcess
from typing import Final
from unittest.mock import MagicMock, patch

from cortex.core.constants import EXTENSION_SCRIPT_MAP
from cortex.services.framework_adapters.base import CheckResult
from cortex.tools.execution import file_language_router as flr
from cortex.tools.execution.file_language_router import (
    collect_project_files,
    route_files,
    run_quality_checks_for_all_languages,
)
from cortex.tools.execution.pre_commit_helpers_models import (
    FileSizeViolation,
    QualityCheckResult,
)
from cortex.tools.execution.pre_commit_pipeline_quality import execute_quality


def test_route_files_groups_py_files_under_python() -> None:
    files = [Path("a.py"), Path("b.py"), Path("c.swift")]
    result = route_files(files)
    assert result["python"] == [Path("a.py"), Path("b.py")]


def test_route_files_groups_swift_files_under_swift() -> None:
    files = [Path("a.swift"), Path("b.swift")]
    assert route_files(files) == {"swift": [Path("a.swift"), Path("b.swift")]}


def test_route_files_skips_unknown_extensions() -> None:
    assert route_files([Path("a.js"), Path("b.ts"), Path("c.go")]) == {}


def test_route_files_mixed_language_repo() -> None:
    result = route_files([Path("a.py"), Path("b.swift"), Path("c.rs")])
    assert set(result.keys()) == {"python", "swift"}
    assert result["python"] == [Path("a.py")]
    assert result["swift"] == [Path("b.swift")]


def test_route_files_empty_list() -> None:
    assert route_files([]) == {}


def test_route_files_uses_extension_map_override() -> None:
    result = route_files(
        [Path("a.ts"), Path("b.py")], extension_map={".ts": "typescript"}
    )
    assert result == {"typescript": [Path("a.ts")]}


def test_collect_project_files_includes_py_and_swift(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    _ = (tmp_path / "src" / "foo.py").write_text("pass", encoding="utf-8")
    (tmp_path / "Sources").mkdir()
    _ = (tmp_path / "Sources" / "Bar.swift").write_text("// swift", encoding="utf-8")

    names = {f.name for f in collect_project_files(tmp_path)}
    assert "foo.py" in names
    assert "Bar.swift" in names


def test_collect_project_files_excludes_pycache(tmp_path: Path) -> None:
    cache = tmp_path / "__pycache__"
    cache.mkdir()
    _ = (cache / "compiled.pyc").write_text("", encoding="utf-8")
    assert not any("__pycache__" in str(f) for f in collect_project_files(tmp_path))


def test_collect_project_files_includes_test_files(tmp_path: Path) -> None:
    # CRITICAL: test files must NOT be excluded — this was the TradeWing bug.
    (tmp_path / "Tests").mkdir()
    _ = (tmp_path / "Tests" / "FooTests.swift").write_text("// test", encoding="utf-8")
    assert any(f.name == "FooTests.swift" for f in collect_project_files(tmp_path))


def test_collect_project_files_excludes_dot_git(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    _ = (tmp_path / ".git" / "config").write_text("", encoding="utf-8")
    assert not any(".git" in str(f) for f in collect_project_files(tmp_path))


def test_collect_project_files_excludes_models_py(tmp_path: Path) -> None:
    _ = (tmp_path / "models.py").write_text("class M: pass", encoding="utf-8")
    assert not any(f.name == "models.py" for f in collect_project_files(tmp_path))


def test_collect_project_files_returns_sorted_paths(tmp_path: Path) -> None:
    for name in ["z.py", "a.py", "m.swift"]:
        _ = (tmp_path / name).write_text("", encoding="utf-8")
    result = collect_project_files(tmp_path)
    assert result == sorted(result)


def test_collect_project_files_excludes_node_modules(tmp_path: Path) -> None:
    nm = tmp_path / "node_modules" / "pkg"
    nm.mkdir(parents=True)
    _ = (nm / "index.js").write_text("", encoding="utf-8")
    assert not any("node_modules" in str(f) for f in collect_project_files(tmp_path))


def test_parse_file_size_violations_python_format(tmp_path: Path) -> None:
    output = (
        "File size violations detected:\n\n"
        "  src/cortex/foo.py: 450 lines (max: 400, excess: 50)\n"
    )
    result = flr._parse_file_size_violations(  # pyright: ignore[reportPrivateUsage]
        output, tmp_path
    )
    assert len(result) == 1
    assert result[0].lines == 450
    assert result[0].max_lines == 400
    assert result[0].excess == 50


def test_parse_file_size_violations_swift_format(tmp_path: Path) -> None:
    output = "  Sources/Foo/Bar.swift: 450 lines (max: 400, excess: 50)\n"
    result = flr._parse_file_size_violations(  # pyright: ignore[reportPrivateUsage]
        output, tmp_path
    )
    assert len(result) == 1
    assert result[0].file.endswith("Bar.swift")
    assert result[0].lines == 450


def test_parse_file_size_violations_no_violations(tmp_path: Path) -> None:
    output = "All files within size limits (400 lines)\n"
    violations = flr._parse_file_size_violations(  # pyright: ignore[reportPrivateUsage]
        output, tmp_path
    )
    assert violations == []


def test_parse_file_size_violations_multiple(tmp_path: Path) -> None:
    output = (
        "  src/a.py: 500 lines (max: 400, excess: 100)\n"
        "  src/b.py: 450 lines (max: 400, excess: 50)\n"
    )
    violations = flr._parse_file_size_violations(  # pyright: ignore[reportPrivateUsage]
        output, tmp_path
    )
    assert len(violations) == 2


def test_parse_file_size_violations_ignores_unrecognised_lines(
    tmp_path: Path,
) -> None:
    output = "some unexpected line\nTotal violations: 0 file(s) exceed 400 lines\n"
    violations = flr._parse_file_size_violations(  # pyright: ignore[reportPrivateUsage]
        output, tmp_path
    )
    assert violations == []


def test_parse_file_size_violations_excess_consistent(tmp_path: Path) -> None:
    output = "  src/foo.py: 450 lines (max: 400, excess: 50)\n"
    result = flr._parse_file_size_violations(  # pyright: ignore[reportPrivateUsage]
        output, tmp_path
    )
    v = result[0]
    assert v.excess == v.lines - v.max_lines


def test_parse_function_length_violations_python_format(tmp_path: Path) -> None:
    output = (
        "  src/cortex/foo.py:\n"
        "    my_func() at line 42: 35 lines (max: 30, excess: 5)\n"
    )
    result = (
        flr._parse_function_length_violations(  # pyright: ignore[reportPrivateUsage]
            output,
            tmp_path,
            language="python",
        )
    )
    assert len(result) == 1
    v = result[0]
    assert v.function == "my_func"
    assert v.line == 42
    assert v.lines == 35
    assert v.max_lines == 30
    assert v.excess == 5


def test_parse_function_length_violations_swift_format(tmp_path: Path) -> None:
    output = "  Sources/Foo/Bar.swift:42: myFunc() — 35 lines (max: 30, excess: 5)\n"
    result = (
        flr._parse_function_length_violations(  # pyright: ignore[reportPrivateUsage]
            output, tmp_path, language="swift"
        )
    )
    assert len(result) == 1
    assert result[0].function == "myFunc"
    assert result[0].line == 42


def test_parse_function_length_violations_no_violations(tmp_path: Path) -> None:
    output = "All functions within length limits (30 lines)\n"
    violations = (
        flr._parse_function_length_violations(  # pyright: ignore[reportPrivateUsage]
            output, tmp_path, language="python"
        )
    )
    assert violations == []


def test_parse_function_length_violations_multiple_python(tmp_path: Path) -> None:
    output = (
        "  src/foo.py:\n"
        "    func_a() at line 10: 35 lines (max: 30, excess: 5)\n"
        "    func_b() at line 50: 40 lines (max: 30, excess: 10)\n"
    )
    result = (
        flr._parse_function_length_violations(  # pyright: ignore[reportPrivateUsage]
            output, tmp_path, language="python"
        )
    )
    assert len(result) == 2
    assert {v.function for v in result} == {"func_a", "func_b"}


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

    def side_effect(
        project_root: Path,
        language: str,
        script_name: str,
        files: list[Path],
    ) -> CheckResult:
        del project_root, files
        if language == "python" and "file_sizes" in script_name:
            return CheckResult(
                check_type="t",
                success=False,
                output=py_output,
                errors=[],
                warnings=[],
                files_modified=[],
            )
        if language == "swift" and "file_sizes" in script_name:
            return CheckResult(
                check_type="t",
                success=False,
                output=swift_output,
                errors=[],
                warnings=[],
                files_modified=[],
            )
        return CheckResult(
            check_type="t",
            success=True,
            output="All ok",
            errors=[],
            warnings=[],
            files_modified=[],
        )

    mock_run.side_effect = side_effect

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

    # _run_script_with_files should be called with swift language.
    calls = mock_run.call_args_list
    assert any(c.args[1] == "swift" for c in calls)


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

    mock_router.assert_called_once_with(tmp_path)
    assert result.success


def test_execute_quality_calls_router_for_python(tmp_path: Path) -> None:
    """Regression: Python projects still go through the router."""
    adapter = _make_mock_adapter(tmp_path)
    with patch(
        "cortex.tools.execution.pre_commit_pipeline_quality.run_quality_checks_for_all_languages",
    ) as mock_router:
        mock_router.return_value = ([], [])
        _ = execute_quality(adapter, "python")

    mock_router.assert_called_once_with(tmp_path)


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


def test_rel_file_str_normalizes_absolute_paths(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    abs_path = tmp_path / "src" / "a.py"
    _ = abs_path.write_text("", encoding="utf-8")

    result = flr._rel_file_str(  # pyright: ignore[reportPrivateUsage]
        str(abs_path), tmp_path
    )
    assert result == "src/a.py"


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


def test_extension_script_map_is_sane() -> None:
    # Minimal sanity check that keeps route_files tests meaningful.
    assert ".py" in EXTENSION_SCRIPT_MAP
    assert ".swift" in EXTENSION_SCRIPT_MAP
