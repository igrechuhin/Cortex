"""Fingerprint the opt-in SwiftPM input boundary for final test reuse."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import sys
from pathlib import Path
from typing import Protocol

# AI: Only passive Cortex output agreed by the project can be excluded. Never
# infer that a Markdown file, or even a Cortex-owned file, is not a test input.
_OPERATIONS_LOG = ".cortex/memory-bank/log.md"
_SESSION_PREFIX = ".cortex/.session/"
_GENERATED_BUILD_NAMES = frozenset({".DS_Store", ".build/"})
_IGNORED_WORKER_ENV = frozenset(
    {"CORTEX_QUALITY_LEASE_FD", "CORTEX_QUALITY_LEASE_REQUEST"}
)
_MAX_FILE_BYTES = 64 * 1024 * 1024
_MAX_INPUT_BYTES = 512 * 1024 * 1024


def _command(root: Path, *argv: str) -> bytes:
    return subprocess.check_output(
        argv,
        cwd=root,
        stderr=subprocess.DEVNULL,
        timeout=30,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
    )


class _Digest(Protocol):
    """Minimal interface needed to update a hash."""

    def update(self, value: bytes, /) -> None: ...


def _hash_field(digest: _Digest, value: bytes) -> None:
    digest.update(len(value).to_bytes(8, "big"))
    digest.update(value)


def _hash_file(digest: _Digest, root: Path, relative: str) -> int:
    path = root / relative
    before = path.lstat()
    if (
        not path.is_relative_to(root)
        or path.resolve() != path
        or not stat.S_ISREG(before.st_mode)
        or before.st_size > _MAX_FILE_BYTES
    ):
        raise ValueError("Unsupported SwiftPM evidence input")
    _hash_field(digest, relative.encode())
    _hash_field(digest, str(before.st_mode & 0o777).encode())
    with path.open("rb") as source:
        _hash_field(digest, source.read(_MAX_FILE_BYTES + 1))
    if (after := path.lstat()) != before and (
        after.st_ino,
        after.st_mode,
        after.st_size,
        after.st_mtime_ns,
    ) != (before.st_ino, before.st_mode, before.st_size, before.st_mtime_ns):
        raise ValueError("SwiftPM input changed while hashing")
    return before.st_size


def _git_inputs(root: Path, outputs: tuple[str, ...]) -> tuple[bytes, list[str]]:
    # AI: Normal Phase A can test wholly unstaged paths, but a partially
    # staged path represents two different proposed versions of one input.
    excluded = _generated_paths(outputs)
    _reject_partial_staging(root, excluded)
    entries = _command(root, "git", "ls-files", "--stage", "-z").split(b"\0")
    stage: list[bytes] = []
    submodules: set[str] = set()
    # AI: Submodules, sparse/staged conflicts and symlinks need their own input
    # policy. Their index entries alone do not identify checked-out bytes.
    for entry in entries:
        if not entry:
            continue
        fields, raw_name = entry.split(b"\t", 1)
        mode, sha, stage_no = fields.split()
        name = raw_name.decode()
        if stage_no != b"0":
            raise ValueError("Unresolved Git index input")
        if mode == b"160000" and name == ".cortex/synapse":
            stage.append(_clean_checkout_fingerprint(root / name, sha))
            submodules.add(name)
        elif mode not in {b"100644", b"100755"}:
            raise ValueError("Unsupported Git index input")
        if not _generated(name, excluded):
            stage.append(entry)
    _validate_ignored(root, excluded)
    paths = _command(
        root, "git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"
    )
    # The scoped opt-in declaration covers the ephemeral log; all other docs
    # and project artifacts remain material, including the contents of the index.
    return b"\0".join(stage), sorted(
        name
        for name in set(paths.decode().split("\0")) - {""} - submodules
        if not _generated(name, excluded)
    )


def _generated_paths(outputs: tuple[str, ...]) -> set[str]:
    allowed = {*outputs, _OPERATIONS_LOG}
    db = ".cortex/experience/experience.db"
    if db in allowed:
        allowed.update((f"{db}-shm", f"{db}-wal"))
    return allowed


def _generated(relative: str, paths: set[str]) -> bool:
    return relative in paths or any(
        prefix.endswith("/") and relative.startswith(prefix) for prefix in paths
    )


def _reject_partial_staging(root: Path, excluded: set[str]) -> None:
    staged = (
        _command(root, "git", "diff", "--cached", "--name-only", "-z", "HEAD")
        .decode()
        .split("\0")
    )
    unstaged = _command(root, "git", "diff", "--name-only", "-z").decode().split("\0")
    if any(
        name and not _generated(name, excluded) for name in set(staged) & set(unstaged)
    ):
        raise ValueError("Partially staged SwiftPM input")


def _validate_ignored(root: Path, excluded: set[str]) -> None:
    ignored = (
        _command(
            root,
            "git",
            "ls-files",
            "--others",
            "--ignored",
            "--exclude-standard",
            "--directory",
            "-z",
        )
        .decode()
        .split("\0")
    )
    if any(
        path
        and path not in _GENERATED_BUILD_NAMES
        and not _generated(path, excluded)
        and not path.startswith(_SESSION_PREFIX)
        for path in ignored
    ):
        raise ValueError("Undeclared ignored test input")


def _clean_checkout_fingerprint(root: Path, index_sha: bytes) -> bytes:
    if (
        root.resolve() != root
        or _command(root, "git", "rev-parse", "--show-toplevel").decode().strip()
        != str(root)
        or _command(root, "git", "rev-parse", "HEAD").strip() != index_sha
    ):
        raise ValueError("Synapse checkout does not match the Git index")
    if _command(root, "git", "status", "--porcelain", "--untracked-files=all"):
        raise ValueError("Dirty dependency checkout")
    if _command(root, "git", "ls-files", "--others", "--ignored", "--exclude-standard"):
        raise ValueError("Unknown ignored dependency inputs")
    digest = hashlib.sha256()
    paths = _command(root, "git", "ls-files", "--cached", "-z").decode().split("\0")
    scanned = 0
    for relative in sorted(set(paths) - {""}):
        scanned += _hash_file(digest, root, relative)
        if scanned > _MAX_INPUT_BYTES:
            raise ValueError("Synapse input exceeds fingerprint budget")
    return digest.digest()


def _runtime_identity(root: Path) -> tuple[bytes, ...]:
    if sys.platform != "darwin":
        raise ValueError("SwiftPM evidence is supported only on configured macOS")
    return (
        sys.version.encode(),
        sys.executable.encode(),
        os.uname().release.encode(),
        _command(root, "/usr/bin/xcrun", "--find", "swift"),
        _command(root, "/usr/bin/xcrun", "--show-sdk-path"),
        _command(root, "/usr/bin/xcodebuild", "-version"),
        _command(root, "swift", "--version"),
        json.dumps(
            {k: v for k, v in os.environ.items() if k not in _IGNORED_WORKER_ENV},
            sort_keys=True,
        ).encode(),
    )


def _dependency_fingerprints(root: Path) -> tuple[bytes, ...]:
    build = root / ".build"
    if build.is_symlink():
        raise ValueError("External SwiftPM build directory")
    artifacts = build / "artifacts"
    if artifacts.is_symlink() or (artifacts.exists() and any(artifacts.iterdir())):
        raise ValueError("Binary SwiftPM dependency evidence is unsupported")
    checkouts = build / "checkouts"
    if checkouts.is_symlink():
        raise ValueError("External SwiftPM dependency checkout")
    if not checkouts.exists():
        return ()
    entries = sorted(checkouts.iterdir())
    if entries and not (root / "Package.resolved").is_file():
        raise ValueError("Unpinned SwiftPM dependency checkout")
    result: list[bytes] = []
    for checkout in entries:
        sha = _command(checkout, "git", "rev-parse", "--verify", "HEAD").strip()
        result.extend(
            (checkout.name.encode(), sha, _clean_checkout_fingerprint(checkout, sha))
        )
    return tuple(result)


def swift_test_input_fingerprint(
    root: Path, outputs: tuple[str, ...] = ()
) -> str | None:
    """Hash exact SwiftPM project bytes, index and runner, or reject this input."""
    root = root.resolve()
    try:
        if not (root / "Package.swift").is_file():
            return None
        stage, paths = _git_inputs(root, outputs)
        digest = hashlib.sha256()
        _hash_field(digest, str(root).encode())
        _hash_field(digest, _command(root, "git", "rev-parse", "--verify", "HEAD"))
        _hash_field(digest, stage)
        _hash_field(digest, json.dumps(outputs).encode())
        for field in (*_runtime_identity(root), *_dependency_fingerprints(root)):
            _hash_field(digest, field)
        total = 0
        for relative in paths:
            total += _hash_file(digest, root, relative)
            if total > _MAX_INPUT_BYTES:
                return None
        return digest.hexdigest()
    except (
        OSError,
        UnicodeError,
        RuntimeError,
        ValueError,
        subprocess.SubprocessError,
    ):
        return None
