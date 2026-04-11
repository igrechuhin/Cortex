"""manage_file operations for workflow schema discovery and forking."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import yaml

from cortex.core.schema_loader import (
    SchemaNotFoundError,
    bundled_workflow_schema_dir,
    load_schema,
)
from cortex.tools.files.operation_helpers import FileOperation
from cortex.tools.files.workflow_schema_fork import fork_workflow_schema
from cortex.tools.files.workflow_schema_paths import project_schema_dir
from cortex.tools.response_builder import error_response

logger = logging.getLogger(__name__)


def _schema_yaml_stems(directory: Path) -> set[str]:
    if not directory.is_dir():
        return set()
    out: set[str] = set()
    for path in directory.glob("*.yaml"):
        if path.is_file():
            out.add(path.stem)
    for path in directory.glob("*.yml"):
        if path.is_file():
            out.add(path.stem)
    return out


def list_workflow_schemas(project_root: Path) -> str:
    """Return JSON listing built-in and project workflow schemas."""
    bundled = bundled_workflow_schema_dir()
    proj = project_schema_dir(project_root)
    names = sorted(_schema_yaml_stems(bundled) | _schema_yaml_stems(proj))
    items: list[dict[str, str]] = []
    for name in names:
        try:
            schema = load_schema(name, project_root)
        except (SchemaNotFoundError, ValueError, yaml.YAMLError, OSError) as e:
            logger.debug("skip schema %s: %s", name, e)
            continue
        proj_file = proj / f"{name}.yaml"
        source = "project" if proj_file.is_file() else "bundled"
        items.append(
            {
                "name": schema.name,
                "description": schema.description,
                "source": source,
            }
        )
    return json.dumps(
        {"status": "success", "schemas": items, "count": len(items)}, indent=2
    )


async def execute_workflow_schema_operation(
    project_root: Path,
    operation: FileOperation,
    content: str | None,
) -> str:
    """Run list_schemas or fork_schema."""
    if operation == FileOperation.LIST_SCHEMAS:
        return list_workflow_schemas(project_root)
    if operation == FileOperation.FORK_SCHEMA:
        return fork_workflow_schema(project_root, content)
    return json.dumps(
        error_response(
            error=f"Unsupported schema operation: {operation}", error_type="ValueError"
        ),
        indent=2,
    )
