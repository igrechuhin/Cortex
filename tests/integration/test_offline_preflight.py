"""Smoke tests for offline preflight (restricted-network contract)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests.integration.conftest import repo_root


@pytest.mark.integration
def test_preflight_offline_isolated_repo_root_exits_zero(tmp_path: Path) -> None:
    """Offline checks run against ``CORTEX_REPO_ROOT`` without requiring a warm uv cache."""
    repo = repo_root()
    _ = shutil.copy2(repo / "pyproject.toml", tmp_path / "pyproject.toml")
    _ = shutil.copy2(repo / "uv.lock", tmp_path / "uv.lock")
    _ = (tmp_path / "vendor").mkdir()
    # Filename matches offline probe; content is irrelevant for the existence check.
    _ = (tmp_path / "vendor" / "uv_build-0.0.1-py3-none-any.whl").write_bytes(b"")

    py = repo / ".venv" / "bin" / "python"
    if not py.is_file():
        py = Path(sys.executable)

    env = os.environ.copy()
    env["CORTEX_REPO_ROOT"] = str(tmp_path)

    mod = subprocess.run(
        [str(py), "-m", "cortex.cli.preflight", "--offline"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert mod.returncode == 0, f"module entry:\n{mod.stdout}\n{mod.stderr}"

    script = subprocess.run(
        ["bash", str(repo / "scripts" / "preflight.sh"), "--offline"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert script.returncode == 0, f"shell wrapper:\n{script.stdout}\n{script.stderr}"
    assert "Offline readiness" in script.stdout
