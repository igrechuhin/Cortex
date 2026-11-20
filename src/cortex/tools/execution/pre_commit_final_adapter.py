"""Opt-in adapter from native commit to its exact full detached Swift gate."""

from __future__ import annotations

import asyncio
import secrets
import subprocess
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from cortex.core.context_logging import MCPContext
from cortex.core.models import ModelDict
from cortex.core.quality_gate_config import (
    load_quality_gate_config,
    staged_final_enabled,
)
from cortex.tools.execution.pre_commit_final_parity import run_staged_final_parity
from cortex.tools.execution.pre_commit_final_ref_guard import commit_verified_tree
from cortex.tools.execution.pre_commit_final_tree import (
    FinalGateAuthority,
    FinalSwiftResult,
    StagedCandidate,
    capture_staged_candidate,
)
from cortex.tools.execution.pre_commit_final_worker_proof import (
    final_worker_challenge,
    verify_worker_proof,
)
from cortex.tools.execution.pre_commit_ownership import (
    current_owner,
    envelope_owned,
    request_owner,
)
from cortex.tools.execution.pre_commit_process import read_result_file
from cortex.tools.execution.pre_commit_quality_gate_job import quality_gate_job_path
from cortex.tools.execution.session_paths import session_dir
from cortex.tools.session.pipeline_handoff_session import get_session_id


class _Phase(BaseModel):
    status: str
    phase_status: str | None = None


class _Pipeline(BaseModel):
    session_id: str
    pipeline: str
    phases: dict[str, _Phase]


class _TestChecks(BaseModel):
    model_config = ConfigDict(strict=True)
    success: bool
    tests_passed: int
    tests_failed: int
    coverage: float


class _WorkerResult(BaseModel):
    language: str
    status: str
    success: bool
    results: dict[str, object]
    checks_performed: list[str]
    test_filter: str | None = None
    full_suite_validated: bool | None = None
    reused_test_evidence: object = None
    skipped_checks: list[str] = Field(default_factory=list)


class _Attempt(BaseModel):
    model_config = ConfigDict(frozen=True)
    challenge: str
    candidate: StagedCandidate
    timeout: int
    coverage: float


_AUTHORITY = FinalGateAuthority()
_ATTEMPTS: dict[tuple[str, str, str], _Attempt] = {}
_RECEIPTS: dict[tuple[str, str, str], tuple[int, float, str, str]] = {}
_MAX_ATTEMPTS = 128
_GATE_ERRORS = (
    OSError,
    ValueError,
    ValidationError,
    RuntimeError,
    subprocess.SubprocessError,
)
_LOCK = asyncio.Lock()
_REQUIRED = frozenset(
    {
        "fix_errors",
        "quality",
        "format",
        "synapse_format",
        "synapse_lint",
        "spelling",
        "type_check",
        "tests",
    }
)


def _error(reason: str) -> ModelDict:
    return {"status": "error", "preflight_passed": False, "error": reason}


def staged_final_preparation_complete(root: Path, run_id: str) -> bool:
    """Require local preparation without importing an early gate verdict."""
    if len(run_id) != 12 or any(c not in "0123456789abcdef" for c in run_id):
        return False
    path = session_dir(root) / run_id / "commit" / "pipeline.json"
    if path.resolve() != path:
        return False
    state = _Pipeline.model_validate_json(path.read_text())
    if state.session_id != run_id or state.pipeline != "commit":
        return False
    phase = state.phases.get("checks")
    # This path has no early test verdict. A previous checks phase belongs
    # to the legacy pipeline and must not be adopted as staged-final proof.
    if phase is not None:
        return False
    expected = {"preflight": "complete", "docs": "complete", "validate": "passed"}
    return all(
        (row := state.phases.get(name)) is not None
        and row.status == status
        and row.phase_status == "completed"
        for name, status in expected.items()
    )


def parse_worker_verdict(
    payload: dict[str, object], threshold: float
) -> FinalSwiftResult:
    """Translate an untrimmed authenticated full SwiftPM worker verdict."""
    result = _WorkerResult.model_validate(payload.get("result"))
    tests = _TestChecks.model_validate(result.results.get("tests"))
    raw_md = payload.get("markdown_result")
    md = cast(dict[str, object], raw_md) if isinstance(raw_md, dict) else {}
    if (
        md.get("status") != "success"
        or md.get("files_with_errors") != 0
        or result.status != "success"
        or not result.success
        or result.language != "swift"
        or result.skipped_checks
        or not _REQUIRED <= set(result.checks_performed)
    ):
        raise ValueError("Final Swift worker did not pass every required check")
    return FinalSwiftResult(
        checks_passed=tests.success,
        full_suite=result.test_filter is None
        and result.full_suite_validated is not False,
        reused_tests=result.reused_test_evidence is not None,
        tests_executed=tests.tests_passed + tests.tests_failed,
        tests_failed=tests.tests_failed,
        coverage=tests.coverage,
        required_coverage=threshold,
    )


def _attempt(
    key: tuple[str, str, str],
    candidate: StagedCandidate,
    timeout: int,
    threshold: float,
) -> _Attempt:
    pending = _ATTEMPTS.get(key)
    if pending is None:
        if len(_ATTEMPTS) >= _MAX_ATTEMPTS:
            raise ValueError("Too many final Swift requests")
        pending = _Attempt(
            challenge=secrets.token_hex(32),
            candidate=candidate,
            timeout=timeout,
            coverage=threshold,
        )
        _ATTEMPTS[key] = pending
    if (pending.candidate, pending.timeout, pending.coverage) != (
        candidate,
        timeout,
        threshold,
    ):
        raise ValueError("Final Swift candidate or execution settings drifted")
    return pending


