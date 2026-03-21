"""Tests for scripts/check_dep_parity.py."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_dep_parity.py"


def _load_check_dep_parity_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "check_dep_parity",
        SCRIPT_PATH,
    )
    if spec is None or spec.loader is None:
        msg = f"Cannot load {SCRIPT_PATH}"
        raise RuntimeError(msg)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_mod = _load_check_dep_parity_module()


def _write_pyproject(tmp_path: Path, dependencies: list[str]) -> None:
    dep_lines = "".join(f'    "{dep}",\n' for dep in dependencies)
    content = (
        "[project]\n"
        'name = "parity-test"\n'
        'version = "0.0.0"\n'
        "dependencies = [\n"
        f"{dep_lines}"
        "]\n"
    )
    assert (tmp_path / "pyproject.toml").write_text(content, encoding="utf-8") >= 0


def _run_script(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--root", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_normalize_distribution_name() -> None:
    assert _mod.normalize_distribution_name("Foo_Bar") == "foo-bar"


def test_parse_requirements_txt_skips_comments_and_blank() -> None:
    text = """
# header
mcp>=1.0

foo>=2.0  # inline
"""
    assert _mod.parse_requirements_txt(text) == ["mcp>=1.0", "foo>=2.0"]


def test_identical_passes(tmp_path: Path) -> None:
    deps = ["foo>=1.0", "bar==2.0"]
    _write_pyproject(tmp_path, deps)
    assert (tmp_path / "requirements.txt").write_text(
        "bar==2.0\nfoo>=1.0\n",
        encoding="utf-8",
    ) >= 0
    assert _mod.check_parity(tmp_path) == []
    proc = _run_script(tmp_path)
    assert proc.returncode == 0
    assert proc.stderr == ""


def test_missing_package_in_requirements(tmp_path: Path) -> None:
    _write_pyproject(tmp_path, ["foo>=1.0", "bar==2.0"])
    assert (tmp_path / "requirements.txt").write_text(
        "foo>=1.0\n", encoding="utf-8"
    ) >= 0
    msgs = _mod.check_parity(tmp_path)
    assert len(msgs) == 1
    assert "Missing from requirements.txt" in msgs[0]
    assert "bar==2.0" in msgs[0]
    proc = _run_script(tmp_path)
    assert proc.returncode == 1
    assert "Missing from requirements.txt" in proc.stderr


def test_wrong_version_in_requirements(tmp_path: Path) -> None:
    _write_pyproject(tmp_path, ["foo>=1.0"])
    assert (tmp_path / "requirements.txt").write_text(
        "foo>=2.0\n", encoding="utf-8"
    ) >= 0
    msgs = _mod.check_parity(tmp_path)
    assert len(msgs) == 1
    assert "Requirement mismatch" in msgs[0]
    proc = _run_script(tmp_path)
    assert proc.returncode == 1
    assert "Requirement mismatch" in proc.stderr


def test_extra_package_in_requirements(tmp_path: Path) -> None:
    _write_pyproject(tmp_path, ["foo>=1.0"])
    assert (tmp_path / "requirements.txt").write_text(
        "foo>=1.0\nbaz>=3.0\n",
        encoding="utf-8",
    ) >= 0
    msgs = _mod.check_parity(tmp_path)
    assert len(msgs) == 1
    assert "Extra in requirements.txt" in msgs[0]
    assert "baz>=3.0" in msgs[0]
    proc = _run_script(tmp_path)
    assert proc.returncode == 1
    assert "Extra in requirements.txt" in proc.stderr


def test_name_normalization_matches_across_sources(tmp_path: Path) -> None:
    """Same normalized name and identical requirement strings must match."""
    _write_pyproject(tmp_path, ["foo_bar>=1.0"])
    assert (tmp_path / "requirements.txt").write_text(
        "foo_bar>=1.0\n", encoding="utf-8"
    ) >= 0
    assert _mod.check_parity(tmp_path) == []


def test_underscore_vs_hyphen_same_string_still_compared(tmp_path: Path) -> None:
    """Different spellings with same normalized name but different text fail."""
    _write_pyproject(tmp_path, ["foo-bar>=1.0"])
    assert (tmp_path / "requirements.txt").write_text(
        "foo_bar>=1.0\n", encoding="utf-8"
    ) >= 0
    msgs = _mod.check_parity(tmp_path)
    assert len(msgs) == 1
    assert "Requirement mismatch" in msgs[0]
