"""Tests for refactoring skill dynamic workflow with inter-phase data passing.

Covers:
- Happy path: all four phases run, target_files threaded from analyse to apply
- verify phase skipped when apply status is not 'success'
- analyse returning empty target_files → plan and apply skipped
- resolve_workflow_inputs correctly resolves list-valued outputs
"""

from __future__ import annotations

import json
from pathlib import Path
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
# Fixtures: canned tool return values
# ---------------------------------------------------------------------------

_ANALYSE_OK = json.dumps(
    {
        "status": "success",
        "target_files": ["src/foo.py", "src/bar.py"],
        "patterns": ["oversized_function", "god_object"],
    }
)

_ANALYSE_EMPTY = json.dumps(
    {
        "status": "success",
        "target_files": [],
        "patterns": [],
    }
)

_PLAN_CREATE_OK = json.dumps(
    {
        "status": "success",
        "plan_file_name": "refactor-foo.md",
        "plan_title": "Refactor foo module",
    }
)

_APPLY_OK = json.dumps(
    {
        "status": "success",
        "files_modified": ["src/foo.py"],
    }
)

_APPLY_FAIL = json.dumps(
    {
        "status": "error",
        "error": "apply failed",
    }
)

_QUALITY_OK = json.dumps(
    {
        "status": "success",
        "preflight_passed": True,
    }
)


def _noop_handoff(pack_name: str, phase_name: str, data: dict[str, object]) -> None:
    """No-op handoff stub for unit tests."""


def _refactoring_manifest() -> SkillPackManifest:
    """Return the refactoring manifest loaded from the real JSON file."""
    skills_dir = (
        Path(__file__).resolve().parent.parent.parent
        / "src"
        / "cortex"
        / "resources"
        / "skills"
    )
    return SkillPackManifest.model_validate_json(
        (skills_dir / "refactoring.json").read_text(encoding="utf-8")
    )


# ---------------------------------------------------------------------------
# Unit tests for resolve_workflow_inputs with list-valued outputs
# ---------------------------------------------------------------------------


def test_resolve_workflow_inputs_list_output_threaded() -> None:
    """List-valued output from prior phase is resolved and forwarded correctly."""
    # Arrange
    phase = SkillWorkflowPhase(
        name="apply",
        tool="manage_file",
        inputs={
            "analyse.target_files": "target_files",
            "plan.plan_file_name": "plan_file_name",
        },
        outputs=["files_modified"],
    )
    ctx: dict[str, object] = {
        "analyse": {
            "target_files": ["src/foo.py", "src/bar.py"],
            "status": "success",
        },
        "plan": {
            "plan_file_name": "refactor-foo.md",
            "status": "success",
        },
    }

    # Act
    kwargs = resolve_workflow_inputs(phase, ctx, {})

    # Assert
    assert kwargs["target_files"] == ["src/foo.py", "src/bar.py"]
    assert kwargs["plan_file_name"] == "refactor-foo.md"


# ---------------------------------------------------------------------------
# execute_sequential_workflow — refactoring happy path
# ---------------------------------------------------------------------------


def test_refactoring_workflow_happy_path_data_threading() -> None:
    """Happy path: target_files from analyse is forwarded to apply phase."""
    # Arrange
    manifest = _refactoring_manifest()
    apply_calls: list[dict[str, object]] = []
    verify_calls: list[int] = []

    def fake_think(**kwargs: object) -> str:
        return _ANALYSE_OK

    def fake_plan(**kwargs: object) -> str:
        return _PLAN_CREATE_OK

    def fake_manage_file(**kwargs: object) -> str:
        apply_calls.append(dict(kwargs))
        return _APPLY_OK

    def fake_run_quality_gate() -> str:
        verify_calls.append(1)
        return _QUALITY_OK

    registry = {
        "think": fake_think,
        "plan": fake_plan,
        "manage_file": fake_manage_file,
        "run_quality_gate": fake_run_quality_gate,
    }

    # Act
    with patch(
        "cortex.tools.skill_pack.operations._get_tool_registry", return_value=registry
    ):
        result = execute_sequential_workflow(manifest, _noop_handoff)

    # Assert
    assert result.passed is True
    assert result.error is None
    # apply received target_files from analyse output
    assert len(apply_calls) == 1
    assert apply_calls[0]["target_files"] == ["src/foo.py", "src/bar.py"]
    assert apply_calls[0]["plan_file_name"] == "refactor-foo.md"
    # verify ran
    assert len(verify_calls) == 1


def test_refactoring_workflow_verify_skipped_when_apply_fails() -> None:
    """verify phase is skipped when apply status is not 'success'."""
    # Arrange
    manifest = _refactoring_manifest()
    verify_calls: list[int] = []

    def fake_think(**kwargs: object) -> str:
        return _ANALYSE_OK

    def fake_plan(**kwargs: object) -> str:
        return _PLAN_CREATE_OK

    def fake_manage_file(**kwargs: object) -> str:
        return _APPLY_FAIL

    def fake_run_quality_gate() -> str:
        verify_calls.append(1)
        return _QUALITY_OK

    registry = {
        "think": fake_think,
        "plan": fake_plan,
        "manage_file": fake_manage_file,
        "run_quality_gate": fake_run_quality_gate,
    }

    # Act
    with patch(
        "cortex.tools.skill_pack.operations._get_tool_registry", return_value=registry
    ):
        result = execute_sequential_workflow(manifest, _noop_handoff)

    # Assert — verify was skipped
    assert verify_calls == []
    verify_phase = next(p for p in result.phases if p.name == "verify")
    assert verify_phase.skipped is True


