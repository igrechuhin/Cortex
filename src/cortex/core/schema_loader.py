"""Load workflow variant YAML into ``WorkflowSchema`` models."""

from __future__ import annotations

import logging
from collections.abc import Mapping, MutableSequence
from pathlib import Path
from typing import cast

import yaml

from cortex.core.models import WorkflowPhase, WorkflowSchema
from cortex.core.path_resolver import CortexResourceType, get_cortex_path

logger = logging.getLogger(__name__)


class SchemaNotFoundError(LookupError):
    """No workflow schema matches the requested name."""

    def __init__(self, name: str) -> None:
        super().__init__(f"Workflow schema not found: {name}")
        self.schema_name = name


class SchemaInheritanceCycleError(ValueError):
    """Workflow schema ``inherits`` chain contains a cycle."""

    def __init__(self, chain: tuple[str, ...]) -> None:
        joined = " -> ".join(chain)
        super().__init__(f"Cyclic workflow schema inherits: {joined}")
        self.chain = chain


def _bundled_schema_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "resources" / "workflow_schemas"


def bundled_workflow_schema_dir() -> Path:
    """Directory of workflow YAML shipped with the ``cortex`` package."""
    return _bundled_schema_dir()


def _project_schema_file(project_root: Path, name: str) -> Path:
    return get_cortex_path(project_root, CortexResourceType.SCHEMAS) / f"{name}.yaml"


def _read_schema_text(name: str, project_root: Path) -> str:
    project_file = _project_schema_file(project_root, name)
    if project_file.is_file():
        return project_file.read_text(encoding="utf-8")
    bundled = _bundled_schema_dir() / f"{name}.yaml"
    if bundled.is_file():
        return bundled.read_text(encoding="utf-8")
    raise SchemaNotFoundError(name)


def _as_mapping(name: str, data: object) -> dict[str, object]:
    if not isinstance(data, dict):
        msg = f"Workflow schema {name!r} root must be a mapping"
        raise ValueError(msg)
    out: dict[str, object] = {}
    for k, v in cast(dict[str, object], data).items():
        out[k] = v
    return out


def _parse_phases(raw: object) -> list[WorkflowPhase]:
    if not isinstance(raw, list):
        raise ValueError("phases must be a non-null list")
    items = cast(list[object], raw)
    return [WorkflowPhase.model_validate(item) for item in items]


def _merge_phase_lists(
    parent: MutableSequence[WorkflowPhase],
    child: list[WorkflowPhase],
) -> list[WorkflowPhase]:
    result = list(parent)
    for phase in child:
        idx = next((i for i, p in enumerate(result) if p.name == phase.name), None)
        if idx is not None:
            result[idx] = phase
        else:
            result.append(phase)
    return result


def _build_merged_schema(
    raw: dict[str, object],
    merged_phases: list[WorkflowPhase],
) -> WorkflowSchema:
    meta = {k: v for k, v in raw.items() if k != "phases"}
    meta["phases"] = [p.model_dump(mode="python") for p in merged_phases]
    return WorkflowSchema.model_validate(meta)


def load_schema(
    name: str,
    project_root: Path,
    *,
    _resolve_stack: tuple[str, ...] = (),
) -> WorkflowSchema:
    """Load a workflow schema by stem (project ``.cortex/schemas`` first).

    Falls back to workflow YAML shipped under ``cortex/resources/workflow_schemas``.
    When ``inherits`` is set, parent phases are merged; child phases override
    same ``name`` and append unknown names.
    """
    if name in _resolve_stack:
        raise SchemaInheritanceCycleError(_resolve_stack + (name,))
    text = _read_schema_text(name, project_root)
    parsed: object = yaml.safe_load(text)
    raw = _as_mapping(name, parsed)
    if "phases" not in raw:
        msg = f"Workflow schema {name!r} missing phases"
        raise ValueError(msg)
    child_phases = _parse_phases(raw["phases"])
    inherits = raw.get("inherits")
    if inherits is None:
        return WorkflowSchema.model_validate(raw)
    if not isinstance(inherits, str):
        raise ValueError("inherits must be a string schema name when set")
    parent = load_schema(
        inherits, project_root, _resolve_stack=_resolve_stack + (name,)
    )
    merged = _merge_phase_lists(parent.phases, child_phases)
    return _build_merged_schema(raw, merged)


def evaluate_workflow_condition(
    expression: str | None,
    session_state: Mapping[str, object] | None,
) -> bool:
    """Evaluate a phase ``condition`` against ``session_state`` (``session_config``).

    Invalid expressions evaluate to False so optional phases are skipped.
    """
    if expression is None:
        return True
    trimmed = expression.strip()
    if trimmed == "":
        return True
    ns: dict[str, object] = {"session_config": dict(session_state or {})}
    try:
        out: object = eval(trimmed, {"__builtins__": {}}, ns)
    except Exception:
        logger.debug("workflow condition eval failed for %r", trimmed, exc_info=True)
        return False
    return bool(out)
