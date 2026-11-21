"""Exercise the detached Cortex worker's fresh final test evidence lane."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import cast

import pytest

from cortex.core.execution_env import LocalExecutionEnvironment
from cortex.core.models import ModelDict
from cortex.core.quality_gate_config import (
    ProjectQualityGateConfig,
    save_quality_gate_config,
)
from cortex.core.session_config import write_session_config
from cortex.services.framework_adapters.base import CheckResult
from cortex.services.framework_adapters.base import TestResult as SuiteResult
from cortex.services.framework_adapters.swift_adapter import SwiftAdapter
from cortex.tools.execution import pre_commit_pipeline_processors as processors
from cortex.tools.execution import pre_commit_test_reuse as reuse
from cortex.tools.execution import pre_commit_zero_arg_tools as gate
from cortex.tools.execution.pre_commit_detached import compute_args_hash
from cortex.tools.execution.pre_commit_helpers_models import (
    CheckStats,
    PreCommitCheck,
    QualityCheckResult,
)
from cortex.tools.execution.pre_commit_test_gate_context import GateTestIntent, GateUse
from cortex.tools.execution.pre_commit_worker import (
    _run_worker_checks,  # pyright: ignore[reportPrivateUsage]
    _write_success_result,  # pyright: ignore[reportPrivateUsage]
)
from cortex.tools.session.pipeline_handoff import pipeline_handoff
from tests.tools.pipeline_handoff_test_support import (
    patch_pipeline_handoff_project_root,
)

_RUN = "abcdef123456"
_PHASE_A_JOB = "fedcba654321"
_FINAL_JOB = "fedcba654322"


def _phase(status: str) -> dict[str, str]:
    return {"status": status, "phase_status": "completed"}


class GateFixture:
    """A real worker pipeline with deterministic subprocess adapter results."""

    def __init__(
        self, root: Path, patch: pytest.MonkeyPatch, run_id: str = _RUN
    ) -> None:
        self.root = root.resolve()
        self.root.joinpath("Package.swift").touch()
        self.state = self.root / ".cortex" / ".session" / run_id / "commit"
        self.state.mkdir(parents=True, exist_ok=True)
        self.tests_started = 0
        self.non_test_checks = 0
        self.markdown_checks = 0
        self.owner = "a" * 64
        self.fingerprint: str | None = "b" * 64
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
        self.markdown_checks += 1
        if self.drift_on_markdown:
            self.fingerprint = "e" * 64
        return self.markdown

    def inputs(self, _root: Path, _outputs: tuple[str, ...]) -> str | None:
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

    def prepare_pipeline(self, use: GateUse | None) -> None:
        """Publish the fixture's authoritative commit phase."""
        phases = {"preflight": _phase("complete")}
        if use is not GateUse.PHASE_A:
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
        use: GateUse | None,
        *,
        test_filter: str | None = None,
        predecessors: tuple[int, ...] = (),
    ) -> dict[str, object]:
        """Execute the worker on the selected authoritative commit phase."""
        self.prepare_pipeline(use)
        intent = (
            GateTestIntent(use=use, run_id=_RUN, predecessors=predecessors)
            if use is not None
            else None
        )
        return self.run_worker(
            intent.model_dump_json() if intent is not None else None, test_filter
        )

    def run_worker(
        self, raw_intent: str | None, test_filter: str | None
    ) -> dict[str, object]:
        """Exercise the same decoded worker intent as a detached gate."""
        use = GateTestIntent.model_validate_json(raw_intent).use if raw_intent else None
        job_id = _PHASE_A_JOB if use is GateUse.PHASE_A else _FINAL_JOB
        args = argparse.Namespace(
            project_root=str(self.root),
            checks=["quality", "tests"],
            timeout=5400,
            coverage_threshold=0.90,
            strict=False,
            test_filter=test_filter,
            gate_test_intent=raw_intent,
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
    initial = fixture.run(GateUse.PHASE_A)
    final = fixture.run(GateUse.FINAL)
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
        GateUse.PHASE_A,
        test_filter="focused" if scenario == "filtered" else None,
    )
    if scenario == "drift":
        fixture.fingerprint = "c" * 64
    if scenario == "foreign":
        fixture.owner = "d" * 64
    final = fixture.run(None if scenario == "generic" else GateUse.FINAL)
    assert "reused_test_evidence" not in final
    assert fixture.tests_started == 2


