"""Verify test-input signature for commit final-gate evidence."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from cortex.tools.execution import pre_commit_test_reuse_inputs as inputs


def _swift_1(_root: Path) -> tuple[bytes, ...]:
    return (b"swift toolchain 1",)


def _swift_2(_root: Path) -> tuple[bytes, ...]:
    return (b"swift toolchain 2",)


def _git(root: Path, *args: str) -> None:
    _ = subprocess.run(["git", *args], cwd=root, stdout=subprocess.DEVNULL, check=True)


def _create_repo(root: Path) -> None:
    _git(root, "init", "-q")
    _git(root, "config", "user.name", "Cortex test")
    _git(root, "config", "user.email", "cortex-test@example.invalid")
    _ = (root / "Package.swift").write_text("// manifest")
    _ = (root / "Package.resolved").write_text("old package lock")
    _ = (root / "Tests.swift").write_text("// staged test inputs")
    _git(root, "add", "Package.swift", "Package.resolved", "Tests.swift")
    _git(root, "commit", "-qm", "fixture")


@pytest.mark.parametrize(
    "change", ["package-lock", "mixed-index", "runner", "git-error"]
)
def test_reuse_requires_identical_proven_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    """Reject changed lock files, mixed index, toolchain drift or unreadable Git."""
    _create_repo(tmp_path)
    monkeypatch.setattr(inputs, "_runtime_identity", _swift_1)
    original = inputs.swift_test_input_fingerprint(tmp_path)
    assert original is not None
    if change == "package-lock":
        _ = (tmp_path / "Package.resolved").write_text("new package lock")
        _git(tmp_path, "add", "Package.resolved")
    elif change == "mixed-index":
        _ = (tmp_path / "Tests.swift").write_text("// new staged tests")
        _git(tmp_path, "add", "Tests.swift")
        _ = (tmp_path / "Tests.swift").write_text("// untested unstaged bytes")
    elif change == "runner":
        monkeypatch.setattr(inputs, "_runtime_identity", _swift_2)
    else:
        monkeypatch.setenv("GIT_DIR", str(tmp_path / "unavailable"))
    observed = inputs.swift_test_input_fingerprint(tmp_path)
    assert observed != original
    if change in {"mixed-index", "git-error"}:
        assert observed is None


def test_unstaged_source_and_declared_metadata_transition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Normal unstaged source can remain identical while opted-in output evolves."""
    _create_repo(tmp_path)
    monkeypatch.setattr(inputs, "_runtime_identity", _swift_1)
    output = ".cortex/memory-bank/progress.md"
    ignored = ".venv/"
    _ = (tmp_path / ".gitignore").write_text(f"{ignored}\n")
    (tmp_path / ignored).mkdir()
    _ = (tmp_path / ignored / "log").write_text("operational")
    (tmp_path / output).parent.mkdir(parents=True)
    _ = (tmp_path / output).write_text("Phase A")
    _git(tmp_path, "add", output, ".gitignore")
    _git(tmp_path, "commit", "-qm", "Allowlisted fixture paths")
    _ = (tmp_path / "Tests.swift").write_text("// wholly unstaged test source")
    original = inputs.swift_test_input_fingerprint(tmp_path, (output, ignored))
    assert original is not None
    _ = (tmp_path / output).write_text("Phase B")
    _git(tmp_path, "add", output)
    assert inputs.swift_test_input_fingerprint(tmp_path, (output, ignored)) == original
    assert inputs.swift_test_input_fingerprint(tmp_path) is None


def test_declared_operational_paths_are_stable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ignore only declared output and accept a dependency-free build directory."""
    _create_repo(tmp_path)
    monkeypatch.setattr(inputs, "_runtime_identity", _swift_1)
    _ = (tmp_path / ".gitignore").write_text(".build/\n")
    _git(tmp_path, "rm", "Package.resolved")
    _git(tmp_path, "add", ".gitignore")
    _git(tmp_path, "commit", "-qm", "Make fixture dependency free")
    db = ".cortex/experience/experience.db"
    artifacts = ".cortex/experience/artifacts/"
    original = inputs.swift_test_input_fingerprint(tmp_path, (db, artifacts))
    assert original is not None
    (tmp_path / ".build/checkouts").mkdir(parents=True)
    (tmp_path / artifacts).mkdir(parents=True)
    _ = (tmp_path / artifacts / "gate.json").write_text("receipt")
    _ = (tmp_path / f"{db}-wal").write_text("SQLite changes")
    assert inputs.swift_test_input_fingerprint(tmp_path, (db, artifacts)) == original
    assert inputs.swift_test_input_fingerprint(tmp_path) != original
