"""Tests for resolve_rumdl_path (detached worker markdown rumdl discovery)."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

from cortex.tools.execution.pre_commit_rumdl_resolve import resolve_rumdl_path


def test_resolve_rumdl_path_prefers_interpreter_adjacent_binary(tmp_path: Path) -> None:
    """When rumdl sits next to sys.executable, use that path."""
    fake_bin = tmp_path / "bin"
    _ = fake_bin.mkdir(parents=True)
    rumdl = fake_bin / "rumdl"
    _ = rumdl.write_text("#!/bin/sh\n", encoding="utf-8")
    fake_py = fake_bin / "python3"
    _ = fake_py.write_text("", encoding="utf-8")
    with patch.object(sys, "executable", str(fake_py)):
        assert resolve_rumdl_path(tmp_path) == str(rumdl)


def test_resolve_rumdl_path_falls_back_to_project_dot_venv(tmp_path: Path) -> None:
    """When interpreter has no adjacent rumdl, use project .venv/bin/rumdl."""
    fake_bin = tmp_path / "fakeenv" / "bin"
    _ = fake_bin.mkdir(parents=True)
    fake_py = fake_bin / "python3"
    _ = fake_py.write_text("", encoding="utf-8")

    venv_rumdl = tmp_path / "proj" / ".venv" / "bin" / "rumdl"
    _ = venv_rumdl.parent.mkdir(parents=True)
    _ = venv_rumdl.write_text("#!/bin/sh\n", encoding="utf-8")

    with patch.object(sys, "executable", str(fake_py)):
        with patch.dict(os.environ, {"VIRTUAL_ENV": ""}, clear=False):
            resolved = resolve_rumdl_path(tmp_path / "proj")
        assert resolved == str(venv_rumdl.resolve())


def test_resolve_rumdl_path_conventional_dot_venv_when_no_stat_match(
    tmp_path: Path,
) -> None:
    """Prefer a conventional ``.venv/bin/rumdl`` path when probes miss (e.g. sandbox)."""
    fake_bin = tmp_path / "bin"
    _ = fake_bin.mkdir(parents=True)
    fake_py = fake_bin / "python3"
    _ = fake_py.write_text("", encoding="utf-8")
    noproj = tmp_path / "noproj"
    expected = str((noproj / ".venv" / "bin" / "rumdl").resolve())
    with patch.object(sys, "executable", str(fake_py)):
        with patch.dict(os.environ, {"VIRTUAL_ENV": ""}, clear=False):
            assert resolve_rumdl_path(noproj) == expected


def test_resolve_rumdl_path_shutil_which_fallback_when_candidates_skipped(
    tmp_path: Path,
) -> None:
    """If direct venv probes are skipped, still resolve rumdl under project venv bins."""
    venv_bin = tmp_path / ".venv" / "bin"
    _ = venv_bin.mkdir(parents=True)
    rumdl = venv_bin / "rumdl"
    _ = rumdl.write_text("#!/bin/sh\necho ok\n", encoding="utf-8")
    rumdl.chmod(0o755)
    fake_bin = tmp_path / "fake" / "bin"
    _ = fake_bin.mkdir(parents=True)
    fake_py = fake_bin / "python3"
    _ = fake_py.write_text("", encoding="utf-8")
    with patch.object(sys, "executable", str(fake_py)):
        with patch.dict(os.environ, {"VIRTUAL_ENV": ""}, clear=False):
            with patch(
                "cortex.tools.execution.pre_commit_rumdl_resolve.iter_venv_executable_candidates",
                return_value=iter(()),
            ):
                resolved = resolve_rumdl_path(tmp_path)
    assert resolved == str(rumdl.resolve())
