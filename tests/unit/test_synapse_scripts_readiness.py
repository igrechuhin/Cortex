"""Regression tests for shared Synapse scripts-directory readiness (bootstrap / check_synapse)."""

from __future__ import annotations

import os
import pathlib
import subprocess


def _repo_root() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parents[2]


def _run_readiness_check(repo_root: pathlib.Path) -> int:
    lib = _repo_root() / "scripts" / "_synapse_lib.sh"
    script = f'source "{lib}"; if _synapse_scripts_ready; then exit 0; else exit 1; fi'
    env = {**os.environ, "REPO_ROOT": str(repo_root)}
    completed = subprocess.run(
        ["bash", "-c", script],
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.returncode


def test_synapse_scripts_ready_false_when_scripts_dir_missing(
    tmp_path: pathlib.Path,
) -> None:
    fake_repo = tmp_path / "repo"
    fake_repo.mkdir()
    assert _run_readiness_check(fake_repo) == 1


def test_synapse_scripts_ready_false_when_scripts_dir_empty(
    tmp_path: pathlib.Path,
) -> None:
    fake_repo = tmp_path / "repo"
    scripts = fake_repo / ".cortex" / "synapse" / "scripts"
    scripts.mkdir(parents=True)
    assert _run_readiness_check(fake_repo) == 1


def test_synapse_scripts_ready_true_when_scripts_dir_has_file(
    tmp_path: pathlib.Path,
) -> None:
    fake_repo = tmp_path / "repo"
    scripts = fake_repo / ".cortex" / "synapse" / "scripts"
    scripts.mkdir(parents=True)
    written = (scripts / ".gitkeep").write_text("", encoding="utf-8")
    assert written == 0
    assert _run_readiness_check(fake_repo) == 0


def test_bootstrap_uses_shared_synapse_readiness() -> None:
    bootstrap = (_repo_root() / "scripts" / "bootstrap.sh").read_text(encoding="utf-8")
    assert "_synapse_lib.sh" in bootstrap
    assert "_synapse_scripts_ready" in bootstrap
    assert "SYNAPSE_SCRIPTS_DIR" not in bootstrap
