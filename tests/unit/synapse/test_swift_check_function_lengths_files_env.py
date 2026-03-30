"""Unit tests for the FILES env var interface of swift/check_function_lengths.py."""

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


def _write_swift_file_with_function(path: Path, *, let_lines: int) -> None:
    """Write a single Swift function whose logical line count is 1 + let_lines."""
    body_lines = [f"let x{i} = 0" for i in range(let_lines)]
    content_lines = ["func foo()", "{", *body_lines, "}"]
    content = "\n".join(content_lines) + "\n"
    _ = path.write_text(content, encoding="utf-8")


def test_files_env_checks_only_specified_file(tmp_path: Path) -> None:
    """When FILES is set, script ignores all other files and does not require Sources/."""
    # Arrange
    big = tmp_path / "Big.swift"
    _write_swift_file_with_function(big, let_lines=4)

    other = tmp_path / "Small.swift"
    _write_swift_file_with_function(other, let_lines=2)

    missing_sources = tmp_path / "MissingSources"

    # Act
    result = _run_script(
        tmp_path,
        extra_env={
            "FILES": str(big),
            "SOURCES_DIR": str(missing_sources),
            "MAX_FUNCTION_LINES": "4",
        },
    )

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
    _write_swift_file_with_function(big, let_lines=4)

    # Act
    result = _run_script(
        tmp_path, extra_env={"SOURCES_DIR": str(sources), "MAX_FUNCTION_LINES": "4"}
    )

    # Assert
    assert result.returncode == 1
    assert "Big.swift" in result.stderr


def test_files_env_includes_tests_dir_in_fallback(tmp_path: Path) -> None:
    """Fallback scan includes Tests/ — regression: Tests/ must be checked."""
    # Arrange
    sources = tmp_path / "Sources"
    sources.mkdir()
    _write_swift_file_with_function(sources / "Ok.swift", let_lines=2)

    tests_dir = tmp_path / "Tests"
    tests_dir.mkdir()
    big_test = tests_dir / "BigTest.swift"
    _write_swift_file_with_function(big_test, let_lines=4)

    # Act
    result = _run_script(
        tmp_path, extra_env={"SOURCES_DIR": str(sources), "MAX_FUNCTION_LINES": "4"}
    )

    # Assert
    assert result.returncode == 1
    assert "BigTest.swift" in result.stderr


def test_files_env_empty_string_uses_fallback(tmp_path: Path) -> None:
    """FILES='' is treated as unset; fallback scan is used."""
    # Arrange
    sources = tmp_path / "Sources"
    sources.mkdir()
    big = sources / "Big.swift"
    _write_swift_file_with_function(big, let_lines=4)

    # Act
    result = _run_script(
        tmp_path,
        extra_env={
            "SOURCES_DIR": str(sources),
            "FILES": "",
            "MAX_FUNCTION_LINES": "4",
        },
    )

    # Assert
    assert result.returncode == 1
    assert "Big.swift" in result.stderr


def test_files_env_generated_suffix_is_excluded(tmp_path: Path) -> None:
    """Dispatcher mode excludes generated suffixes (e.g. .pb.swift)."""
    # Arrange
    generated = tmp_path / "Generated.pb.swift"
    _write_swift_file_with_function(generated, let_lines=10)

    missing_sources = tmp_path / "MissingSources"

    # Act
    result = _run_script(
        tmp_path,
        extra_env={
            "FILES": str(generated),
            "SOURCES_DIR": str(missing_sources),
            "MAX_FUNCTION_LINES": "4",
        },
    )

    # Assert
    assert result.returncode == 0
