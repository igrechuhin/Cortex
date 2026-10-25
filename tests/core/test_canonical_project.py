"""Behavioral tests for canonical main-worktree identity resolution."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from cortex.core.canonical_project import (
    CanonicalProjectError,
    CanonicalReadFailure,
    parse_worktree_records,
    resolve_canonical_identity,
)
from cortex.core.execution_env import ExecutionEnvironment, ExecutionResult
from tests.tools.canonical_read_test_support import (
    add_linked_worktree,
    build_canonical_main,
    init_git_repo,
)


def _ok(stdout: str) -> ExecutionResult:
    return ExecutionResult(returncode=0, stdout=stdout, stderr="", duration_ms=1)


def _fail() -> ExecutionResult:
    return ExecutionResult(returncode=128, stdout="", stderr="err", duration_ms=1)


def _fake_env(responses: list[ExecutionResult]) -> ExecutionEnvironment:
    env = MagicMock(spec=ExecutionEnvironment)
    env.execute.side_effect = responses
    return env


@pytest.mark.timeout(30)
def test_main_worktree_resolves_local_is_canonical(tmp_path: Path) -> None:
    main = tmp_path / "main"
    build_canonical_main(main)

    identity = resolve_canonical_identity(main)

    assert identity.relation.value == "local_is_canonical"
    assert identity.canonical_root == main.resolve()


@pytest.mark.timeout(30)
def test_linked_worktree_maps_to_canonical_main(tmp_path: Path) -> None:
    main = tmp_path / "main"
    build_canonical_main(main)
    worktree = tmp_path / "wt"
    add_linked_worktree(main, worktree)

    identity = resolve_canonical_identity(worktree)

    assert identity.relation.value == "linked_worktree"
    assert identity.canonical_root == main.resolve()
    assert identity.local_root == worktree.resolve()
    assert identity.common_git_dir == (main / ".git").resolve()


@pytest.mark.timeout(30)
def test_non_git_root_fails_closed(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()

    with pytest.raises(CanonicalProjectError) as excinfo:
        _ = resolve_canonical_identity(plain)

    assert excinfo.value.failure is CanonicalReadFailure.NOT_A_GIT_CHECKOUT


@pytest.mark.timeout(30)
def test_subdirectory_of_worktree_is_not_a_listed_worktree(
    tmp_path: Path,
) -> None:
    main = tmp_path / "main"
    build_canonical_main(main)
    worktree = tmp_path / "wt"
    add_linked_worktree(main, worktree)

    with pytest.raises(CanonicalProjectError) as excinfo:
        _ = resolve_canonical_identity(worktree / ".cortex")

    assert excinfo.value.failure is CanonicalReadFailure.LOCAL_ROOT_NOT_LISTED


@pytest.mark.timeout(30)
def test_duplicate_local_worktree_records_fail_closed(tmp_path: Path) -> None:
    main = tmp_path / "main"
    build_canonical_main(main)
    porcelain = f"worktree {main}\nHEAD abc\n\nworktree {main}\nHEAD abc\n\n"
    env = _fake_env(
        [
            _ok(""),
            _ok(str(main / ".git")),
            _ok(porcelain),
        ]
    )

    with pytest.raises(CanonicalProjectError) as excinfo:
        _ = resolve_canonical_identity(main, env=env)

    assert excinfo.value.failure is CanonicalReadFailure.AMBIGUOUS_LOCAL_WORKTREE


@pytest.mark.timeout(30)
def test_bare_main_worktree_fails_closed(tmp_path: Path) -> None:
    bare = tmp_path / "bare.git"
    bare.mkdir()
    porcelain = f"bare\n\nworktree {bare}\nHEAD abc\n\n"
    env = _fake_env([_ok(""), _ok(str(bare)), _ok(porcelain)])

    with pytest.raises(CanonicalProjectError) as excinfo:
        _ = resolve_canonical_identity(bare, env=env)

    assert excinfo.value.failure is CanonicalReadFailure.AMBIGUOUS_MAIN_WORKTREE


@pytest.mark.timeout(30)
def test_canonical_without_memory_bank_fails_closed(tmp_path: Path) -> None:
    main = tmp_path / "main"
    init_git_repo(main)
    _ = (main / "code.txt").write_text("x", encoding="utf-8")

    with pytest.raises(CanonicalProjectError) as excinfo:
        _ = resolve_canonical_identity(main)

    assert excinfo.value.failure is CanonicalReadFailure.CANONICAL_NOT_CORTEX_ROOT


@pytest.mark.timeout(30)
def test_cross_repository_mapping_fails_closed(tmp_path: Path) -> None:
    main = tmp_path / "main"
    build_canonical_main(main)
    other = tmp_path / "other"
    build_canonical_main(other)
    porcelain = f"worktree {other}\nHEAD abc\n\nworktree {main}\nHEAD abc\n\n"
    env = _fake_env(
        [
            _ok(""),
            _ok(str(main / ".git")),
            _ok(porcelain),
            _ok(str(other / ".git")),
        ]
    )

    with pytest.raises(CanonicalProjectError) as excinfo:
        _ = resolve_canonical_identity(main, env=env)

    assert excinfo.value.failure is CanonicalReadFailure.COMMON_DIR_MISMATCH


@pytest.mark.timeout(30)
def test_git_failure_fails_closed(tmp_path: Path) -> None:
    main = tmp_path / "main"
    build_canonical_main(main)
    env = _fake_env([_ok(""), _ok(str(main / ".git")), _fail()])

    with pytest.raises(CanonicalProjectError) as excinfo:
        _ = resolve_canonical_identity(main, env=env)

    assert excinfo.value.failure is CanonicalReadFailure.GIT_FAILURE


@pytest.mark.timeout(30)
def test_symlinked_plans_dir_fails_closed(tmp_path: Path) -> None:
    main = tmp_path / "main"
    build_canonical_main(main)
    outside = tmp_path / "outside-plans"
    outside.mkdir()
    plans = main / ".cortex" / "plans"
    for entry in plans.iterdir():
        entry.unlink()
    plans.rmdir()
    plans.symlink_to(outside, target_is_directory=True)

    with pytest.raises(CanonicalProjectError) as excinfo:
        _ = resolve_canonical_identity(main)

    assert excinfo.value.failure is CanonicalReadFailure.TRAVERSAL_ESCAPE


@pytest.mark.timeout(30)
def test_symlinked_cortex_dir_inside_root_fails_closed(tmp_path: Path) -> None:
    main = tmp_path / "main"
    build_canonical_main(main)
    _ = (main / ".cortex").rename(main / ".cortex-real-content")
    shadow = main / "shadow"
    (shadow / "memory-bank").mkdir(parents=True)
    # AI: .cortex symlinks to an inside-root directory; containment alone
    # would pass, so the symlink guard itself must reject this mapping.
    (main / ".cortex").symlink_to(shadow, target_is_directory=True)

    with pytest.raises(CanonicalProjectError) as excinfo:
        _ = resolve_canonical_identity(main)

    assert excinfo.value.failure is CanonicalReadFailure.TRAVERSAL_ESCAPE


def test_parse_worktree_records_handles_spaceless_flags() -> None:
    porcelain = (
        "worktree /repo/main\nHEAD abc\nbranch refs/heads/main\n\n"
        "worktree /repo/wt\ndetached\nHEAD def\n\nbare\n\n"
    )
    records = parse_worktree_records(porcelain)

    assert records[0]["worktree"] == "/repo/main"
    assert "detached" in records[1]
    assert records[2] == {"bare": ""}
