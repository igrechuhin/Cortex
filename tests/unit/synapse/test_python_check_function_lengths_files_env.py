"""Unit tests for the FILES env var interface of python/check_function_lengths.py."""

import os
import subprocess
import sys
from pathlib import Path

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.managers.initialization import get_project_root

_PROJECT_ROOT = get_project_root(None)
_SCRIPT = (
    get_cortex_path(_PROJECT_ROOT, CortexResourceType.SYNAPSE)
    / "scripts"
    / "python"
    / "check_function_lengths.py"
)


def _run_script(
    tmp_path: Path, *, extra_env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(_SCRIPT)],
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True,
    )


def _write_py_file_with_function(
    path: Path, *, func_name: str, logical_lines: int
) -> None:
    """Write a function whose logical line count is exactly logical_lines."""
    body_lines = [f"    x{i} = {i}" for i in range(logical_lines)]
    content = f"def {func_name}():\n" + "\n".join(body_lines) + "\n"
    _ = path.write_text(content, encoding="utf-8")


def test_files_env_dispatcher_checks_only_specified_file(
    tmp_path: Path,
) -> None:
    """When FILES is set, script ignores directory scanning."""
    # Arrange
    big = tmp_path / "Big.py"
    _write_py_file_with_function(big, func_name="foo", logical_lines=3)

    other = tmp_path / "Small.py"
    _write_py_file_with_function(other, func_name="bar", logical_lines=1)

    missing_src_dir = tmp_path / "MissingSrc"

    # Act
    result = _run_script(
        tmp_path,
        extra_env={
            "FILES": str(big),
            "SRC_DIR": str(missing_src_dir),
            "MAX_FUNCTION_LINES": "2",
        },
    )

    # Assert
    assert result.returncode == 1
    assert "Big.py" in result.stderr
    assert "Small.py" not in result.stderr
    assert "Error: Source directory" not in result.stderr


def test_files_env_empty_string_uses_fallback(tmp_path: Path) -> None:
    """FILES='' is treated as unset; fallback scan is used."""
    # Arrange
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    big = src_dir / "Big.py"
    _write_py_file_with_function(big, func_name="foo", logical_lines=3)

    # Act
    result = _run_script(
        tmp_path,
        extra_env={
            "SRC_DIR": str(src_dir),
            "FILES": "",
            "MAX_FUNCTION_LINES": "2",
        },
    )

    # Assert
    assert result.returncode == 1
    assert "Big.py" in result.stderr


def test_files_env_dispatcher_ignores_test_filter(tmp_path: Path) -> None:
    """Dispatcher mode should not apply test_*.py exclusion."""
    # Arrange
    src_dir = tmp_path / "src"
    src_dir.mkdir()

    test_bad = src_dir / "test_skip.py"
    _write_py_file_with_function(test_bad, func_name="foo", logical_lines=3)

    ok_py = src_dir / "ok.py"
    _write_py_file_with_function(ok_py, func_name="bar", logical_lines=1)

    missing_src_dir = tmp_path / "MissingSrc"

    # Fallback: should skip test_*.py, so no violations.
    result_fallback = _run_script(
        tmp_path,
        extra_env={"SRC_DIR": str(src_dir), "MAX_FUNCTION_LINES": "2"},
    )
    assert result_fallback.returncode == 0
    assert "test_skip.py" not in result_fallback.stderr

    # Dispatcher: should check the explicit file anyway.
    result_dispatcher = _run_script(
        tmp_path,
        extra_env={
            "FILES": str(test_bad),
            "SRC_DIR": str(missing_src_dir),
            "MAX_FUNCTION_LINES": "2",
        },
    )
    assert result_dispatcher.returncode == 1
    assert "test_skip.py" in result_dispatcher.stderr
