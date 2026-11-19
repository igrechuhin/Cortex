"""Run-scoped, independently measured evidence for a fresh final test check."""

from __future__ import annotations

import math
import os
import re
import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from cortex.core.quality_gate_config import load_quality_gate_config
from cortex.services.framework_adapters.base import TestResult
from cortex.tools.execution.pre_commit_test_reuse_inputs import (
    swift_test_input_fingerprint,
)
from cortex.tools.execution.pre_commit_workspace import worker_owner
from cortex.tools.execution.session_paths import session_dir


class GateUse(StrEnum):
    """Authorized role inside the native commit workflow."""

    PHASE_A = "phase-a"
    FINAL = "final"


class GateTestIntent(BaseModel):
    """Server-derived workflow identity transported to the detached worker."""

    model_config = ConfigDict(frozen=True)
    use: GateUse
    run_id: str = Field(pattern=r"^[a-f0-9]{12}$")
    swift_outputs: tuple[str, ...] = ()
    predecessors: tuple[int, ...] = ()


class TestEvidence(BaseModel):
    """A test result created by a green detached Phase A execution."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    owner: str = Field(pattern=r"^[a-f0-9]{64}$")
    run_id: str = Field(pattern=r"^[a-f0-9]{12}$")
    job_id: str = Field(pattern=r"^[a-f0-9]{12}$")
    completed_at: float = Field(allow_inf_nan=False)
    fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    tests: TestResult
    server_pid: int | None = None
    test_timeout: int | None = None


class _TestLane(BaseModel):
    """In-flight evidence isolated to one detached worker invocation."""

    root: Path
    intent: GateTestIntent
    fingerprint: str | None = None
    candidate: TestResult | None = None
    reused: TestEvidence | None = None
    server_pid: int | None = None
    test_timeout: int | None = None


_GATE_INTENT: ContextVar[GateTestIntent | None] = ContextVar(
    "quality_gate_test_intent", default=None
)
_TEST_LANE: ContextVar[_TestLane | None] = ContextVar(
    "quality_gate_test_lane", default=None
)
_MAX_AGE_SECONDS = 4 * 3600


class _PipelinePhase(BaseModel):
    status: str | None = None
    phase_status: str | None = None

    def completed(self) -> bool:
        return self.phase_status == "completed" and self.status in (
            "complete",
            "completed",
            "passed",
        )


class _CommitPipeline(BaseModel):
    session_id: str
    pipeline: str
    phases: dict[str, _PipelinePhase]


def _verified_context(root: Path, intent: GateTestIntent) -> bool:
    path = session_dir(root) / intent.run_id / "commit" / "pipeline.json"
    try:
        if path.resolve() != path:
            return False
        value = _CommitPipeline.model_validate_json(path.read_text())
    except (ValueError, OSError, RuntimeError):
        return False
    if value.session_id != intent.run_id or value.pipeline != "commit":
        return False
    complete = {name for name, phase in value.phases.items() if phase.completed()}
    if "preflight" not in complete:
        return False
    if intent.use is GateUse.PHASE_A:
        return "checks" not in complete
    return {"checks", "docs", "validate"} <= complete


def derive_gate_intent(
    root: Path, value: object, fresh: bool, test_filter: str | None
) -> GateTestIntent | None:
    """Recognize only explicit, opted-in, unfiltered commit phases."""
    if not fresh or test_filter is not None or value not in ("phase-a", "final"):
        return None
    policy = load_quality_gate_config(root)
    if not policy.reuse_swiftpm_final_tests:
        return None
    from cortex.tools.session.pipeline_handoff_session import (
        get_session_id,
        recoverable_predecessors,
    )

    active = get_session_id(root, mint=False, pipeline="commit")
    if not re.fullmatch(r"[a-f0-9]{12}", active):
        return None
    intent = GateTestIntent(
        use=GateUse(str(value)),
        predecessors=(
            recoverable_predecessors(root, active) if value == "phase-a" else ()
        ),
        run_id=active,
        swift_outputs=tuple(
            sorted({item.value for item in policy.swiftpm_final_test_outputs})
        ),
    )
    return intent if _verified_context(root, intent) else None


@contextmanager
def gate_intent_scope(intent: GateTestIntent | None) -> Iterator[None]:
    """Keep routing/identity bound to only this asynchronous request."""
    token = _GATE_INTENT.set(intent)
    try:
        yield
    finally:
        _GATE_INTENT.reset(token)


def gate_intent_json() -> str | None:
    """Serialize the current internal request identity for hashing and spawn."""
    value = _GATE_INTENT.get()
    return value.model_dump_json() if value is not None else None


def _evidence_path(root: Path, intent: GateTestIntent) -> Path:
    return session_dir(root) / intent.run_id / "commit" / "phase-a-test-evidence.json"


@contextmanager
def worker_test_lane(
    root: Path, raw: str | None, test_timeout: int | None = None
) -> Iterator[_TestLane | None]:
    """Enable evidence only under a real detached owner and verified run state."""
    lane = None
    if raw and worker_owner():
        try:
            intent = GateTestIntent.model_validate_json(raw)
        except ValidationError:
            intent = None
        if intent is not None and _verified_context(root, intent):
            lane = _TestLane(
                root=root,
                intent=intent,
                server_pid=os.getppid(),
                test_timeout=test_timeout,
            )
    if lane is not None and lane.intent.use is GateUse.PHASE_A:
        path = _evidence_path(root, lane.intent)
        try:
            if path.resolve() != path:
                lane = None
            elif not lane.intent.predecessors:
                path.unlink(missing_ok=True)
        except (OSError, RuntimeError):
            lane = None
    token = _TEST_LANE.set(lane)
    try:
        yield lane
    finally:
        _TEST_LANE.reset(token)


def _eligible(tests: TestResult, threshold: float) -> bool:
    measured = tests.coverage
    return (
        tests.success
        and not tests.execution_uncertain
        and tests.tests_run > 0
        and tests.tests_passed > 0
        and tests.tests_failed == 0
        and not tests.errors
        and measured is not None
        and math.isfinite(measured)
        and 0.0 < measured <= 1.0
        and measured >= threshold
    )


def begin_test_evidence(threshold: float) -> TestResult | None:
    """Fingerprint immediately before test execution or final evidence use."""
    lane = _TEST_LANE.get()
    if lane is None:
        return None
    lane.fingerprint = swift_test_input_fingerprint(
        lane.root, lane.intent.swift_outputs
    )
    if lane.fingerprint is None:
        return None
    if lane.intent.use is GateUse.PHASE_A and not lane.intent.predecessors:
        return None
    evidence = _read_evidence(lane)
    if evidence is None:
        return None
    if (
        not _matches_evidence_owner(lane, evidence)
        or evidence.run_id != lane.intent.run_id
        or evidence.fingerprint != lane.fingerprint
        or not 0 <= time.time() - evidence.completed_at <= _MAX_AGE_SECONDS
        or not _eligible(evidence.tests, threshold)
    ):
        return None
    lane.reused = evidence
    return _reuse_result(evidence, lane.intent.use)


def _matches_evidence_owner(lane: _TestLane, evidence: TestEvidence) -> bool:
    """Ordinary final reuse is private; reconnect requires the real terminal job."""
    if lane.intent.use is GateUse.FINAL:
        return evidence.owner == worker_owner()
    if (
        evidence.owner == worker_owner()
        or evidence.server_pid not in lane.intent.predecessors
        or lane.test_timeout is None
        or evidence.test_timeout != lane.test_timeout
    ):
        return False
    path = session_dir(lane.root) / f"pre_commit_result_{evidence.job_id}.json"
    try:
        if path.resolve() != path:
            return False
        terminal = _TerminalEvidence.model_validate_json(path.read_text())
    except (OSError, RuntimeError, ValidationError):
        return False
    return terminal.eligible(evidence.owner)


class _TerminalEvidence(BaseModel):
    status: str
    owner: str
    quality_gate_pending: bool = False
    result: dict[str, object]
    markdown_result: dict[str, object]

    def eligible(self, owner: str) -> bool:
        return (
            self.status == "completed"
            and self.owner == owner
            and self.quality_gate_pending
            and self.result.get("success") is True
            and not self.result.get("skipped_checks")
            and self.markdown_result.get("status") == "success"
            and self.markdown_result.get("files_with_errors") == 0
        )


def _reuse_result(evidence: TestEvidence, use: GateUse = GateUse.FINAL) -> TestResult:
    return evidence.tests.model_copy(
        deep=True,
        update={
            "output": (
                "Full test results reused from observed green Phase A; "
                f"no {use.value} tests executed."
            ),
            "tests_run": 0,
            "tests_passed": 0,
            "skipped_tests": 0,
        },
    )


def _read_evidence(lane: _TestLane) -> TestEvidence | None:
    try:
        path = _evidence_path(lane.root, lane.intent)
        return (
            TestEvidence.model_validate_json(path.read_text())
            if path.resolve() == path
            else None
        )
    except (OSError, RuntimeError, ValidationError):
        return None


def finish_test_evidence(tests: TestResult, threshold: float) -> None:
    """Retain only a fully measured Phase A candidate with stable test inputs."""
    lane = _TEST_LANE.get()
    if (
        lane is not None
        and lane.intent.use is GateUse.PHASE_A
        and lane.fingerprint is not None
        and _eligible(tests, threshold)
        and swift_test_input_fingerprint(lane.root, lane.intent.swift_outputs)
        == lane.fingerprint
    ):
        lane.candidate = tests.model_copy(deep=True)


def test_lane_active() -> bool:
    """Explicit commit evidence never relies on the legacy skip stamp."""
    return _TEST_LANE.get() is not None


def did_reused_inputs_drift(lane: _TestLane | None) -> bool:
    """Block old evidence if inputs changed during remaining final checks."""
    return (
        lane is not None
        and lane.reused is not None
        and swift_test_input_fingerprint(lane.root, lane.intent.swift_outputs)
        != lane.fingerprint
    )


def publish_test_evidence(
    lane: _TestLane | None,
    job_id: str,
    result: dict[str, object],
    markdown: dict[str, object] | None,
) -> None:
    """Issue only after a green worker (and mark explicit reused provenance)."""
    if lane is None:
        return
    if lane.reused is not None:
        _mark_reuse(lane.reused, result, lane.intent.use)
        return
    if (
        lane.intent.use is not GateUse.PHASE_A
        or lane.candidate is None
        or lane.fingerprint is None
        or result.get("success") is not True
        or result.get("skipped_checks")
        or markdown is None
        or markdown.get("files_with_errors") != 0
        or markdown.get("status") != "success"
        or swift_test_input_fingerprint(lane.root, lane.intent.swift_outputs)
        != lane.fingerprint
        or (owner := worker_owner()) is None
    ):
        return
    _save_evidence(lane, job_id, owner, lane.fingerprint, lane.candidate)


def _save_evidence(
    lane: _TestLane, job_id: str, owner: str, fingerprint: str, candidate: TestResult
) -> None:
    from cortex.tools.execution.pre_commit_worker import atomic_write

    evidence = TestEvidence(
        owner=owner,
        run_id=lane.intent.run_id,
        job_id=job_id,
        completed_at=time.time(),
        fingerprint=fingerprint,
        tests=candidate,
        server_pid=lane.server_pid,
        test_timeout=lane.test_timeout,
    )
    atomic_write(
        _evidence_path(lane.root, lane.intent), evidence.model_dump(mode="json")
    )


def _mark_reuse(
    original: TestEvidence, result: dict[str, object], use: GateUse
) -> None:
    result["reused_test_evidence"] = {
        "source_job_id": original.job_id,
        "source_completed_at": original.completed_at,
        (
            "tests_executed_in_final"
            if use is GateUse.FINAL
            else "tests_executed_after_reconnect"
        ): 0,
        "tests_passed_in_phase_a": original.tests.tests_passed,
        "coverage": original.tests.coverage,
    }
