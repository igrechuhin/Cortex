"""Unit tests for the FILES env var interface of swift/check_file_sizes.py."""

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
    / "swift"
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


def test_files_env_checks_only_specified_file(tmp_path: Path) -> None:
    """When FILES is set, script ignores all other files and does not require Sources/."""
    # Arrange
    big = tmp_path / "Big.swift"
    _ = big.write_text("let x = 1\n" * 401, encoding="utf-8")
    other = tmp_path / "Small.swift"
    _ = other.write_text("// comment only\n", encoding="utf-8")

    # Act
    result = _run_script(tmp_path, extra_env={"FILES": str(big)})

    # Assert
    assert result.returncode == 1
    assert "Big.swift" in result.stderr
    assert "Small.swift" not in result.stderr
    assert "Sources directory not found" not in result.stderr


def test_files_env_absent_scans_sources_dir(tmp_path: Path) -> None:
    """When FILES is not set, script falls back to scanning Sources/."""
    # Arrange
    sources = tmp_path / "Sources"
    sources.mkdir()
    big = sources / "Big.swift"
    _ = big.write_text("let x = 1\n" * 401, encoding="utf-8")

    # Act
    result = _run_script(tmp_path, extra_env={"SOURCES_DIR": str(sources)})

    # Assert
    assert result.returncode == 1
    assert "Big.swift" in result.stderr


def test_files_env_includes_tests_dir_in_fallback(tmp_path: Path) -> None:
    """Fallback scan includes Tests/ — regression: TESTS/ must be checked."""
    # Arrange
    sources = tmp_path / "Sources"
    sources.mkdir()
    _ = (sources / "Ok.swift").write_text("// tiny\n", encoding="utf-8")

    tests_dir = tmp_path / "Tests"
    tests_dir.mkdir()
    big_test = tests_dir / "BigTest.swift"
    _ = big_test.write_text("let x = 1\n" * 401, encoding="utf-8")

    # Act
    result = _run_script(tmp_path, extra_env={"SOURCES_DIR": str(sources)})

    # Assert
    assert result.returncode == 1
    assert "BigTest.swift" in result.stderr


def test_files_env_empty_string_uses_fallback(tmp_path: Path) -> None:
    """FILES='' is treated as unset; fallback scan is used."""
    # Arrange
    sources = tmp_path / "Sources"
    sources.mkdir()
    big = sources / "Big.swift"
    _ = big.write_text("let x = 1\n" * 401, encoding="utf-8")

    # Act
    result = _run_script(tmp_path, extra_env={"SOURCES_DIR": str(sources), "FILES": ""})

    # Assert
    assert result.returncode == 1
    assert "Big.swift" in result.stderr