async def _run_attempt(
    root: Path,
    key: tuple[str, str, str],
    pending: _Attempt,
    invoke: Callable[[], Awaitable[ModelDict]],
) -> ModelDict:
    with final_worker_challenge(pending.challenge):
        job = quality_gate_job_path(root, pending.timeout, pending.coverage)
        result = await invoke()
    if result.get("status") in {"running", "timeout"}:
        return result
    return await _admit_result(root, key, pending, job, result)


async def _admit_result(
    root: Path,
    key: tuple[str, str, str],
    pending: _Attempt,
    job: Path,
    result: ModelDict,
) -> ModelDict:
    _ = _ATTEMPTS.pop(key, None)
    payload, status = await read_result_file(job)
    if (
        payload is None
        or status != "completed"
        or not envelope_owned(payload)
        or not verify_worker_proof(job, payload, pending.challenge)
        or result.get("cached_result") is True
        or result.get("status") != "success"
        or result.get("preflight_passed") is not True
    ):
        return _error("No authenticated terminal result for this final Swift worker")
    return await _record_receipt(root, key, pending, payload, result)


async def _record_receipt(
    root: Path,
    key: tuple[str, str, str],
    pending: _Attempt,
    payload: dict[str, object],
    result: ModelDict,
) -> ModelDict:
    verdict = parse_worker_verdict(payload, pending.coverage)
    if not verdict.passed() or capture_staged_candidate(root) != pending.candidate:
        return _error("Final Swift tests failed or staged tree changed")
    await run_staged_final_parity(root)
    receipt = _AUTHORITY.issue(
        key[2], pending.candidate, capture_staged_candidate(root), verdict
    )
    if receipt is None:
        return _error("Final Swift tests failed or staged tree changed")
    if len(_RECEIPTS) >= _MAX_ATTEMPTS:
        _ = _RECEIPTS.pop(next(iter(_RECEIPTS)))
    _RECEIPTS[key] = (pending.timeout, pending.coverage, *receipt)
    result["staged_final_authorized"] = True
    return result


async def staged_swift_gate(
    root: Path,
    *,
    intent: str,
    ctx: MCPContext | None,
    timeout: int,
    threshold: float,
    test_filter: str | None,
    invoke: Callable[[], Awaitable[ModelDict]],
    commit_message: str | None = None,
) -> ModelDict:
    """Recognize explicit native-only opt-in; retain no authority after restart."""
    if ctx is None or test_filter is not None:
        return _error("Final Swift gate requires an unfiltered native MCP session")
    try:
        if not staged_final_enabled(root, load_quality_gate_config(root)):
            return _error("Staged final Swift mode is not enabled for this project")
        run_id = get_session_id(root, mint=False, pipeline="commit")
        if not staged_final_preparation_complete(root, run_id):
            return _error(
                "Checkpoint, documentation and validation must complete before final Swift"
            )
        return await _with_owner(
            root, ctx, run_id, intent, timeout, threshold, invoke, commit_message
        )
    except _GATE_ERRORS as exc:
        return _error(str(exc))


async def _with_owner(
    root: Path,
    ctx: MCPContext,
    run_id: str,
    intent: str,
    timeout: int,
    threshold: float,
    invoke: Callable[[], Awaitable[ModelDict]],
    commit_message: str | None,
) -> ModelDict:
    async with _LOCK:
        with request_owner(ctx):
            key = (str(root.resolve()), current_owner(), run_id)
            candidate = capture_staged_candidate(root)
            receipt = _RECEIPTS.get(key)
            if _receipt_valid(run_id, candidate, timeout, threshold, receipt):
                if intent == "commit-staged-final":
                    return await _write_verified_commit(
                        root, key, candidate, commit_message
                    )
                return _authorized()
            if intent in {"verify-staged-final", "commit-staged-final"}:
                return _error(
                    "The exact staged tree has no authenticated final Swift result"
                )
            _ = _RECEIPTS.pop(key, None)
            return await _run_attempt(
                root, key, _attempt(key, candidate, timeout, threshold), invoke
            )


def _authorized() -> ModelDict:
    return {
        "status": "success",
        "preflight_passed": True,
        "staged_final_authorized": True,
    }


def _receipt_valid(
    run_id: str,
    candidate: StagedCandidate,
    timeout: int,
    threshold: float,
    receipt: tuple[int, float, str, str] | None,
) -> bool:
    return (
        receipt is not None
        and (receipt[0], receipt[1]) == (timeout, threshold)
        and _AUTHORITY.verify(run_id, candidate, receipt[2], receipt[3])
    )


async def _write_verified_commit(
    root: Path,
    key: tuple[str, str, str],
    candidate: StagedCandidate,
    message: str | None,
) -> ModelDict:
    # No retries from an old receipt, even if a regular hook rejects the commit.
    if not message or candidate.branch is None or candidate.tree is None:
        return _error("Verified branch, staged tree and commit message are required")
    _ = _RECEIPTS.pop(key, None)
    commit = await asyncio.to_thread(
        commit_verified_tree,
        root,
        candidate.branch,
        candidate.head,
        candidate.tree,
        message,
    )
    return {"status": "success", "commit_sha": commit, "committed_tree": candidate.tree}
