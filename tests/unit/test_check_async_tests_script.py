"""Unit tests for check_async_tests synapse script.

Tests detection of unawaited coroutines and integration with the script.
"""

from __future__ import annotations

import ast
import sys
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.managers.initialization import get_project_root

# Import script module from synapse scripts (standalone, not from cortex package)
_PROJECT_ROOT = get_project_root()
_SCRIPT_DIR = (
    get_cortex_path(_PROJECT_ROOT, CortexResourceType.SYNAPSE) / "scripts" / "python"
)
if _SCRIPT_DIR.exists():
    sys.path.insert(0, str(_SCRIPT_DIR))


def _collect_async_names_from_tree(tree: ast.AST) -> set[str]:
    """Mirror of script's collection logic for testing."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef):
            names.add(node.name)
    return names


class TestCollectAsyncNames:
    """Test collection of async function names from AST."""

    def test_collects_async_function_names(self) -> None:
        """Async function at module level is collected."""
        tree = ast.parse("async def foo(): pass")
        assert _collect_async_names_from_tree(tree) == {"foo"}

    def test_collects_async_method_names(self) -> None:
        """Async method names are collected."""
        tree = ast.parse("class C:\n  async def bar(self): pass")
        assert _collect_async_names_from_tree(tree) == {"bar"}

    def test_ignores_sync_functions(self) -> None:
        """Sync function names are not collected."""
        tree = ast.parse("def sync_func(): pass")
        assert _collect_async_names_from_tree(tree) == set()

    def test_multiple_async_names(self) -> None:
        """Multiple async names are all collected."""
        tree = ast.parse(
            "async def a(): pass\nasync def b(): pass\nclass X:\n  async def c(self): pass"
        )
        assert _collect_async_names_from_tree(tree) == {"a", "b", "c"}


class TestCheckAsyncTestsScriptModule:
    """Test check_async_tests script when importable."""

    @pytest.fixture(autouse=True)
    def _add_script_path(self) -> Generator[None]:
        if _SCRIPT_DIR.exists():
            if str(_SCRIPT_DIR) not in sys.path:
                sys.path.insert(0, str(_SCRIPT_DIR))
        yield
        if str(_SCRIPT_DIR) in sys.path:
            sys.path.remove(str(_SCRIPT_DIR))

    def test_check_file_reports_unawaited_call(self) -> None:
        """check_file reports when an async name is called without await."""
        if not _SCRIPT_DIR.exists():
            pytest.skip(
                "check_async_tests script dir not present (ref: cleanup-skipped-legacy-tests)"
            )
        import check_async_tests as m  # noqa: PLC0415

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            _ = f.write("async def detect_failure(): pass\n")
            _ = f.write("def test_foo():\n")
            _ = f.write("    detect_failure()  # unawaited\n")
            path = Path(f.name)
        try:
            violations = m.check_file(path, {"detect_failure"})
            assert len(violations) == 1
            assert violations[0][2] == "detect_failure"
        finally:
            path.unlink(missing_ok=True)

    def test_check_file_no_violation_when_awaited(self) -> None:
        """check_file reports no violation when call is awaited."""
        if not _SCRIPT_DIR.exists():
            pytest.skip(
                "check_async_tests script dir not present (ref: cleanup-skipped-legacy-tests)"
            )
        import check_async_tests as m  # noqa: PLC0415

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            _ = f.write("async def detect_failure(): pass\n")
            _ = f.write("async def test_foo():\n")
            _ = f.write("    await detect_failure()\n")
            path = Path(f.name)
        try:
            violations = m.check_file(path, {"detect_failure"})
            assert violations == []
        finally:
            path.unlink(missing_ok=True)

    def test_check_file_no_violation_for_unknown_name(self) -> None:
        """check_file ignores calls to names not in async set."""
        if not _SCRIPT_DIR.exists():
            pytest.skip(
                "check_async_tests script dir not present (ref: cleanup-skipped-legacy-tests)"
            )
        import check_async_tests as m  # noqa: PLC0415

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            _ = f.write("def test_foo():\n")
            _ = f.write("    sync_helper()  # not in async set\n")
            path = Path(f.name)
        try:
            violations = m.check_file(path, {"other_async"})
            assert violations == []
        finally:
            path.unlink(missing_ok=True)

    def test_check_file_attribute_call_unawaited(self) -> None:
        """check_file reports handler.detect_failure() when not awaited."""
        if not _SCRIPT_DIR.exists():
            pytest.skip(
                "check_async_tests script dir not present (ref: cleanup-skipped-legacy-tests)"
            )
        import check_async_tests as m  # noqa: PLC0415

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            _ = f.write("def test_foo():\n")
            _ = f.write("    handler.detect_failure()  # unawaited\n")
            path = Path(f.name)
        try:
            violations = m.check_file(path, {"detect_failure"})
            assert len(violations) == 1
            assert violations[0][2] == "detect_failure"
        finally:
            path.unlink(missing_ok=True)
