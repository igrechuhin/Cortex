"""Tests for pre_commit_rumdl_resolve — uv_executable, coerce_rumdl_argv0, markdown_rumdl_argv."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from cortex.tools.execution.pre_commit_rumdl_resolve import (
    coerce_rumdl_argv0,
    markdown_rumdl_argv,
    uv_executable,
)

# ── uv_executable ─────────────────────────────────────────────────────────────


def test_uv_executable_returns_shutil_which_result(tmp_path: Path) -> None:
    """When uv is on PATH, return what shutil.which finds."""
    fake_uv = tmp_path / "uv"
    _ = fake_uv.write_text("#!/bin/sh\n", encoding="utf-8")
    fake_uv.chmod(0o755)
    with patch.dict(os.environ, {"PATH": str(tmp_path)}, clear=False):
        result = uv_executable()
    assert result == str(fake_uv)


def test_uv_executable_falls_back_to_common_path(tmp_path: Path) -> None:
    """When PATH has no uv, scan _UV_COMMON_PATHS and return the first that exists."""
    fake_uv = tmp_path / "uv"
    _ = fake_uv.write_text("#!/bin/sh\n", encoding="utf-8")
    fake_uv.chmod(0o755)
    with patch("shutil.which", return_value=None):
        with patch(
            "cortex.tools.execution.pre_commit_rumdl_resolve._UV_COMMON_PATHS",
            (fake_uv,),
        ):
            result = uv_executable()
    assert result == str(fake_uv.resolve())


def test_uv_executable_returns_none_when_not_found(tmp_path: Path) -> None:
    """Return None when uv cannot be located anywhere."""
    with patch("shutil.which", return_value=None):
        with patch(
            "cortex.tools.execution.pre_commit_rumdl_resolve._UV_COMMON_PATHS",
            (),
        ):
            result = uv_executable()
    assert result is None


# ── coerce_rumdl_argv0 ────────────────────────────────────────────────────────


def test_coerce_rumdl_argv0_no_op_when_not_bare(tmp_path: Path) -> None:
    """If argv0 is already an absolute path, leave cmd unchanged."""
    cmd = ["/some/path/rumdl", "check", "file.md"]
    assert coerce_rumdl_argv0(tmp_path, cmd) == cmd


def test_coerce_rumdl_argv0_no_op_for_empty_cmd(tmp_path: Path) -> None:
    """Empty cmd is returned unchanged."""
    assert coerce_rumdl_argv0(tmp_path, []) == []


def test_coerce_rumdl_argv0_resolves_via_shutil_which(tmp_path: Path) -> None:
    """When shutil.which finds rumdl in the augmented PATH, replace argv0."""
    venv_bin = tmp_path / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    rumdl = venv_bin / "rumdl"
    _ = rumdl.write_text("#!/bin/sh\n", encoding="utf-8")
    rumdl.chmod(0o755)
    cmd = ["rumdl", "check"]
    result = coerce_rumdl_argv0(tmp_path, cmd)
    assert result[0] == str(rumdl.resolve())
    assert result[1:] == ["check"]


def test_coerce_rumdl_argv0_sandbox_fallback_when_no_which(tmp_path: Path) -> None:
    """When shutil.which fails and no is_file() match, use forced venv path."""
    root = tmp_path / "proj"
    root.mkdir()
    cmd = ["rumdl", "check"]
    with patch("shutil.which", return_value=None):
        with patch(
            "cortex.tools.execution.pre_commit_rumdl_resolve._rumdl_from_project_venv",
            return_value=None,
        ):
            result = coerce_rumdl_argv0(root, cmd)
    expected_argv0 = str((root / ".venv" / "bin" / "rumdl").resolve())
    assert result[0] == expected_argv0
    assert result[1:] == ["check"]


# ── markdown_rumdl_argv ───────────────────────────────────────────────────────


def test_markdown_rumdl_argv_prefers_uv_run(tmp_path: Path) -> None:
    """When uv is found, argv should start with [uv, 'run', 'rumdl', 'check']."""
    fake_uv = tmp_path / "uv"
    _ = fake_uv.write_text("#!/bin/sh\n", encoding="utf-8")
    fake_uv.chmod(0o755)
    with patch(
        "cortex.tools.execution.pre_commit_rumdl_resolve.uv_executable",
        return_value=str(fake_uv),
    ):
        result = markdown_rumdl_argv(tmp_path, with_fix=False)
    assert result[:4] == [str(fake_uv), "run", "rumdl", "check"]
    assert "--fix" not in result


def test_markdown_rumdl_argv_with_fix_flag(tmp_path: Path) -> None:
    """--fix appears in argv when with_fix=True."""
    fake_uv = tmp_path / "uv"
    _ = fake_uv.write_text("#!/bin/sh\n", encoding="utf-8")
    fake_uv.chmod(0o755)
    with patch(
        "cortex.tools.execution.pre_commit_rumdl_resolve.uv_executable",
        return_value=str(fake_uv),
    ):
        result = markdown_rumdl_argv(tmp_path, with_fix=True)
    assert "--fix" in result


def test_markdown_rumdl_argv_includes_config_when_present(tmp_path: Path) -> None:
    """When .rumdl.toml exists, argv includes --config <path>."""
    config = tmp_path / ".rumdl.toml"
    _ = config.write_text("[default]\n", encoding="utf-8")
    with patch(
        "cortex.tools.execution.pre_commit_rumdl_resolve.uv_executable",
        return_value=None,
    ):
        rumdl = tmp_path / ".venv" / "bin" / "rumdl"
        rumdl.parent.mkdir(parents=True)
        _ = rumdl.write_text("#!/bin/sh\n", encoding="utf-8")
        result = markdown_rumdl_argv(tmp_path, with_fix=False)
    assert "--config" in result
    assert str(config) in result


def test_markdown_rumdl_argv_falls_back_to_forced_path_when_no_uv(
    tmp_path: Path,
) -> None:
    """Without uv and without a resolvable binary, use .venv/bin/rumdl directly."""
    root = tmp_path / "proj"
    root.mkdir()
    with patch(
        "cortex.tools.execution.pre_commit_rumdl_resolve.uv_executable",
        return_value=None,
    ):
        with patch(
            "cortex.tools.execution.pre_commit_rumdl_resolve.resolve_rumdl_path",
            return_value="rumdl",
        ):
            result = markdown_rumdl_argv(root, with_fix=False)
    expected_argv0 = str((root / ".venv/bin/rumdl").resolve())
    assert result[0] == expected_argv0
    assert result[1] == "check"


def test_markdown_rumdl_argv_no_doubled_uv_prefix(tmp_path: Path) -> None:
    """argv must never be [uv, run, rumdl, run, rumdl, ...] — no doubled prefix."""
    fake_uv = tmp_path / "uv"
    _ = fake_uv.write_text("#!/bin/sh\n", encoding="utf-8")
    fake_uv.chmod(0o755)
    with patch(
        "cortex.tools.execution.pre_commit_rumdl_resolve.uv_executable",
        return_value=str(fake_uv),
    ):
        result = markdown_rumdl_argv(tmp_path, with_fix=False)
    # "rumdl" must appear exactly once as a positional token (after "run")
    rumdl_indices = [i for i, t in enumerate(result) if t == "rumdl"]
    assert (
        len(rumdl_indices) == 1
    ), f"rumdl appears {len(rumdl_indices)} times: {result}"


@pytest.mark.parametrize("with_fix", [True, False])
def test_markdown_rumdl_argv_check_subcommand_always_present(
    tmp_path: Path, with_fix: bool
) -> None:
    """'check' subcommand must always be in argv regardless of uv availability."""
    with patch(
        "cortex.tools.execution.pre_commit_rumdl_resolve.uv_executable",
        return_value=None,
    ):
        rumdl = tmp_path / ".venv" / "bin" / "rumdl"
        rumdl.parent.mkdir(parents=True)
        _ = rumdl.write_text("#!/bin/sh\n", encoding="utf-8")
        result = markdown_rumdl_argv(tmp_path, with_fix=with_fix)
    assert "check" in result
