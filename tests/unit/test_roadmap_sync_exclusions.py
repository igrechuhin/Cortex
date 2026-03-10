"""
Unit tests for roadmap_sync exclusion patterns (path-segment-aware).

Ensures production files containing substrings like 'test', 'example',
'demo', or 'sample' are not incorrectly excluded from TODO scanning.
"""

from pathlib import Path
from tempfile import TemporaryDirectory

from cortex.validation.roadmap_sync import TodoItem, scan_codebase_todos


def _make_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    written = path.write_text(content, encoding="utf-8")
    assert isinstance(written, int)


def _paths_from_todos(todos: list[TodoItem]) -> set[str]:
    return {t.file_path for t in todos}


class TestRoadmapSyncExclusions:
    """Regression tests for path-segment-aware exclusion patterns."""

    def test_test_directory_excluded(self) -> None:
        """Path under tests/ or test/ is excluded."""
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _make_file(root / "src" / "tests" / "unit" / "foo.py", "# TODO: x\n")
            _make_file(root / "src" / "test" / "bar.py", "# TODO: y\n")
            result = scan_codebase_todos(root)
            paths = _paths_from_todos(result)
            assert "src/tests/unit/foo.py" not in paths
            assert "src/test/bar.py" not in paths

    def test_contest_not_excluded(self) -> None:
        """src/contest/ (contains 'test' substring) is NOT excluded."""
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _make_file(root / "src" / "contest" / "runner.py", "# TODO: implement\n")
            result = scan_codebase_todos(root)
            paths = _paths_from_todos(result)
            assert "src/contest/runner.py" in paths

    def test_test_in_name_not_prefix_not_excluded(self) -> None:
        """Production file with 'test' in name but not test_ prefix is NOT excluded."""
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _make_file(
                root / "src" / "cortex" / "validation" / "my_test_config.py",
                "# TODO: refactor\n",
            )
            result = scan_codebase_todos(root)
            paths = _paths_from_todos(result)
            assert "src/cortex/validation/my_test_config.py" in paths

    def test_examples_directory_excluded(self) -> None:
        """Path under examples/ or example/ is excluded."""
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _make_file(root / "src" / "examples" / "demo.py", "# TODO: remove\n")
            _make_file(root / "src" / "example" / "sample.py", "# TODO: doc\n")
            result = scan_codebase_todos(root)
            paths = _paths_from_todos(result)
            assert "src/examples/demo.py" not in paths
            assert "src/example/sample.py" not in paths

    def test_demonstration_not_excluded(self) -> None:
        """src/demonstration.py (contains 'demo' substring) is NOT excluded."""
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _make_file(root / "src" / "demonstration.py", "# TODO: finish\n")
            result = scan_codebase_todos(root)
            paths = _paths_from_todos(result)
            assert "src/demonstration.py" in paths

    def test_test_prefix_py_excluded(self) -> None:
        """File named test_*.py is excluded (at any path under src)."""
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _make_file(root / "src" / "test_integration.py", "# TODO: e2e\n")
            _make_file(root / "src" / "pkg" / "test_helpers.py", "# TODO: share\n")
            result = scan_codebase_todos(root)
            paths = _paths_from_todos(result)
            assert "src/test_integration.py" not in paths
            assert "src/pkg/test_helpers.py" not in paths

    def test_latest_metrics_not_excluded(self) -> None:
        """src/cortex/latest_metrics.py (contains 'test' substring) is NOT excluded."""
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _make_file(root / "src" / "cortex" / "latest_metrics.py", "# TODO: cache\n")
            result = scan_codebase_todos(root)
            paths = _paths_from_todos(result)
            assert "src/cortex/latest_metrics.py" in paths

    def test_conftest_excluded(self) -> None:
        """conftest.py at any path under src is excluded."""
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _make_file(root / "src" / "conftest.py", "# TODO: fixture\n")
            _make_file(root / "src" / "pkg" / "conftest.py", "# TODO: other\n")
            result = scan_codebase_todos(root)
            paths = _paths_from_todos(result)
            assert "src/conftest.py" not in paths
            assert "src/pkg/conftest.py" not in paths

    def test_demos_directory_excluded(self) -> None:
        """Path under demos/ or demo/ is excluded."""
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _make_file(root / "src" / "demos" / "app.py", "# TODO: ui\n")
            _make_file(root / "src" / "demo" / "script.py", "# TODO: run\n")
            result = scan_codebase_todos(root)
            paths = _paths_from_todos(result)
            assert "src/demos/app.py" not in paths
            assert "src/demo/script.py" not in paths

    def test_samples_directory_excluded(self) -> None:
        """Path under samples/ or sample/ is excluded."""
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _make_file(root / "src" / "samples" / "config.py", "# TODO: doc\n")
            result = scan_codebase_todos(root)
            paths = _paths_from_todos(result)
            assert "src/samples/config.py" not in paths
