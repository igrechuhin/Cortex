"""Exercise the detached Cortex worker's fresh final test evidence lane."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import pytest

from cortex.services.framework_adapters.base import CheckResult
from cortex.services.framework_adapters.base import TestResult as SuiteResult
from cortex.services.framework_adapters.swift_adapter import SwiftAdapter
from cortex.tools.execution import pre_commit_pipeline_processors as processors
from cortex.tools.execution import pre_commit_test_reuse as reuse
from cortex.tools.execution.pre_commit_detached import compute_args_hash
from cortex.tools.execution.pre_commit_helpers_models import (
    CheckStats,
    PreCommitCheck,
    QualityCheckResult,
)
from cortex.tools.execution.pre_commit_worker import (
    _run_worker_checks,  # pyright: ignore[reportPrivateUsage]
    _write_success_result,  # pyright: ignore[reportPrivateUsage]
)

_RUN = "abcdef123456"
_PHASE_A_JOB = "fedcba654321"
_FINAL_JOB = "fedcba654322"


def _phase(status: str) -> dict[str, str]:
    return {"status": status, "phase_status": "completed"}


class GateFixture:
    """A real worker pipeline with deterministic subprocess adapter results."""

    def __init__(self, root: Path, patch: pytest.MonkeyPatch) -> None:
        self.root = root.resolve()
        self.root.joinpath("Package.swift").touch()
        self.state = self.root / ".cortex" / ".session" / _RUN / "commit"
        self.state.mkdir(parents=True)
        self.tests_started = 0
        self.non_test_checks = 0
        self.owner = "a" * 64
        self.fingerprint = "b" * 64
        self.drift_on_markdown = False
        self.coverage: float | None = 0.92
        self.markdown = {"status": "success", "files_with_errors": 0}
        patch.setattr(reuse, "worker_owner", lambda: self.owner)
        patch.setattr(reuse, "swift_test_input_fingerprint", self.inputs)
        patch.setattr(processors, "_execute_tests", self.execute_tests)
        patch.setattr(
            "cortex.tools.execution.pre_commit_worker._run_checks", self.checks
        )
        patch.setattr(
            "cortex.tools.execution.pre_commit_worker.run_markdown_lint",
            self.check_markdown,
        )

    def check_markdown(self, _root: str) -> dict[str, str | int]:
        if self.drift_on_markdown:
            self.fingerprint = "e" * 64
        return self.markdown

    def inputs(self, _root: Path, _outputs: tuple[str, ...]) -> str:
        """Return current simulated checkout fingerprint."""
        return self.fingerprint

    def execute_tests(self, *_args: object, **_kwargs: object) -> SuiteResult:
        """Return observed complete suite success, without host toolchain use."""
        self.tests_started += 1
        return SuiteResult(
            success=True,
            tests_run=30,
            tests_passed=30,
            tests_failed=0,
            coverage=self.coverage,
            pass_rate=1.0,
            output="actual fresh tests",
            errors=[],
        )

    def checks(self, *_args: object, **kwargs: object) -> dict[str, object]:
        """Run the real test processor after a counted fresh non-test check."""
        self.non_test_checks += 1
        results: dict[str, CheckResult | SuiteResult | QualityCheckResult] = {}
        stats = CheckStats(
            total_errors=0, total_warnings=0, files_modified=[], checks_performed=[]
        )
        selected = kwargs.get("test_filter")
        processors.process_tests_check(
            SwiftAdapter(str(self.root)),
            [PreCommitCheck.TESTS],
            900,
            0.90,
            results,
            stats,
            test_filter=selected if isinstance(selected, str) else None,
        )
        return {
            "success": True,
            "results": {key: value.model_dump() for key, value in results.items()},
        }

    def prepare_pipeline(self, use: reuse.GateUse | None) -> None:
        """Publish the fixture's authoritative commit phase."""
        phases = {"preflight": _phase("complete")}
        if use is not reuse.GateUse.PHASE_A:
            phases.update(
                checks=_phase("passed"),
                docs=_phase("complete"),
                validate=_phase("passed"),
            )
        path = self.state / "pipeline.json"
        _ = path.write_text(
            json.dumps({"session_id": _RUN, "pipeline": "commit", "phases": phases})
        )

    def run(
        self,
        use: reuse.GateUse | None,
        *,
        test_filter: str | None = None,
        predecessors: tuple[int, ...] = (),
    ) -> dict[str, object]:
        """Execute the worker on the selected authoritative commit phase."""
        self.prepare_pipeline(use)
        job_id = _PHASE_A_JOB if use is reuse.GateUse.PHASE_A else _FINAL_JOB
        intent = (
            reuse.GateTestIntent(use=use, run_id=_RUN, predecessors=predecessors)
            if use is not None
            else None
        )
        args = argparse.Namespace(
            project_root=str(self.root),
            checks=["quality", "tests"],
            timeout=5400,
            coverage_threshold=0.90,
            strict=False,
            test_filter=test_filter,
            gate_test_intent=intent.model_dump_json() if intent is not None else None,
            include_markdown_lint=True,
        )
        result, _ = _run_worker_checks(
            args, self.root / f"pre_commit_result_{job_id}.json", True
        )
        return result


