"""Tests for the opt-in commit staged candidate verifier."""

import subprocess
from pathlib import Path

import pytest

from cortex.tools.execution.pre_commit_final_ref_guard import commit_verified_tree
from cortex.tools.execution.pre_commit_final_tree import (
    FinalGateAuthority,
    FinalGateState,
    FinalGateTransition,
    FinalSwiftResult,
    StagedCandidate,
    capture_staged_candidate,
)

RUN = "123456789abc"


def _result(**changes: object) -> FinalSwiftResult:
    payload: dict[str, object] = {
        "checks_passed": True,
        "full_suite": True,
        "reused_tests": False,
        "tests_executed": 20,
        "tests_failed": 0,
        "coverage": 0.93,
        "required_coverage": 0.9,
    }
    return FinalSwiftResult.model_validate(payload | changes)


def test_receipt_is_bound_to_run_candidate_and_live_server() -> None:
    """Reject forged or stale results even when they were once green."""
    candidate = StagedCandidate(root="/repo", head="commit", index_hash="a" * 64)
    changed = candidate.model_copy(update={"index_hash": "b" * 64})
    authority = FinalGateAuthority()
    receipt = authority.issue(RUN, candidate, candidate, _result())
    assert receipt is not None
    data, signature = receipt
    assert authority.verify(RUN, candidate, data, signature)
    assert not authority.verify(RUN, candidate, data + " ", signature)
    assert not authority.verify("0" * 12, candidate, data, signature)
    assert not authority.verify(RUN, changed, data, signature)
    assert not FinalGateAuthority().verify(RUN, candidate, data, signature)
    assert authority.issue(RUN, candidate, changed, _result()) is None


@pytest.mark.parametrize(
    "fields",
    [
        {"checks_passed": False},
        {"full_suite": False},
        {"reused_tests": True},
        {"tests_executed": 0},
        {"tests_failed": 1},
        {"coverage": 0.89},
    ],
)
def test_no_receipt_for_incomplete_or_failed_worker(fields: dict[str, object]) -> None:
    """Selected, reused or failed tests cannot authorize a final commit."""
    candidate = StagedCandidate(root="/repo", head="commit", index_hash="a" * 64)
    assert (
        FinalGateAuthority().issue(RUN, candidate, candidate, _result(**fields)) is None
    )


def _run_git(root: Path, *args: str) -> None:
    _ = subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, timeout=10
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _run_git(tmp_path, "init")
    _ = (tmp_path / "input.swift").write_text("// source")
    _run_git(tmp_path, "add", "--", "input.swift")
    _run_git(
        tmp_path,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "--no-gpg-sign",
        "-m",
        "initial",
    )
    return tmp_path


def test_stage_capture_requires_exact_clean_candidate(repo: Path) -> None:
    """Changing unstaged bytes or adding an untracked input rejects capture."""
    base = capture_staged_candidate(repo)
    _ = (repo / "input.swift").write_text("// revised")
    with pytest.raises(subprocess.CalledProcessError):
        _ = capture_staged_candidate(repo)
    _run_git(repo, "add", "--", "input.swift")
    assert capture_staged_candidate(repo) != base
    _ = (repo / "new.swift").write_text("// untracked")
    with pytest.raises(ValueError, match="untracked"):
        _ = capture_staged_candidate(repo)


def test_stage_capture_rejects_assume_unchanged(repo: Path) -> None:
    """Git index flags cannot conceal direct edits to candidate files."""
    _run_git(repo, "update-index", "--assume-unchanged", "input.swift")
    with pytest.raises(ValueError, match="masked"):
        _ = capture_staged_candidate(repo)


@pytest.mark.asyncio
async def test_transition_runs_once_and_authorizes_only_the_final_candidate(
    repo: Path,
) -> None:
    """A deferred guard cannot commit and later staged edits invalidate success."""
    gate = FinalGateTransition(RUN, repo, FinalGateAuthority())
    calls = 0

    async def invoke() -> FinalSwiftResult:
        nonlocal calls
        calls += 1
        assert gate.state is FinalGateState.RUNNING
        assert not gate.permits_commit()
        return _result()

    assert gate.state is FinalGateState.TESTS_DEFERRED
    assert not gate.permits_commit()
    assert await gate.run(invoke)
    assert gate.permits_commit()
    assert not await gate.run(invoke)
    assert calls == 1
    _ = (repo / "input.swift").write_text("// after")
    _run_git(repo, "add", "--", "input.swift")
    assert not gate.permits_commit()


@pytest.mark.asyncio
async def test_transition_rejects_worker_crash_or_candidate_drift(repo: Path) -> None:
    """Authority cannot be issued after a crash or intervening tracked write."""
    gate = FinalGateTransition(RUN, repo, FinalGateAuthority())

    async def crash() -> FinalSwiftResult:
        raise RuntimeError("worker crashed")

    with pytest.raises(RuntimeError, match="crashed"):
        _ = await gate.run(crash)
    assert gate.state is FinalGateState.FAILED
    assert not gate.permits_commit()
    gate = FinalGateTransition(RUN, repo, FinalGateAuthority())

    async def drift() -> FinalSwiftResult:
        _ = (repo / "input.swift").write_text("// during")
        _run_git(repo, "add", "--", "input.swift")
        return _result()

    assert not await gate.run(drift)
    assert gate.state is FinalGateState.FAILED
    assert not gate.permits_commit()


@pytest.mark.parametrize("drift", [False, True])
def test_atomic_commit_checks_after_native_git_hooks(repo: Path, drift: bool) -> None:
    """Reject a normal pre-commit hook that changes the tested index before the ref moves."""
    _require_reference_hook(repo)
    _run_git(repo, "config", "user.name", "Test")
    _run_git(repo, "config", "user.email", "test@example.invalid")
    _run_git(repo, "config", "commit.gpgSign", "false")
    _ = (repo / "input.swift").write_text("// staged")
    _run_git(repo, "add", "--", "input.swift")
    candidate = capture_staged_candidate(repo)
    assert candidate.branch and candidate.tree
    if drift:
        _install_index_changing_hook(repo)
        with pytest.raises(subprocess.CalledProcessError):
            _ = commit_verified_tree(
                repo, candidate.branch, candidate.head, candidate.tree, "guard"
            )
        assert capture_staged_candidate(repo).head == candidate.head
    else:
        revision = commit_verified_tree(
            repo, candidate.branch, candidate.head, candidate.tree, "guard"
        )
        assert revision != candidate.head
        assert capture_staged_candidate(repo).tree == candidate.tree


def _require_reference_hook(root: Path) -> None:
    result = subprocess.run(
        [
            "git",
            "-c",
            "hook.probe.event=reference-transaction",
            "-c",
            "hook.probe.command=true",
            "hook",
            "list",
            "reference-transaction",
        ],
        cwd=root,
        check=False,
        capture_output=True,
        timeout=10,
    )
    if result.returncode != 0 or b"probe" not in result.stdout.splitlines():
        pytest.skip("Git lacks command-scoped reference hooks; see git-hook")


def _install_index_changing_hook(root: Path) -> None:
    hook = root / ".git" / "hooks" / "pre-commit"
    _ = hook.write_text(
        "#!/bin/sh\nprintf '%s\\n' '// drifted' > input.swift\ngit add -- input.swift\n"
    )
    hook.chmod(0o755)