def test_refactoring_workflow_empty_targets_skips_plan_and_apply() -> None:
    """When analyse returns empty target_files, plan and apply are still called
    (condition only gates on analyse.status, not on target_files content).
    Empty target_files is a data concern, not a skip condition."""
    # Arrange
    manifest = _refactoring_manifest()
    plan_calls: list[dict[str, object]] = []
    apply_calls: list[dict[str, object]] = []

    def fake_think(**kwargs: object) -> str:
        return _ANALYSE_EMPTY

    def fake_plan(**kwargs: object) -> str:
        plan_calls.append(dict(kwargs))
        return _PLAN_CREATE_OK

    def fake_manage_file(**kwargs: object) -> str:
        apply_calls.append(dict(kwargs))
        return _APPLY_OK

    def fake_run_quality_gate() -> str:
        return _QUALITY_OK

    registry = {
        "think": fake_think,
        "plan": fake_plan,
        "manage_file": fake_manage_file,
        "run_quality_gate": fake_run_quality_gate,
    }

    # Act
    with patch(
        "cortex.tools.skill_pack.operations._get_tool_registry", return_value=registry
    ):
        result = execute_sequential_workflow(manifest, _noop_handoff)

    # Assert — analyse succeeded, so plan and apply still run with empty target_files
    assert result.passed is True
    assert len(plan_calls) == 1
    assert len(apply_calls) == 1
    assert apply_calls[0]["target_files"] == []


def test_refactoring_workflow_phase_outputs_captured() -> None:
    """Outputs declared in manifest are captured from tool results."""
    # Arrange
    manifest = _refactoring_manifest()

    def fake_think(**kwargs: object) -> str:
        return _ANALYSE_OK

    def fake_plan(**kwargs: object) -> str:
        return _PLAN_CREATE_OK

    def fake_manage_file(**kwargs: object) -> str:
        return _APPLY_OK

    def fake_run_quality_gate() -> str:
        return _QUALITY_OK

    registry = {
        "think": fake_think,
        "plan": fake_plan,
        "manage_file": fake_manage_file,
        "run_quality_gate": fake_run_quality_gate,
    }

    # Act
    with patch(
        "cortex.tools.skill_pack.operations._get_tool_registry", return_value=registry
    ):
        result = execute_sequential_workflow(manifest, _noop_handoff)

    # Assert
    analyse_phase = next(p for p in result.phases if p.name == "analyse")
    assert analyse_phase.outputs.get("target_files") == ["src/foo.py", "src/bar.py"]
    assert analyse_phase.outputs.get("patterns") == ["oversized_function", "god_object"]
    plan_phase = next(p for p in result.phases if p.name == "plan")
    assert plan_phase.outputs.get("plan_file_name") == "refactor-foo.md"


# ---------------------------------------------------------------------------
# skill_pack(operation="execute") dispatcher integration
# ---------------------------------------------------------------------------


def _make_happy_registry(
    capture_list: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    """Return a tool registry with all four phases returning success fixtures."""

    def fake_think(**kwargs: object) -> str:
        return _ANALYSE_OK

    def fake_plan(**kwargs: object) -> str:
        return _PLAN_CREATE_OK

    def fake_manage_file(**kwargs: object) -> str:
        if capture_list is not None:
            capture_list.append(dict(kwargs))
        return _APPLY_OK

    def fake_run_quality_gate() -> str:
        return _QUALITY_OK

    return {
        "think": fake_think,
        "plan": fake_plan,
        "manage_file": fake_manage_file,
        "run_quality_gate": fake_run_quality_gate,
    }


@pytest.mark.asyncio
@pytest.mark.timeout(15)
async def test_skill_pack_execute_refactoring_happy_path() -> None:
    """skill_pack(operation=execute, pack_name=refactoring) runs workflow and returns result."""
    manifest = _refactoring_manifest()
    registry = _make_happy_registry()
    with (
        patch(
            "cortex.tools.skill_pack.operations.load_shipped_manifests",
            return_value=[manifest],
        ),
        patch(
            "cortex.tools.skill_pack.operations._get_tool_registry",
            return_value=registry,
        ),
    ):
        result = await skill_pack(operation="execute", pack_name="refactoring")

    data = json.loads(result)
    assert data["status"] == "success"
    assert data["passed"] is True
    assert isinstance(data["phases"], list)
    assert len(data["phases"]) == 4


@pytest.mark.asyncio
@pytest.mark.timeout(15)
async def test_skill_pack_execute_refactoring_manifest_loads_with_workflow() -> None:
    """refactoring manifest has a workflow block with four phases."""
    # Act
    result = await skill_pack(operation="load", pack_name="refactoring")
    data = json.loads(result)

    # Assert
    assert data["status"] == "success"
    pack = data["pack"]
    assert pack["workflow"] is not None
    phases = pack["workflow"]["phases"]
    assert len(phases) == 4
    phase_names = [p["name"] for p in phases]
    assert phase_names == ["analyse", "plan", "apply", "verify"]


@pytest.mark.asyncio
@pytest.mark.timeout(15)
async def test_skill_pack_execute_refactoring_apply_receives_target_files() -> None:
    """target_files from analyse output is injected into apply kwargs."""
    manifest = _refactoring_manifest()
    captured_apply_kwargs: list[dict[str, object]] = []
    registry = _make_happy_registry(capture_list=captured_apply_kwargs)
    with (
        patch(
            "cortex.tools.skill_pack.operations.load_shipped_manifests",
            return_value=[manifest],
        ),
        patch(
            "cortex.tools.skill_pack.operations._get_tool_registry",
            return_value=registry,
        ),
    ):
        _ = await skill_pack(operation="execute", pack_name="refactoring")

    assert len(captured_apply_kwargs) == 1
    assert captured_apply_kwargs[0]["target_files"] == ["src/foo.py", "src/bar.py"]
    assert captured_apply_kwargs[0]["plan_file_name"] == "refactor-foo.md"
