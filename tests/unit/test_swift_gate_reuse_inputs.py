"""Verify test-input signature for commit final-gate evidence."""

from __future__ import annotations

import hashlib
import os
import subprocess
from io import BufferedReader
from pathlib import Path
from unittest.mock import patch

import pytest

from cortex.tools.execution import pre_commit_swift_symlink_inputs as links
from cortex.tools.execution import pre_commit_test_reuse_inputs as inputs
from cortex.tools.execution.pre_commit_swift_symlink_inputs import (
    _creation_stamp,  # pyright: ignore[reportPrivateUsage]
    _read_target_digest,  # pyright: ignore[reportPrivateUsage]
)
from cortex.tools.execution.session_paths import session_dir


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
    _ = (root / "Sources.swift").write_text("// source input")
    _ = (root / "Tests.swift").write_text("// staged test inputs")
    _git(
        root, "add", "Package.swift", "Package.resolved", "Sources.swift", "Tests.swift"
    )
    _git(root, "commit", "-qm", "fixture")


@pytest.mark.parametrize(
    "change",
    [
        "Sources.swift",
        "Tests.swift",
        "package-lock",
        "mixed-index",
        "runner",
        "git-error",
    ],
)
def test_reuse_requires_identical_proven_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    """Reject changed source, tests, dependencies, index, or runner state."""
    _create_repo(tmp_path)
    monkeypatch.setattr(inputs, "_runtime_identity", _swift_1)
    original = inputs.swift_test_input_fingerprint(tmp_path)
    assert original is not None
    if change in {"Sources.swift", "Tests.swift"}:
        _ = (tmp_path / change).write_text("// changed Swift input")
    elif change == "package-lock":
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


@pytest.fixture
def swiftpm_link(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Path, Path]:
    """Use a committed link to a small file outside the checkout."""
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setattr(inputs, "_runtime_identity", _swift_1)
    root = tmp_path / "repo"
    root.mkdir()
    _create_repo(root)
    target = tmp_path / "archive.dat"
    _ = target.write_bytes(b"same")
    try:
        _ = _creation_stamp(target.stat())
    except ValueError:
        # AI: Supply a stable creation stamp for the synthetic Linux checkout.
        monkeypatch.setattr(links, "_creation_stamp", _fixture_creation_stamp)
    link = root / "Data"
    link.symlink_to(target)
    _git(root, "add", "--", link.name)
    _git(root, "commit", "-qm", "Add fixture link")
    return root, link, target


def _fixture_creation_stamp(_info: os.stat_result) -> str:
    return "fixture-creation-time"


def _linked_fingerprint(root: Path) -> str | None:
    return inputs.swift_test_input_fingerprint(root, trust_symlink_metadata=True)


def test_swift_symlink_warm_cache_avoids_body_reads(
    swiftpm_link: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Neither the default lane nor CI admits linked targets."""
    root, _, _ = swiftpm_link
    assert inputs.swift_test_input_fingerprint(root) is None
    with patch.object(links, "_read_target_digest", wraps=_read_target_digest) as read:
        original = _linked_fingerprint(root)
        assert original is not None
        cache_path = session_dir(root) / links.SWIFT_SYMLINK_CACHE_FILENAME
        assert cache_path.is_file()
        assert _linked_fingerprint(root) == original
        monkeypatch.setenv("CI", "true")
        assert _linked_fingerprint(root) is None
        read.assert_called_once()


@pytest.mark.parametrize("change_content", [False, True])
def test_swift_symlink_metadata_change_rehashes_and_refreshes_cache(
    swiftpm_link: tuple[Path, Path, Path], change_content: bool
) -> None:
    """New timestamps alone preserve evidence when SHA-256 still matches."""
    root, _, target = swiftpm_link
    with patch.object(links, "_read_target_digest", wraps=_read_target_digest) as read:
        original = _linked_fingerprint(root)
        assert original is not None
        before = target.stat()
        if change_content:
            _ = target.write_bytes(b"diff")
        os.utime(target, ns=(before.st_atime_ns, before.st_mtime_ns + 1_000_000_000))
        observed = _linked_fingerprint(root)
        assert observed is not None
        assert (observed == original) is not change_content
        assert _linked_fingerprint(root) == observed
        assert read.call_count == 2


@pytest.mark.parametrize("same_resolved_path", [False, True])
def test_swift_symlink_redirection_rehashes_even_for_identical_bytes(
    swiftpm_link: tuple[Path, Path, Path], same_resolved_path: bool
) -> None:
    """Changing the link text invalidates the old target identity."""
    root, link, target = swiftpm_link
    alternate = target.with_name("alternate.dat")
    if same_resolved_path:
        alternate.symlink_to(target)
    else:
        _ = alternate.write_bytes(b"same")
    with patch.object(links, "_read_target_digest", wraps=_read_target_digest) as read:
        original = _linked_fingerprint(root)
        assert original is not None
        link.unlink()
        link.symlink_to(alternate)
        observed = _linked_fingerprint(root)
        assert observed is not None and observed != original
        assert read.call_count == 2


@pytest.mark.parametrize("target_kind", ["dangling", "directory", "fifo"])
def test_swift_symlink_unsupported_target_rejects_before_reading_files(
    swiftpm_link: tuple[Path, Path, Path], target_kind: str
) -> None:
    """A second unsupported link blocks reuse before any archive body is read."""
    root, _, target = swiftpm_link
    unsupported = target.with_name("unsupported")
    if target_kind == "directory":
        unsupported.mkdir()
    elif target_kind == "fifo":
        os.mkfifo(unsupported)
    (root / "ZLink").symlink_to(unsupported)
    with patch.object(links, "_read_target_digest", wraps=_read_target_digest) as read:
        assert _linked_fingerprint(root) is None
    read.assert_not_called()


@pytest.mark.parametrize("missing", ["creation", "modification"])
def test_swift_symlink_missing_stat_timestamp_rejects_evidence(
    swiftpm_link: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch, missing: str
) -> None:
    root, _, target = swiftpm_link
    lstat = Path.lstat

    def incomplete_stat(path: Path) -> os.stat_result:
        result = lstat(path)
        if path != target:
            return result
        extra = {"st_mtime_ns": result.st_mtime_ns} if missing == "creation" else {}
        return os.stat_result(tuple(result), extra)

    monkeypatch.setattr(links, "_creation_stamp", _creation_stamp)
    monkeypatch.setattr(Path, "lstat", incomplete_stat)
    assert _linked_fingerprint(root) is None


def test_swift_symlink_warm_cache_rejects_unreadable_target(
    swiftpm_link: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _, _ = swiftpm_link
    assert _linked_fingerprint(root) is not None

    def inaccessible(_path: str, _flags: int) -> int:
        raise PermissionError("unreadable fixture target")

    monkeypatch.setattr(links, "_open_target", inaccessible)
    assert _linked_fingerprint(root) is None


def test_swift_symlink_rejects_changes_while_body_is_being_hashed(
    swiftpm_link: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _, target = swiftpm_link
    file_digest = hashlib.file_digest

    def mutate_while_reading(source: BufferedReader, algorithm: str) -> object:
        digest = file_digest(source, algorithm)
        _ = target.write_bytes(b"updated target bytes")
        return digest

    with monkeypatch.context() as patcher:
        patcher.setattr(hashlib, "file_digest", mutate_while_reading)
        assert _linked_fingerprint(root) is None
    cache_path = session_dir(root) / links.SWIFT_SYMLINK_CACHE_FILENAME
    assert not cache_path.exists()
    assert _linked_fingerprint(root) is not None
