"""Resolve Swift test evidence roles from a bound commit pipeline."""

import re
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.quality_gate_config import load_quality_gate_config
from cortex.tools.execution.session_paths import session_dir
from cortex.tools.session.pipeline_handoff_session import (
    get_session_id,
    passive_session_id,
    recoverable_predecessors,
)


class GateUse(StrEnum):
    """Role of a full gate in the standard commit workflow."""

    PHASE_A = "phase-a"
    FINAL = "final"


class GateTestIntent(BaseModel):
    """Server-derived workflow identity transported to the detached worker."""

    model_config = ConfigDict(frozen=True)
    use: GateUse
    run_id: str = Field(pattern=r"^[a-f0-9]{12}$")
    swift_outputs: tuple[str, ...] = ()
    predecessors: tuple[int, ...] = ()
    trust_swiftpm_symlink_metadata: bool = False


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

    def frontier(self) -> GateUse | None:
        complete = {name for name, phase in self.phases.items() if phase.completed()}
        if "preflight" not in complete or "final-gate" in complete:
            return None
        if {"checks", "docs", "validate"} <= complete:
            return GateUse.FINAL
        later = {"docs", "validate", "final-gate"}
        if "checks" not in complete and later.isdisjoint(self.phases):
            return GateUse.PHASE_A
        return None

    def inferred_use(self) -> GateUse | None:
        frontier = self.frontier()
        if frontier is GateUse.FINAL:
            phase = self.phases.get("final-gate")
            if phase is None or (phase.status, phase.phase_status) != (
                "running",
                "running",
            ):
                return None
        return frontier


def _read_commit_pipeline(root: Path, run_id: str) -> _CommitPipeline | None:
    if not re.fullmatch(r"[a-f0-9]{12}", run_id):
        return None
    path = session_dir(root) / run_id / "commit" / "pipeline.json"
    try:
        if path.resolve() != path:
            return None
        value = _CommitPipeline.model_validate_json(path.read_text())
    except (ValueError, OSError, RuntimeError):
        return None
    return value if value.session_id == run_id and value.pipeline == "commit" else None


def standard_commit_frontier(root: Path) -> GateUse | None:
    """Read the current bound run without adopting a stale or foreign run."""
    state = _read_commit_pipeline(root, passive_session_id(root))
    return state.frontier() if state is not None else None


def verified_gate_context(root: Path, intent: GateTestIntent) -> bool:
    """Check that the worker still belongs to the requested commit phase."""
    state = _read_commit_pipeline(root, intent.run_id)
    return state is not None and state.frontier() is intent.use


def derive_gate_intent(
    root: Path, value: object, fresh: bool, test_filter: str | None
) -> GateTestIntent | None:
    """Route fresh, full SwiftPM gates inside a verified commit."""
    if not fresh or test_filter is not None or value not in (None, "phase-a", "final"):
        return None
    if not (root / "Package.swift").is_file():
        return None
    policy = load_quality_gate_config(root)
    if not policy.reuse_swiftpm_final_tests:
        return None
    active = (
        passive_session_id(root)
        if value is None
        else get_session_id(root, mint=False, pipeline="commit")
    )
    state = _read_commit_pipeline(root, active)
    if state is None:
        return None
    use = state.inferred_use() if value is None else GateUse(str(value))
    if use is None or state.frontier() is not use:
        return None
    return GateTestIntent(
        use=use,
        predecessors=(
            recoverable_predecessors(root, active) if use is GateUse.PHASE_A else ()
        ),
        run_id=active,
        swift_outputs=tuple(sorted(set(policy.swiftpm_final_test_outputs))),
        trust_swiftpm_symlink_metadata=policy.trust_swiftpm_symlink_metadata,
    )
