"""Tests for workflow operations (run_composite_workflow suggest_workflow)."""

from __future__ import annotations

import json

import pytest

from cortex.tools.categories import ToolCategory, get_tool_category
from cortex.tools.composite_tools import run_composite_workflow


@pytest.mark.asyncio
@pytest.mark.timeout(5)
async def test_suggest_workflow_returns_valid_json() -> None:
    """run_composite_workflow suggest_workflow returns JSON with status, task_description, count, workflows."""
    result = await run_composite_workflow(
        operation="suggest_workflow",
        task_description="implement new feature",
        limit=3,
    )
    data = json.loads(result)
    assert data["status"] == "success"
    assert "count" in data
    assert "workflows" in data
    assert isinstance(data["workflows"], list)
    for w in data["workflows"]:
        assert "name" in w
        assert "description" in w
        assert "steps" in w


@pytest.mark.asyncio
@pytest.mark.timeout(5)
async def test_suggest_workflow_recommends_feature_workflow() -> None:
    """run_composite_workflow suggest_workflow recommends new_feature_development for implement tasks."""
    result = await run_composite_workflow(
        operation="suggest_workflow",
        task_description="implement API endpoint",
        limit=5,
    )
    data = json.loads(result)
    assert data["status"] == "success"
    names = [w["name"] for w in data["workflows"]]
    assert "new_feature_development" in names


@pytest.mark.asyncio
@pytest.mark.timeout(5)
async def test_suggest_workflow_recommends_bug_workflow() -> None:
    """run_composite_workflow suggest_workflow recommends bug_investigation for debug/fix tasks."""
    result = await run_composite_workflow(
        operation="suggest_workflow",
        task_description="fix failing test and debug error",
        limit=5,
    )
    data = json.loads(result)
    assert data["status"] == "success"
    names = [w["name"] for w in data["workflows"]]
    assert "bug_investigation" in names


@pytest.mark.asyncio
@pytest.mark.timeout(5)
async def test_suggest_workflow_limit_clamped() -> None:
    """run_composite_workflow suggest_workflow clamps limit to 1-10."""
    result = await run_composite_workflow(
        operation="suggest_workflow",
        task_description="implement",
        limit=0,
    )
    data = json.loads(result)
    assert data["status"] == "success"
    assert len(data["workflows"]) <= 1
    result2 = await run_composite_workflow(
        operation="suggest_workflow",
        task_description="implement",
        limit=100,
    )
    data2 = json.loads(result2)
    assert len(data2["workflows"]) <= 10


def test_run_composite_workflow_is_deferred_medium() -> None:
    """run_composite_workflow is catalogued as deferred_medium."""
    assert get_tool_category("run_composite_workflow") == ToolCategory.DEFERRED_MEDIUM
