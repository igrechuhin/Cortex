"""Unit tests for workflow schema Pydantic models."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from cortex.core.models import WorkflowPhase, WorkflowSchema

_REPO_ROOT = Path(__file__).resolve().parents[2]
_BUILTIN_SCHEMA_DIR = _REPO_ROOT / ".cortex" / "schemas"


def test_workflow_phase_minimal() -> None:
    phase = WorkflowPhase(name="plan", tool="/cortex/plan", required=True)
    assert phase.condition is None
    assert phase.config == {}


def test_workflow_phase_with_optional_fields() -> None:
    phase = WorkflowPhase(
        name="eda",
        tool="/cortex/do",
        required=False,
        condition="session_config.get('eda_required', False)",
        config={"mode": "explore"},
    )
    assert phase.config["mode"] == "explore"


def test_workflow_schema_round_trip() -> None:
    schema = WorkflowSchema(
        name="fast-path",
        description="plan → implement → commit",
        phases=[
            WorkflowPhase(name="plan", tool="/cortex/plan", required=True),
            WorkflowPhase(name="commit", tool="/cortex/commit", required=True),
        ],
        inherits=None,
    )
    dumped = schema.model_dump(mode="python")
    restored = WorkflowSchema.model_validate(dumped)
    assert restored.name == "fast-path"
    assert len(restored.phases) == 2


def test_workflow_schema_forbids_extra_keys() -> None:
    with pytest.raises(ValidationError):
        _ = WorkflowSchema.model_validate(
            {
                "name": "x",
                "description": "d",
                "phases": [],
                "unknown": True,
            }
        )


def test_workflow_phase_forbids_extra_keys() -> None:
    with pytest.raises(ValidationError):
        _ = WorkflowPhase.model_validate(
            {
                "name": "plan",
                "tool": "/cortex/plan",
                "required": True,
                "extra": 1,
            }
        )


@pytest.mark.parametrize(
    "stem",
    ("default", "fast-path", "compliance", "data-science"),
)
def test_builtin_workflow_yaml_parses_to_model(stem: str) -> None:
    # AI: YAML fixtures live under .cortex/schemas/ per plan Step 2; loader (Step 3) will resolve paths later.
    path = _BUILTIN_SCHEMA_DIR / f"{stem}.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    schema = WorkflowSchema.model_validate(raw)
    assert schema.name == stem
    assert schema.phases
    for phase in schema.phases:
        assert phase.name
        assert phase.tool.startswith("/cortex/")