def test_final_lane_distinguishes_detached_job_identity() -> None:
    """Fresh final cannot reuse the whole Phase A worker result."""
    args = (["quality", "tests"], 5400, 0.9, False, True)
    before = compute_args_hash(*args)
    phase_a = GateTestIntent(use=GateUse.PHASE_A, run_id=_RUN)
    final = GateTestIntent(use=GateUse.FINAL, run_id=_RUN)
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
    assert fixture.run(GateUse.PHASE_A)["success"] is True
    fixture.drift_on_markdown = True
    final = fixture.run(GateUse.FINAL)
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
    old = fixture.run(GateUse.PHASE_A)
    if scenario != "missing_receipt":
        receipt = fixture.state.parent.parent / f"pre_commit_result_{_PHASE_A_JOB}.json"
        _write_success_result(receipt, 0.0, 987, old, dict(fixture.markdown), True)
    predecessor = 0 if scenario == "foreign" else os.getppid()
    fixture.owner = "b" * 64
    if scenario == "drift":
        fixture.fingerprint = "c" * 64
    result = fixture.run(GateUse.PHASE_A, predecessors=(predecessor,))
    assert result["success"] is True
    assert fixture.non_test_checks == 2
    assert fixture.tests_started == (1 if scenario == "valid" else 2)
    assert ("reused_test_evidence" in result) is (scenario == "valid")


async def _commit_write(
    caller: str, phase: str, fields: dict[str, object]
) -> dict[str, object]:
    """Use the standard commit's flattened handoff for either bridge."""
    payload = {"operation": "write", "pipeline": "commit", "phase": phase, **fields}
    if caller == "bridge":
        assert write_session_config(payload)
        result = await pipeline_handoff()
    else:
        result = await pipeline_handoff(data=payload)
    return json.loads(result)


async def _configure_standard_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, reuse_enabled: bool
) -> GateFixture:
    monkeypatch.delenv("CORTEX_PIPELINE_SESSION_ID", raising=False)
    patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "cortex.core.session_config.get_current_project_root", lambda: tmp_path
    )
    monkeypatch.setattr(gate, "get_current_project_root", lambda: tmp_path)
    initialized = json.loads(
        await pipeline_handoff(operation="init", pipeline="commit")
    )
    fixture = GateFixture(tmp_path, monkeypatch, initialized["session_id"])
    _ = save_quality_gate_config(
        tmp_path,
        ProjectQualityGateConfig(
            test_timeout=5400, reuse_swiftpm_final_tests=reuse_enabled
        ),
    )

    async def spawn(*_args: object, **kwargs: object) -> ModelDict:
        assert kwargs["force_fresh"] is True
        assert kwargs["timeout"] == 5400
        return cast(ModelDict, fixture.run_worker(reuse.gate_intent_json(), None))

    monkeypatch.setattr(gate, "_spawn_and_poll_phase_a", spawn)
    return fixture


async def _prepare_standard_final_gate(caller: str) -> None:
    _ = await _commit_write(caller, "checks", {"status": "passed", "coverage": 0.92})
    _ = await _commit_write(caller, "docs", {"status": "complete"})
    _ = await _commit_write(caller, "validate", {"status": "passed"})
    if caller == "marked":
        _ = await pipeline_handoff(
            operation="mark_running", pipeline="commit", phase="final-gate"
        )
    elif caller == "task":
        _ = await pipeline_handoff(
            operation="write_task",
            pipeline="commit",
            phase="checks",
            data={"force_fresh": True},
        )
    else:
        handoff = await _commit_write(caller, "checks", {"force_fresh": True})
        assert "task_file" in handoff and "result_file" not in handoff

    pipeline = json.loads(await pipeline_handoff(operation="read", pipeline="commit"))
    assert pipeline["phases"]["checks"]["coverage"] == 0.92


@pytest.mark.parametrize("caller", ["native", "bridge", "marked", "task"])
@pytest.mark.parametrize("scenario", ["same", "changed", "unknown", "disabled"])
async def test_standard_commit_gate_routes_and_validates_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caller: str, scenario: str
) -> None:
    """Standard handoffs record the full suite and always recheck Markdown."""
    fixture = await _configure_standard_commit(
        tmp_path, monkeypatch, reuse_enabled=scenario != "disabled"
    )
    _ = await _commit_write(caller, "preflight", {"status": "complete"})
    environment = LocalExecutionEnvironment()
    assert (await gate.run_quality_gate_inner(None, environment))["success"] is True
    await _prepare_standard_final_gate(caller)
    if scenario in ("changed", "unknown"):
        fixture.fingerprint = "c" * 64 if scenario == "changed" else None
    final = await gate.run_quality_gate_inner(None, environment)

    assert final["success"] is True
    assert fixture.markdown_checks == 2
    assert fixture.tests_started == (1 if scenario == "same" else 2)
    assert ("reused_test_evidence" in final) is (scenario == "same")
