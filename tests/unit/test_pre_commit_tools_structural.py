"""Structural and size tests extracted from test_pre_commit_tools."""

from __future__ import annotations

import ast
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from cortex.core.constants import FUNCTION_LENGTH_EXCLUDED_PATHS, MAX_FILE_LINES
from cortex.tools.execution.pre_commit_helpers_quality import (
    check_file_sizes,
    check_function_lengths_in_file,
    count_file_lines,
    get_docstring_range,
)
from cortex.tools.execution.pre_commit_pipeline_quality import (
    changed_relative_files,
    filter_preexisting_structural_violations,
    read_head_source,
    run_git_diff_output,
)

_EXECUTE_REQUIRED = {
    "test_timeout": 300,
    "coverage_threshold": 0.9,
    "strict_mode": False,
}


class TestCountFileLines:
    """Test count_file_lines helper function."""

    def test_count_lines_simple_file(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            _ = f.write("x = 1\n")
            _ = f.write("y = 2\n")
            _ = f.write("z = 3\n")
            f.flush()
            path = Path(f.name)

        try:
            count = count_file_lines(path)
            assert count == 3
        finally:
            path.unlink()

    def test_count_lines_with_comments_and_blanks(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            _ = f.write("# This is a comment\n")
            _ = f.write("\n")
            _ = f.write("x = 1\n")
            _ = f.write("  # Indented comment\n")
            _ = f.write("\n")
            _ = f.write("y = 2\n")
            f.flush()
            path = Path(f.name)

        try:
            count = count_file_lines(path)
            assert count == 2
        finally:
            path.unlink()

    def test_count_lines_with_docstring(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            _ = f.write("x = 1\n")
            _ = f.write("y = 2\n")
            f.flush()
            path = Path(f.name)

        try:
            count = count_file_lines(path)
            assert count == 2
        finally:
            path.unlink()

    def test_count_lines_nonexistent_file(self) -> None:
        count = count_file_lines(Path("/nonexistent/file.py"))
        assert count == 0


class TestCheckFileSizes:
    def test_no_violations_when_no_src(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            violations = check_file_sizes(Path(tmpdir))
            assert violations == []

    def test_no_violations_when_files_within_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            src_dir = project_root / "src"
            src_dir.mkdir()
            _ = (src_dir / "small.py").write_text("x = 1\ny = 2\n")
            violations = check_file_sizes(project_root)
            assert violations == []

    def test_detects_file_size_violation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            src_dir = project_root / "src"
            src_dir.mkdir()
            large_content = "\n".join(
                [f"x{i} = {i}" for i in range(MAX_FILE_LINES + 50)]
            )
            _ = (src_dir / "large.py").write_text(large_content)
            violations = check_file_sizes(project_root)
            assert len(violations) == 1
            assert violations[0].file == "src/large.py"

    def test_skips_test_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            src_dir = project_root / "src"
            src_dir.mkdir()
            large_content = "\n".join(
                [f"x{i} = {i}" for i in range(MAX_FILE_LINES + 50)]
            )
            _ = (src_dir / "test_large.py").write_text(large_content)
            violations = check_file_sizes(project_root)
            assert violations == []


class TestGetDocstringRange:
    def test_returns_range_when_function_has_docstring(self) -> None:
        source = 'def foo():\n    """Docstring here."""\n    pass\n'
        tree = ast.parse(source)
        func = tree.body[0]
        assert isinstance(func, ast.FunctionDef)
        result = get_docstring_range(func)
        assert result is not None
        assert result == (2, 2)

    def test_returns_none_when_no_docstring(self) -> None:
        source = "def bar():\n    pass\n"
        tree = ast.parse(source)
        func = tree.body[0]
        assert isinstance(func, ast.FunctionDef)
        assert get_docstring_range(func) is None


def _git_commit_short_function_module(root: Path, py_file: Path) -> None:
    short_body = "\n".join(f"    x{i} = {i}" for i in range(10))
    _ = py_file.write_text(f"def short_func():\n{short_body}\n    return x0\n")
    _ = subprocess.run(["git", "add", "."], cwd=root, check=True, capture_output=True)
    _ = subprocess.run(
        ["git", "commit", "-m", "init"], cwd=root, check=True, capture_output=True
    )


def _write_long_function_version_of_short_func(py_file: Path) -> None:
    long_body = "\n".join(f"    x{i} = {i}" for i in range(35))
    _ = py_file.write_text(f"def short_func():\n{long_body}\n    return x0\n")


class TestStructuralViolationFiltering:
    def _init_git_repo(self, root: Path) -> None:
        _ = subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
        _ = subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=root,
            check=True,
            capture_output=True,
        )
        _ = subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=root,
            check=True,
            capture_output=True,
        )

    def test_reports_violation_when_lines_added_inside_existing_function(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            src = root / "src"
            src.mkdir()
            py_file = src / "module.py"
            self._init_git_repo(root)
            _git_commit_short_function_module(root, py_file)
            _write_long_function_version_of_short_func(py_file)
            from cortex.tools.execution.pre_commit_helpers_models import (
                FunctionLengthViolation,
            )

            func_violations = [
                FunctionLengthViolation(
                    file="src/module.py",
                    function="short_func",
                    line=1,
                    lines=35,
                    max_lines=30,
                    excess=5,
                )
            ]
            filtered_file, filtered_func = filter_preexisting_structural_violations(
                root, [py_file], [], func_violations
            )
            assert filtered_file == []
            assert len(filtered_func) == 1 and filtered_func[0].function == "short_func"

    def test_run_git_diff_output_handles_binary_bytes(self) -> None:
        mocked = MagicMock(returncode=0, stdout=b"\x89PNG\r\n@@ -1 +1 @@\n")
        with patch(
            "cortex.tools.execution.pre_commit_pipeline_quality.subprocess.run",
            return_value=mocked,
        ):
            output = run_git_diff_output(Path("/tmp"), ["git", "diff", "--unified=0"])
        assert output is not None
        assert "@@ -1 +1 @@" in output

    def test_read_head_source_handles_binary_bytes(self) -> None:
        exists = MagicMock(returncode=0, stdout=b"", stderr=b"")
        show = MagicMock(returncode=0, stdout=b"\x89PNG\r\n", stderr=b"")
        with patch(
            "cortex.tools.execution.pre_commit_pipeline_quality.subprocess.run",
            side_effect=[exists, show],
        ):
            output = read_head_source(Path("/tmp"), "Tests/Charts/snapshot.png")
        assert output is not None
        assert "PNG" in output

    def test_changed_relative_files_skips_non_checkable_extensions(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            src = root / "src"
            src.mkdir()
            py_file = src / "module.py"
            png_file = src / "chart.png"
            _ = py_file.write_text("x = 1\n")
            _ = png_file.write_bytes(b"\x89PNG\r\n")
            changed = changed_relative_files(root, [py_file, png_file])
            assert "src/module.py" in changed
            assert "src/chart.png" not in changed


def test_no_oversized_files_in_src() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    violations = check_file_sizes(repo_root)
    if violations:
        lines = [
            f"  {v.file}: {v.lines} logical lines (max {v.max_lines}, excess {v.excess})"
            for v in sorted(violations, key=lambda x: -x.excess)
        ]
        raise AssertionError(
            f"{len(violations)} oversized file(s) detected:\n" + "\n".join(lines)
        )


def test_no_oversized_functions_in_src() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    src = repo_root / "src" / "cortex"
    excluded = frozenset(FUNCTION_LENGTH_EXCLUDED_PATHS)
    all_violations: list[tuple[str, str, int, int]] = []
    for py_file in sorted(src.glob("**/*.py")):
        if "__pycache__" in str(py_file) or py_file.name.startswith("test_"):
            continue
        try:
            rel = py_file.relative_to(repo_root).as_posix()
        except ValueError:
            rel = str(py_file)
        if rel in excluded:
            continue
        for func_name, logical_lines, start_line in check_function_lengths_in_file(
            py_file
        ):
            all_violations.append((rel, func_name, start_line, logical_lines))
    if all_violations:
        lines = [
            f"  {rel}:{start_line} {func}() — {ll} logical lines"
            for rel, func, start_line, ll in sorted(all_violations, key=lambda x: -x[3])
        ]
        raise AssertionError(
            f"{len(all_violations)} oversized function(s) detected:\n"
            + "\n".join(lines)
        )
