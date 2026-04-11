"""Tests for manage_file workflow schema helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.files.manage_file_helpers import execute_file_operation
from cortex.tools.files.operation_helpers import FileOperation


@pytest.mark.asyncio
async def test_list_workflow_schemas_json(tmp_path: Path) -> None:
    raw = await execute_file_operation(
        tmp_path,
        "_workflow_schemas",
        FileOperation.LIST_SCHEMAS,
        None,
        False,
        None,
        None,
        None,
    )
    result = json.loads(raw)
    assert result["status"] == "success"
    names = {item["name"] for item in result["schemas"]}
    assert "default" in names
    assert "fast-path" in names


@pytest.mark.asyncio
async def test_fork_schema_copies_bundled(tmp_path: Path) -> None:
    content = json.dumps({"base": "fast-path", "new_name": "forked-fast"})
    raw = await execute_file_operation(
        tmp_path,
        "_workflow_schemas",
        FileOperation.FORK_SCHEMA,
        content,
        False,
        None,
        None,
        None,
    )
    result = json.loads(raw)
    assert result["status"] == "success"
    dest = get_cortex_path(tmp_path, CortexResourceType.SCHEMAS) / "forked-fast.yaml"
    assert dest.is_file()
    data = yaml.safe_load(dest.read_text(encoding="utf-8"))
    assert data["name"] == "forked-fast"


@pytest.mark.asyncio
async def test_fork_schema_rejects_duplicate(tmp_path: Path) -> None:
    schemas = get_cortex_path(tmp_path, CortexResourceType.SCHEMAS)
    schemas.mkdir(parents=True)
    _ = (schemas / "x.yaml").write_text("name: x\ndescription: d\nphases: []\n")
    raw = await execute_file_operation(
        tmp_path,
        "_workflow_schemas",
        FileOperation.FORK_SCHEMA,
        json.dumps({"base": "default", "new_name": "x"}),
        False,
        None,
        None,
        None,
    )
    result = json.loads(raw)
    assert result["status"] == "error"
