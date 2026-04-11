"""Unit tests for workflow schema loading and condition evaluation."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
import yaml

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.schema_loader import (
    SchemaInheritanceCycleError,
    SchemaNotFoundError,
    evaluate_workflow_condition,
    load_schema,
)


def _schemas_dir(tmp_path: Path) -> Path:
    schemas = get_cortex_path(tmp_path, CortexResourceType.SCHEMAS)
    _ = schemas.mkdir(parents=True)
    return schemas


def _write_schema_yaml(path: Path, data: dict[str, object]) -> None:
    _ = path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def test_load_schema_prefers_project_over_bundled(tmp_path: Path) -> None:
    schemas = _schemas_dir(tmp_path)
    custom: dict[str, object] = {
        "name": "default",
        "description": "project-local override",
        "phases": [
            {"name": "plan", "tool": "/cortex/plan", "required": True},
        ],
    }
    _write_schema_yaml(schemas / "default.yaml", custom)
    schema = load_schema("default", tmp_path)
    assert schema.description == "project-local override"
    assert len(schema.phases) == 1


def test_load_schema_bundled_fallback(tmp_path: Path) -> None:
    cortex = tmp_path / ".cortex"
    _ = cortex.mkdir()
    schema = load_schema("fast-path", tmp_path)
    assert schema.name == "fast-path"
    assert {p.name for p in schema.phases} == {"plan", "implement", "commit"}


def test_load_schema_not_found(tmp_path: Path) -> None:
    with pytest.raises(SchemaNotFoundError):
        _ = load_schema("no-such-workflow-xyz", tmp_path)


def _inherit_merge_base() -> dict[str, object]:
    return {
        "name": "base-wf",
        "description": "base",
        "phases": [
            {"name": "plan", "tool": "/cortex/plan", "required": True},
            {"name": "commit", "tool": "/cortex/commit", "required": True},
        ],
    }


def _inherit_merge_child() -> dict[str, object]:
    return {
        "name": "child-wf",
        "description": "child",
        "inherits": "base-wf",
        "phases": [
            {"name": "plan", "tool": "/cortex/plan", "required": False},
            {"name": "implement", "tool": "/cortex/do", "required": True},
        ],
    }


def test_load_schema_inherits_merge(tmp_path: Path) -> None:
    schemas = _schemas_dir(tmp_path)
    _write_schema_yaml(schemas / "base-wf.yaml", _inherit_merge_base())
    _write_schema_yaml(schemas / "child-wf.yaml", _inherit_merge_child())
    merged = load_schema("child-wf", tmp_path)
    assert merged.name == "child-wf"
    by_name = {p.name: p for p in merged.phases}
    assert by_name["plan"].required is False
    assert "implement" in by_name
    assert by_name["commit"].required is True


def test_load_schema_inherits_cycle(tmp_path: Path) -> None:
    schemas = _schemas_dir(tmp_path)
    empty_phases = cast(list[object], [])
    a: dict[str, object] = {
        "name": "a",
        "description": "a",
        "inherits": "b",
        "phases": empty_phases,
    }
    b: dict[str, object] = {
        "name": "b",
        "description": "b",
        "inherits": "a",
        "phases": empty_phases,
    }
    _write_schema_yaml(schemas / "a.yaml", a)
    _write_schema_yaml(schemas / "b.yaml", b)
    with pytest.raises(SchemaInheritanceCycleError):
        _ = load_schema("a", tmp_path)


def test_evaluate_workflow_condition_true_false() -> None:
    assert evaluate_workflow_condition(None, {}) is True
    assert evaluate_workflow_condition("", {}) is True
    assert (
        evaluate_workflow_condition("session_config.get('x', False)", {"x": True})
        is True
    )
    assert (
        evaluate_workflow_condition("session_config.get('x', False)", {"x": False})
        is False
    )


def test_evaluate_workflow_condition_invalid_expression() -> None:
    assert evaluate_workflow_condition("session_config[undefined_name]", {}) is False


def test_load_schema_inherits_appends_new_phase(tmp_path: Path) -> None:
    schemas = _schemas_dir(tmp_path)
    base: dict[str, object] = {
        "name": "base-append",
        "description": "base",
        "phases": [
            {"name": "plan", "tool": "/cortex/plan", "required": True},
        ],
    }
    child: dict[str, object] = {
        "name": "child-append",
        "description": "child",
        "inherits": "base-append",
        "phases": [
            {"name": "review", "tool": "/cortex/review", "required": True},
        ],
    }
    _write_schema_yaml(schemas / "base-append.yaml", base)
    _write_schema_yaml(schemas / "child-append.yaml", child)
    merged = load_schema("child-append", tmp_path)
    assert [p.name for p in merged.phases] == ["plan", "review"]
