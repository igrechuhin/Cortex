"""Server-side building blocks for a staged-tree-bound full commit verdict.

This module does not alter the default commit workflow or admit deferred tests.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import subprocess
from collections.abc import Awaitable, Callable
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class StagedCandidate(BaseModel):
    """Candidate identity held by the uninterrupted commit server."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    root: str
    head: str
    index_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    tree: str | None = None
    branch: str | None = None


class FinalSwiftResult(BaseModel):
    """Authoritative worker verdict, never a client-supplied phase write."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    checks_passed: bool
    full_suite: bool
    reused_tests: bool
    tests_executed: int = Field(ge=0)
    tests_failed: int = Field(ge=0)
    coverage: float = Field(ge=0, le=1, allow_inf_nan=False)
    required_coverage: float = Field(ge=0, le=1, allow_inf_nan=False)

    def passed(self) -> bool:
        """Require a real, unfiltered, non-reused invocation."""
        return (
            self.checks_passed
            and self.full_suite
            and not self.reused_tests
            and self.tests_executed > 0
            and self.tests_failed == 0
            and self.coverage >= self.required_coverage
        )


class _Receipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    run_id: str = Field(pattern=r"^[0-9a-f]{12}$")
    candidate: StagedCandidate
    result: FinalSwiftResult


class FinalGateAuthority:
    """Sign only verified staged candidates; a new process cannot adopt receipts."""

    def __init__(self) -> None:
        self._secret = secrets.token_bytes(32)

    def issue(
        self,
        run_id: str,
        before: StagedCandidate,
        after: StagedCandidate,
        result: FinalSwiftResult,
    ) -> tuple[str, str] | None:
        """Record a complete final verdict only for unchanged inputs."""
        if before != after or not result.passed():
            return None
        data = _Receipt(run_id=run_id, candidate=after, result=result).model_dump_json()
        return data, self._sign(data)

    def verify(
        self, run_id: str, current: StagedCandidate, data: str, signature: str
    ) -> bool:
        """Verify the signed receipt immediately before authorizing the commit."""
        if not signature.isascii() or not hmac.compare_digest(
            self._sign(data), signature
        ):
            return False
        try:
            receipt = _Receipt.model_validate_json(data)
        except ValidationError:
            return False
        return (
            receipt.run_id == run_id
            and receipt.candidate == current
            and receipt.result.passed()
        )

    def _sign(self, data: str) -> str:
        return hmac.digest(self._secret, data.encode(), "sha256").hex()


def _git(root: Path, *args: str) -> bytes:
    return subprocess.check_output(
        ["git", "-c", "core.fsmonitor=false", *args],
        cwd=root,
        stderr=subprocess.DEVNULL,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
        timeout=30,
    )


def capture_staged_candidate(root: Path) -> StagedCandidate:
    """Reject tracked worktree divergence, untracked inputs, and masked index paths."""
    root = root.resolve(strict=True)
    if (
        Path(os.fsdecode(_git(root, "rev-parse", "--show-toplevel").rstrip(b"\n")))
        != root
    ):
        raise ValueError("The final SwiftPM gate must run at the repository root")
    if _git(root, "ls-files", "--unmerged", "-z"):
        raise ValueError("The candidate has unmerged paths")
    if any(
        entry[:1] != b"H"
        for entry in _git(root, "ls-files", "-v", "-z").split(b"\0")
        if entry
    ):
        raise ValueError("The candidate has masked index paths")
    _ = _git(root, "diff", "--quiet", "--no-ext-diff", "--ignore-submodules=none", "--")
    if _git(root, "ls-files", "--others", "--exclude-standard", "-z"):
        raise ValueError("The candidate has untracked inputs")
    index = _git(root, "ls-files", "--stage", "-z")
    tree = _git(root, "write-tree").decode().strip()
    if _git(root, "ls-files", "--stage", "-z") != index:
        raise ValueError("The index changed while the candidate was captured")
    return StagedCandidate(
        root=str(root),
        tree=tree,
        branch=_git(root, "symbolic-ref", "HEAD").decode().strip(),
        head=_git(root, "rev-parse", "--verify", "HEAD").decode().strip(),
        index_hash=hashlib.sha256(index).hexdigest(),
    )


class FinalGateState(StrEnum):
    """A deferred suite is not an early passing verdict."""

    TESTS_DEFERRED = "tests-deferred"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"


class FinalGateTransition:
    """Server-owned transition from fast guards to final worker completion."""

    def __init__(self, run_id: str, root: Path, authority: FinalGateAuthority) -> None:
        self._run_id = run_id
        self._root = root
        self._authority = authority
        self._candidate = capture_staged_candidate(root)
        self._state = FinalGateState.TESTS_DEFERRED
        self._receipt: tuple[str, str] | None = None

    @property
    def state(self) -> FinalGateState:
        """Expose deferred, pending, failed and passed as distinct verdicts."""
        return self._state

    async def run(
        self, invoke_full_gate: Callable[[], Awaitable[FinalSwiftResult]]
    ) -> bool:
        """Run the exact full worker once and never issue on error or tree drift."""
        if self._state is not FinalGateState.TESTS_DEFERRED:
            return False
        self._state = FinalGateState.RUNNING
        try:
            if capture_staged_candidate(self._root) != self._candidate:
                return False
            result = await invoke_full_gate()
            self._receipt = self._authority.issue(
                self._run_id,
                self._candidate,
                capture_staged_candidate(self._root),
                result,
            )
            return self._receipt is not None
        finally:
            self._state = (
                FinalGateState.PASSED if self._receipt else FinalGateState.FAILED
            )

    def permits_commit(self) -> bool:
        """Recheck current candidate against the in-process receipt at use time."""
        if self._state is not FinalGateState.PASSED or self._receipt is None:
            return False
        try:
            return self._authority.verify(
                self._run_id, capture_staged_candidate(self._root), *self._receipt
            )
        except (OSError, ValueError, subprocess.SubprocessError):
            return False
