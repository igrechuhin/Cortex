"""Tests for planning skill dynamic workflow with inter-phase data passing.

Covers:
- Happy path: create → register → complete, with plan_file_name threaded from create to register
- complete skipped when create status is not 'success'
- Missing required phase_inputs raises no error (tool decides); correct kwargs forwarded
- resolve_workflow_inputs correctly merges caller phase_inputs and prior-phase outputs
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from cortex.tools.skill_pack.models import (
    SkillPackManifest,
    SkillWorkflowPhase,
)
from cortex.tools.skill_pack.operations import (
    execute_sequential_workflow,
    resolve_workflow_inputs,
    skill_pack,
)

# ---------------------------------------------------------------------------
# Fixtures: plan tool return values
# ---------------------------------------------------------------------------

_CREATE_OK = json.dumps(
    {
        "status": "success",
        "plan_file_name": "my-plan.md",
        "plan_title": "My Plan",
    }
)

_CREATE_FAIL = json.dumps(
    {
        "status": "error",
        "error": "create failed",
    }
)

_REGISTER_OK = json.dumps({"status": "success"})
_COMPLETE_OK = json.dumps(
    {"status": "success", "archived_path": ".cortex/plans/archive/my-plan.md"}
)


def _noop_handoff(pack_name: str, phase_name: str, data: dict[str, object]) -> None:
    """No-op handoff stub for unit tests."""


def _planning_manifest() -> SkillPackManifest:
    """Return the planning manifest loaded from the real JSON file."""
    from pathlib import Path

    skills_dir = (
        Path(__file__).resolve().parent.parent.parent
        / "src"
        / "cortex"
        / "resources"
        / "skills"
    )
    return SkillPackManifest.model_validate_json(
        (skills_dir / "planning.json").read_text(encoding="utf-8")
    )


# ---------------------------------------------------------------------------
# Unit tests for resolve_workflow_inputs
# ---------------------------------------------------------------------------


def testresolve_workflow_inputs_prior_phase_output_threaded() -> None:
    """Prior-phase output is resolved and placed under the correct param name."""
    # Arrange
    phase = SkillWorkflowPhase(
        name="register",
        tool="plan",
        inputs={"create.plan_file_name": "plan_file_name"},
        outputs=["status"],
    )
    ctx: dict[str, object] = {
        "create": {"plan_file_name": "my-plan.md", "status": "success"}
    }

    # Act
    kwargs = resolve_workflow_inputs(phase, ctx, {})

    # Assert
    assert kwargs["plan_file_name"] == "my-plan.md"


def testresolve_workflow_inputs_caller_phase_inputs_used_when_no_prior() -> None:
    """Caller-provided phase_inputs are used when prior-phase output is absent."""
    # Arrange
    phase = SkillWorkflowPhase(
        name="create",
        tool="plan",
        inputs={},
        outputs=["plan_file_name", "plan_title", "status"],
    )
    phase_inputs: dict[str, dict[str, object]] = {
        "create": {"title": "My Plan", "content": "# Content"}
    }

    # Act
    kwargs = resolve_workflow_inputs(phase, {}, phase_inputs)

    # Assert
    assert kwargs["title"] == "My Plan"
    assert kwargs["content"] == "# Content"


def testresolve_workflow_inputs_prior_phase_overrides_caller_value() -> None:
    """Prior-phase resolved value overrides caller phase_inputs value."""
    # Arrange
    phase = SkillWorkflowPhase(
        name="register",
        tool="plan",
        inputs={"create.plan_file_name": "plan_file_name"},
        outputs=["status"],
    )
    ctx: dict[str, object] = {"create": {"plan_file_name": "actual-file.md"}}
    phase_inputs: dict[str, dict[str, object]] = {
        "register": {"plan_file_name": "stale-value.md"}
    }

    # Act
    kwargs = resolve_workflow_inputs(phase, ctx, phase_inputs)

    # Assert — prior-phase output wins
    assert kwargs["plan_file_name"] == "actual-file.md"


def testresolve_workflow_inputs_malformed_src_key_ignored() -> None:
    """A src_key without a dot separator is silently ignored."""
    # Arrange
    phase = SkillWorkflowPhase(
        name="register",
        tool="plan",
        inputs={"no_dot_key": "plan_file_name"},
        outputs=["status"],
    )

    # Act
    kwargs = resolve_workflow_inputs(phase, {}, {})

    # Assert — malformed key produces no entry
    assert "plan_file_name" not in kwargs


# ---------------------------------------------------------------------------
# execute_sequential_workflow — planning happy path
# ---------------------------------------------------------------------------


def test_planning_workflow_happy_path_data_threading() -> None:
    """Happy path: plan_file_name from create is forwarded to register and complete."""
    # Arrange
    manifest = _planning_manifest()
    register_calls: list[dict[str, object]] = []
    complete_calls: list[dict[str, object]] = []

    def fake_plan(**kwargs: object) -> str:
        op = kwargs.get("operation")
        if op == "create":
            return _CREATE_OK
        if op == "register":
            register_calls.append(dict(kwargs))
            return _REGISTER_OK
        if op == "complete":
            complete_calls.append(dict(kwargs))
            return _COMPLETE_OK
        return json.dumps({"status": "error", "error": f"unexpected op: {op}"})

    registry = {"plan": fake_plan}
    phase_inputs: dict[str, dict[str, object]] = {
        "create": {"title": "My Plan", "content": "# body"}
    }

    # Act
    with patch(
        "cortex.tools.skill_pack.operations._get_tool_registry", return_value=registry
    ):
        result = execute_sequential_workflow(manifest, _noop_handoff, phase_inputs)

    # Assert
    assert result.passed is True
    assert result.error is None
    # register received plan_file_name from create output
    assert len(register_calls) == 1
    assert register_calls[0]["plan_file_name"] == "my-plan.md"
    assert register_calls[0]["plan_title"] == "My Plan"
    # complete also received plan_title from create
    assert len(complete_calls) == 1
    assert complete_calls[0]["plan_title"] == "My Plan"


def test_planning_workflow_complete_skipped_when_create_fails() -> None:
    """complete phase is skipped when create returns error status."""
    # Arrange
    manifest = _planning_manifest()
    complete_calls: list[dict[str, object]] = []

    def fake_plan(**kwargs: object) -> str:
        op = kwargs.get("operation")
        if op == "create":
            return _CREATE_FAIL
        if op == "register":
            # register is still attempted (no condition on it)
            return _REGISTER_OK
        if op == "complete":
            complete_calls.append(dict(kwargs))
            return _COMPLETE_OK
        return json.dumps({"status": "error"})

    registry = {"plan": fake_plan}

    # Act
    with patch(
        "cortex.tools.skill_pack.operations._get_tool_registry", return_value=registry
    ):
        result = execute_sequential_workflow(manifest, _noop_handoff)

    # Assert — complete was skipped
    assert complete_calls == []
    complete_phase = next(p for p in result.phases if p.name == "complete")
    assert complete_phase.skipped is True


def test_planning_workflow_phase_outputs_captured() -> None:
    """Outputs declared in manifest are captured from tool result."""
    # Arrange
    manifest = _planning_manifest()

    def fake_plan(**kwargs: object) -> str:
        op = kwargs.get("operation")
        if op == "create":
            return _CREATE_OK
        if op == "register":
            return _REGISTER_OK
        if op == "complete":
            return _COMPLETE_OK
        return json.dumps({"status": "error"})

    registry = {"plan": fake_plan}

    # Act
    with patch(
        "cortex.tools.skill_pack.operations._get_tool_registry", return_value=registry
    ):
        result = execute_sequential_workflow(manifest, _noop_handoff)

    # Assert
    create_phase = next(p for p in result.phases if p.name == "create")
    assert create_phase.outputs.get("plan_file_name") == "my-plan.md"
    assert create_phase.outputs.get("plan_title") == "My Plan"


# ---------------------------------------------------------------------------
# skill_pack(operation="execute") dispatcher integration
# ---------------------------------------------------------------------------


def _fake_plan_router(**kwargs: object) -> str:
    """Route plan kwargs to canned responses by operation."""
    op = kwargs.get("operation")
    if op == "create":
        return _CREATE_OK
    if op == "register":
        return _REGISTER_OK
    if op == "complete":
        return _COMPLETE_OK
    return json.dumps({"status": "error"})


@pytest.mark.asyncio
@pytest.mark.timeout(15)
async def test_skill_pack_execute_planning_happy_path() -> None:
    """skill_pack(operation=execute, pack_name=planning) runs workflow and returns result."""
    manifest = _planning_manifest()
    registry = {"plan": _fake_plan_router}
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
        result = await skill_pack(
            operation="execute",
            pack_name="planning",
            phase_inputs={"create": {"title": "My Plan", "content": "# body"}},
        )
    data = json.loads(result)
    assert data["status"] == "success"
    assert data["passed"] is True
    assert isinstance(data["phases"], list)
    assert len(data["phases"]) == 3


@pytest.mark.asyncio
@pytest.mark.timeout(15)
async def test_skill_pack_execute_planning_manifest_loads_with_workflow() -> None:
    """planning manifest has a workflow block with three phases."""
    # Act
    result = await skill_pack(operation="load", pack_name="planning")
    data = json.loads(result)

    # Assert
    assert data["status"] == "success"
    pack = data["pack"]
    assert pack["workflow"] is not None
    phases = pack["workflow"]["phases"]
    assert len(phases) == 3
    phase_names = [p["name"] for p in phases]
    assert phase_names == ["create", "register", "complete"]


@pytest.mark.asyncio
@pytest.mark.timeout(15)
async def test_skill_pack_execute_planning_register_receives_plan_file_name() -> None:
    """plan_file_name from create output is injected into register kwargs."""
    manifest = _planning_manifest()
    captured_register_kwargs: list[dict[str, object]] = []

    def fake_plan(**kwargs: object) -> str:
        op = kwargs.get("operation")
        if op == "register":
            captured_register_kwargs.append(dict(kwargs))
        return _fake_plan_router(**kwargs)

    registry = {"plan": fake_plan}
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
        _ = await skill_pack(
            operation="execute",
            pack_name="planning",
            phase_inputs={"create": {"title": "My Plan", "content": "# body"}},
        )
    assert len(captured_register_kwargs) == 1
    assert captured_register_kwargs[0]["plan_file_name"] == "my-plan.md"
    assert captured_register_kwargs[0]["plan_title"] == "My Plan"
    assert captured_register_kwargs[0]["plan_title"] == "My Plan"
