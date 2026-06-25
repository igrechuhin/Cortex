"""Tests for skill_pack(operation='execute') and execute_sequential_workflow."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from cortex.tools.skill_pack.models import (
    SkillPackManifest,
    SkillWorkflow,
    SkillWorkflowPhase,
    SkillWorkflowResult,
)
from cortex.tools.skill_pack.operations import (
    execute_sequential_workflow,
    skill_pack,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_GATE_OK = json.dumps({"status": "success", "preflight_passed": True})
_GATE_FAIL = json.dumps({"status": "success", "preflight_passed": False})
_AUTOFIX_OK = json.dumps({"status": "success"})


def _noop_handoff(pack_name: str, phase_name: str, data: dict[str, object]) -> None:
    """No-op handoff stub for unit tests."""


_GATE_CONDITION = "not gate_1.get('preflight_passed', True)"
_GATE_SUCCESS = "preflight_passed == True"


def _quality_workflow_phases() -> list[SkillWorkflowPhase]:
    """Return the three quality-workflow phases (gate_1, autofix, gate_2)."""
    return [
        SkillWorkflowPhase(
            name="gate_1",
            tool="run_quality_gate",
            required=True,
            max_iterations=1,
            outputs=["preflight_passed", "status"],
            success_condition=_GATE_SUCCESS,
        ),
        SkillWorkflowPhase(
            name="autofix",
            tool="autofix",
            required=False,
            condition=_GATE_CONDITION,
            retry_condition=_GATE_CONDITION,
            max_iterations=3,
            outputs=["status"],
        ),
        SkillWorkflowPhase(
            name="gate_2",
            tool="run_quality_gate",
            required=True,
            max_iterations=1,
            outputs=["preflight_passed", "status"],
            success_condition=_GATE_SUCCESS,
        ),
    ]


def _quality_manifest() -> SkillPackManifest:
    """Return a minimal quality manifest with the three-phase workflow."""
    return SkillPackManifest(
        name="quality",
        description="quality",
        tools=["run_quality_gate", "autofix"],
        workflow=SkillWorkflow(mode="sequential", phases=_quality_workflow_phases()),
    )


# ---------------------------------------------------------------------------
# execute_sequential_workflow — happy path
# ---------------------------------------------------------------------------


def test_execute_workflow_gate_passes_first_time() -> None:
    """Happy path: gate passes on first call — autofix is skipped."""
    # Arrange
    manifest = _quality_manifest()
    call_log: list[str] = []

    def fake_gate() -> str:
        call_log.append("gate")
        return _GATE_OK

    def fake_autofix() -> str:  # pragma: no cover
        call_log.append("autofix")
        return _AUTOFIX_OK

    registry = {"run_quality_gate": fake_gate, "autofix": fake_autofix}

    # Act
    with patch(
        "cortex.tools.skill_pack.operations._get_tool_registry", return_value=registry
    ):
        result = execute_sequential_workflow(manifest, _noop_handoff)

    # Assert
    assert isinstance(result, SkillWorkflowResult)
    assert result.passed is True
    assert result.error is None
    # gate_1 ran, autofix skipped (condition false when gate passed), gate_2 ran
    non_skipped = [p for p in result.phases if not p.skipped]
    assert len(non_skipped) == 2  # gate_1 and gate_2
    assert call_log == ["gate", "gate"]
    # Total iterations = gate_1(1) + gate_2(1); autofix skipped counts 0
    assert result.iterations == 2


def test_execute_workflow_autofix_runs_when_gate_fails_then_passes() -> None:
    """Gate fails → autofix runs once → gate_2 passes → result.passed True."""
    # Arrange
    manifest = _quality_manifest()
    call_log: list[str] = []

    def fake_gate() -> str:
        call_log.append("gate")
        # First call fails; subsequent calls pass
        return _GATE_FAIL if len(call_log) == 1 else _GATE_OK

    def fake_autofix() -> str:
        call_log.append("autofix")
        return _AUTOFIX_OK

    registry = {"run_quality_gate": fake_gate, "autofix": fake_autofix}

    # Act
    with patch(
        "cortex.tools.skill_pack.operations._get_tool_registry", return_value=registry
    ):
        result = execute_sequential_workflow(manifest, _noop_handoff)

    # Assert
    assert result.passed is True
    # gate_1 failed → autofix ran → gate_2 passed
    assert "gate" in call_log
    assert "autofix" in call_log
    # At least gate_1, autofix (1 iter), gate_2
    assert result.iterations >= 3


def test_execute_workflow_retry_cap_enforced() -> None:
    """Gate never passes → autofix runs up to max_iterations=3 → passed=False."""
    # Arrange
    manifest = _quality_manifest()
    autofix_calls: list[int] = []

    def fake_gate() -> str:
        return _GATE_FAIL

    def fake_autofix() -> str:
        autofix_calls.append(1)
        return _AUTOFIX_OK

    registry = {"run_quality_gate": fake_gate, "autofix": fake_autofix}

    # Act
    with patch(
        "cortex.tools.skill_pack.operations._get_tool_registry", return_value=registry
    ):
        result = execute_sequential_workflow(manifest, _noop_handoff)

    # Assert
    # autofix runs at most max_iterations=3 times
    assert len(autofix_calls) <= 3
    # gate_2 still runs and fails → overall passed=False
    assert result.passed is False


def test_execute_workflow_condition_false_skips_phase() -> None:
    """A phase whose condition evaluates to False is recorded as skipped."""
    # Arrange
    always_skip_phase = SkillWorkflowPhase(
        name="never",
        tool="autofix",
        required=False,
        condition="False",
        max_iterations=1,
    )
    manifest = SkillPackManifest(
        name="test",
        description="test",
        tools=["autofix"],
        workflow=SkillWorkflow(
            mode="sequential",
            phases=[always_skip_phase],
        ),
    )
    autofix_calls: list[int] = []

    def fake_autofix() -> str:  # pragma: no cover
        autofix_calls.append(1)
        return _AUTOFIX_OK

    registry = {"autofix": fake_autofix}

    # Act
    with patch(
        "cortex.tools.skill_pack.operations._get_tool_registry", return_value=registry
    ):
        result = execute_sequential_workflow(manifest, _noop_handoff)

    # Assert
    assert autofix_calls == []
    assert len(result.phases) == 1
    assert result.phases[0].skipped is True
    assert result.passed is True  # no required phase failed


def test_execute_workflow_missing_workflow_returns_error() -> None:
    """Manifest with no workflow block returns SkillWorkflowResult with error."""
    # Arrange
    manifest = SkillPackManifest(
        name="no_workflow",
        description="no workflow",
        tools=[],
        workflow=None,
    )

    # Act
    result = execute_sequential_workflow(manifest, _noop_handoff)

    # Assert
    assert result.passed is False
    assert result.error is not None
    assert "no workflow" in result.error.lower()


# ---------------------------------------------------------------------------
# skill_pack(operation="execute") — dispatcher integration tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.timeout(15)
async def test_skill_pack_execute_missing_pack_name_returns_error() -> None:
    """skill_pack(operation=execute) without pack_name returns structured error."""
    # Arrange / Act
    result = await skill_pack(operation="execute")
    data = json.loads(result)

    # Assert
    assert data["status"] == "error"
    assert "pack_name" in data["error"]


@pytest.mark.asyncio
@pytest.mark.timeout(15)
async def test_skill_pack_execute_unknown_pack_returns_error() -> None:
    """skill_pack(operation=execute) with unknown pack returns error + available."""
    # Arrange / Act
    result = await skill_pack(operation="execute", pack_name="no_such_pack_xyz")
    data = json.loads(result)

    # Assert
    assert data["status"] == "error"
    assert "not found" in data["error"].lower()
    assert "available" in data


@pytest.mark.asyncio
@pytest.mark.timeout(15)
async def test_skill_pack_execute_pack_without_workflow_returns_error() -> None:
    """skill_pack(operation=execute) on a pack with no workflow block returns error."""
    # Arrange: use a fake manifest without workflow
    no_wf_manifest = SkillPackManifest(
        name="core",
        description="core",
        tools=["session"],
        workflow=None,
    )
    with patch(
        "cortex.tools.skill_pack.operations._load_all_manifests",
        return_value=[no_wf_manifest],
    ):
        result = await skill_pack(operation="execute", pack_name="core")

    data = json.loads(result)

    # Assert
    assert data["status"] == "error"
    assert "workflow" in data["error"].lower()


@pytest.mark.asyncio
@pytest.mark.timeout(15)
async def test_skill_pack_execute_quality_happy_path() -> None:
    """skill_pack(operation=execute, pack_name=quality) runs workflow and returns result."""
    # Arrange
    manifest = _quality_manifest()

    def fake_gate() -> str:
        return _GATE_OK

    def fake_autofix() -> str:  # pragma: no cover
        return _AUTOFIX_OK

    registry = {"run_quality_gate": fake_gate, "autofix": fake_autofix}

    with (
        patch(
            "cortex.tools.skill_pack.operations._load_all_manifests",
            return_value=[manifest],
        ),
        patch(
            "cortex.tools.skill_pack.operations._get_tool_registry",
            return_value=registry,
        ),
    ):
        result = await skill_pack(operation="execute", pack_name="quality")

    data = json.loads(result)

    # Assert
    assert data["status"] == "success"
    assert data["passed"] is True
    assert isinstance(data["iterations"], int)
    assert isinstance(data["phases"], list)


@pytest.mark.asyncio
@pytest.mark.timeout(15)
async def test_skill_pack_unknown_operation_error() -> None:
    """skill_pack with unknown operation returns updated error message."""
    # Arrange / Act
    result = await skill_pack(operation="unknown_op")  # type: ignore[arg-type]
    data = json.loads(result)

    # Assert
    assert data["status"] == "error"
    assert "execute" in data["error"]