def test_final_lane_runs_fresh_checks_and_reuses_only_tests(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two workers execute non-test checks; only Phase A executes Swift tests."""
    fixture = GateFixture(tmp_path, monkeypatch)
    initial = fixture.run(reuse.GateUse.PHASE_A)
    final = fixture.run(reuse.GateUse.FINAL)
    assert initial["success"] is True and final["success"] is True
    assert fixture.tests_started == 1
    assert fixture.non_test_checks == 2
    provenance = final["reused_test_evidence"]
    assert isinstance(provenance, dict)
    assert provenance["source_job_id"] == _PHASE_A_JOB
    assert provenance["tests_executed_in_final"] == 0
    assert provenance["coverage"] == 0.92


@pytest.mark.parametrize(
    "scenario", ["generic", "drift", "foreign", "missing_coverage", "filtered", "lint"]
)
def test_unproven_evidence_executes_tests_fresh(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scenario: str
) -> None:
    """Old callers, changed evidence, and incomplete suites cannot skip tests."""
    fixture = GateFixture(tmp_path, monkeypatch)
    if scenario == "missing_coverage":
        fixture.coverage = None
    if scenario == "lint":
        fixture.markdown = {"status": "error", "files_with_errors": 1}
    _ = fixture.run(
        reuse.GateUse.PHASE_A,
        test_filter="focused" if scenario == "filtered" else None,
    )
    if scenario == "drift":
        fixture.fingerprint = "c" * 64
    if scenario == "foreign":
        fixture.owner = "d" * 64
    final = fixture.run(None if scenario == "generic" else reuse.GateUse.FINAL)
    assert "reused_test_evidence" not in final
    assert fixture.tests_started == 2


def test_final_lane_distinguishes_detached_job_identity() -> None:
    """Fresh final cannot reuse the whole Phase A worker result."""
    args = (["quality", "tests"], 5400, 0.9, False, True)
    before = compute_args_hash(*args)
    phase_a = reuse.GateTestIntent(use=reuse.GateUse.PHASE_A, run_id=_RUN)
    final = reuse.GateTestIntent(use=reuse.GateUse.FINAL, run_id=_RUN)
    with reuse.gate_intent_scope(phase_a):
        first = compute_args_hash(*args)
    with reuse.gate_intent_scope(final):
        second = compute_args_hash(*args)
    assert len({before, first, second}) == 3


def test_final_lane_rejects_inputs_changed_during_checks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A post-test mutation cannot produce an accepted reused result."""
    fixture = GateFixture(tmp_path, monkeypatch)
    assert fixture.run(reuse.GateUse.PHASE_A)["success"] is True
    fixture.drift_on_markdown = True
    final = fixture.run(reuse.GateUse.FINAL)
    assert final["success"] is False
    assert "reused_test_evidence" not in final
    assert fixture.tests_started == 1


@pytest.mark.parametrize("scenario", ["valid", "drift", "foreign", "missing_receipt"])
def test_phase_a_reconnect_reuses_only_verified_swift_tests(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scenario: str
) -> None:
    """A prior terminal undelivered receipt can save only the expensive tests."""
    fixture = GateFixture(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "cortex.tools.execution.pre_commit_worker.worker_owner", lambda: fixture.owner
    )
    old = fixture.run(reuse.GateUse.PHASE_A)
    if scenario != "missing_receipt":
        receipt = fixture.state.parent.parent / f"pre_commit_result_{_PHASE_A_JOB}.json"
        _write_success_result(receipt, 0.0, 987, old, dict(fixture.markdown), True)
    predecessor = 0 if scenario == "foreign" else os.getppid()
    fixture.owner = "b" * 64
    if scenario == "drift":
        fixture.fingerprint = "c" * 64
    result = fixture.run(reuse.GateUse.PHASE_A, predecessors=(predecessor,))
    assert result["success"] is True
    assert fixture.non_test_checks == 2
    assert fixture.tests_started == (1 if scenario == "valid" else 2)
    assert ("reused_test_evidence" in result) is (scenario == "valid")
