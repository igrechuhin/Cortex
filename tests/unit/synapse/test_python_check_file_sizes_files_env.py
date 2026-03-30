"""Unit tests for the FILES env var interface of python/check_file_sizes.py."""

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
    / "check_file_sizes.py"
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


def _write_python_file(path: Path, *, logical_lines: int) -> None:
    """Write a file with a predictable number of logical lines."""
    lines = [f"print({i})" for i in range(logical_lines)]
    _ = path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_files_env_dispatcher_checks_only_specified_file(
    tmp_path: Path,
) -> None:
    """When FILES is set, script ignores directory scanning."""
    # Arrange
    big = tmp_path / "Big.py"
    _write_python_file(big, logical_lines=20)
    other = tmp_path / "Small.py"
    _write_python_file(other, logical_lines=1)

    missing_src_dir = tmp_path / "MissingSrc"

    # Act
    result = _run_script(
        tmp_path,
        extra_env={
            "FILES": str(big),
            "SRC_DIR": str(missing_src_dir),
            "MAX_FILE_LINES": "10",
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
    _write_python_file(big, logical_lines=20)

    # Act
    result = _run_script(
        tmp_path,
        extra_env={
            "SRC_DIR": str(src_dir),
            "FILES": "",
            "MAX_FILE_LINES": "10",
        },
    )

    # Assert
    assert result.returncode == 1
    assert "Big.py" in result.stderr


def test_files_env_dispatcher_ignores_test_and_excluded_filters(
    tmp_path: Path,
) -> None:
    """Dispatcher mode should not apply test_/models.py exclusions."""
    # Arrange
    src_dir = tmp_path / "src"
    src_dir.mkdir()

    models_py = src_dir / "models.py"
    _write_python_file(models_py, logical_lines=20)

    test_bad = src_dir / "test_bad.py"
    _write_python_file(test_bad, logical_lines=20)

    ok_py = src_dir / "ok.py"
    _write_python_file(ok_py, logical_lines=1)

    missing_src_dir = tmp_path / "MissingSrc"

    # Fallback: should skip models.py and test_*.py
    result_fallback = _run_script(
        tmp_path,
        extra_env={"SRC_DIR": str(src_dir), "MAX_FILE_LINES": "10"},
    )
    assert result_fallback.returncode == 0
    assert "models.py" not in result_fallback.stderr
    assert "test_bad.py" not in result_fallback.stderr

    # Dispatcher: should check exactly the passed files.
    result_dispatcher = _run_script(
        tmp_path,
        extra_env={
            "FILES": f"{models_py}\n{test_bad}",
            "SRC_DIR": str(missing_src_dir),
            "MAX_FILE_LINES": "10",
        },
    )
    assert result_dispatcher.returncode == 1
    assert "models.py" in result_dispatcher.stderr
    assert "test_bad.py" in result_dispatcher.stderr
