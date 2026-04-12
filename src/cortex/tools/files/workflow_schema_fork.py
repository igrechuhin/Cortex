"""Fork workflow YAML into ``.cortex/schemas`` (split from list ops for size limits)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import yaml

from cortex.core.models import OperationStatus
from cortex.core.project_session_config import validate_schema_fork_name
from cortex.tools.files.workflow_schema_paths import (
    fork_schema_source_file,
    project_schema_dir,
)
from cortex.tools.response_builder import error_response


def _err_json(msg: str, err_type: str = "ValueError") -> str:
    return json.dumps(error_response(error=msg, error_type=err_type), indent=2)


def parse_fork_schema_request(content: str | None) -> str | tuple[str, str]:
    """Return error JSON or ``(base, new_name)``."""
    if content is None or not str(content).strip():
        return _err_json(
            "content is required for fork_schema (JSON with base, new_name)",
        )
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as e:
        return _err_json(f"Invalid JSON: {e}")
    if not isinstance(payload, dict):
        return _err_json("content must be a JSON object")
    data = cast(dict[str, object], payload)
    base_raw, new_raw = data.get("base"), data.get("new_name")
    if not isinstance(base_raw, str) or not isinstance(new_raw, str):
        return _err_json("base and new_name must be non-empty strings")
    base, new_name = base_raw.strip(), new_raw.strip().lower()
    if not base:
        return _err_json("base must be non-empty")
    if (name_err := validate_schema_fork_name(new_name)) is not None:
        return _err_json(name_err)
    if new_name == base:
        return _err_json("new_name must differ from base")
    return (base, new_name)


def write_forked_schema_file(project_root: Path, base: str, new_name: str) -> str:
    """Copy resolved base YAML to project schemas with updated ``name`` field."""
    src = fork_schema_source_file(project_root, base)
    if src is None:
        return _err_json(f"Unknown base schema: {base!r}", "SchemaNotFoundError")
    dest_dir = project_schema_dir(project_root)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{new_name}.yaml"
    if dest.exists():
        return _err_json(
            f"Schema file already exists: {dest.relative_to(project_root)}",
            "FileExistsError",
        )
    updated = rewrite_forked_yaml_name(src.read_text(encoding="utf-8"), new_name)
    try:
        _ = dest.write_text(updated, encoding="utf-8")
    except OSError as e:
        return _err_json(str(e), type(e).__name__)
    rel = dest.relative_to(project_root)
    return json.dumps(
        {
            "status": OperationStatus.SUCCESS.value,
            "path": str(rel),
            "base": base,
            "new_name": new_name,
        },
        indent=2,
    )


def rewrite_forked_yaml_name(yaml_text: str, new_stem: str) -> str:
    """Set ``name:`` in YAML text to ``new_stem`` when a root mapping is detected."""
    try:
        parsed: object = yaml.safe_load(yaml_text)
    except yaml.YAMLError:
        return yaml_text
    if not isinstance(parsed, dict):
        return yaml_text
    mapping = cast(dict[str, object], parsed)
    if "name" in mapping:
        mapping["name"] = new_stem
    try:
        return yaml.safe_dump(
            mapping,
            sort_keys=False,
            default_flow_style=False,
            allow_unicode=True,
        )
    except yaml.YAMLError:
        return yaml_text


def fork_workflow_schema(project_root: Path, content: str | None) -> str:
    """Copy base workflow YAML to ``.cortex/schemas/<new_name>.yaml``."""
    parsed = parse_fork_schema_request(content)
    if isinstance(parsed, str):
        return parsed
    base, new_name = parsed
    return write_forked_schema_file(project_root, base, new_name)
