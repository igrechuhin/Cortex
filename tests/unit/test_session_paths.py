"""Tests for shared pre-commit session path helpers."""

from pathlib import Path

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.execution.session_paths import session_dir


def test_session_dir_creates_and_returns_session_path(tmp_path: Path) -> None:
    expected = get_cortex_path(tmp_path, CortexResourceType.SESSION)
    assert not expected.exists()
    got = session_dir(tmp_path)
    assert got == expected
    assert got.is_dir()
