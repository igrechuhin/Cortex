"""Tests for skill pack operations (skill_pack tool: operation=discover|load)."""

from __future__ import annotations

import json
from typing import cast

import pytest

from cortex.tools.skill_pack.operations import skill_pack
from cortex.tools.structure.categories import get_tool_category


@pytest.mark.asyncio
@pytest.mark.timeout(5)
async def test_skill_pack_discover_returns_valid_json() -> None:
    """skill_pack(operation=discover) returns JSON with status, task_description, count, packs."""
    result = await skill_pack(
        operation="discover", task_description="implement feature", limit=5
    )
    data = json.loads(result)
    assert isinstance(data, dict)
    assert data["status"] == "success"
    assert data["task_description"] == "implement feature"
    assert "count" in data
    assert "packs" in data
    packs = cast(list[dict[str, object]], data["packs"])
    assert isinstance(packs, list)
    for p in packs:
        assert isinstance(p, dict)
        assert "name" in p and "description" in p and "reason" in p


@pytest.mark.asyncio
@pytest.mark.timeout(5)
async def test_skill_pack_discover_recommends_core_for_session() -> None:
    """skill_pack(operation=discover) recommends core pack for session/orientation tasks."""
    result = await skill_pack(
        operation="discover",
        task_description="session start and load context",
        limit=5,
    )
    data = json.loads(result)
    assert data["status"] == "success"
    names = [p["name"] for p in data["packs"]]
    assert "core" in names


@pytest.mark.asyncio
@pytest.mark.timeout(5)
async def test_skill_pack_discover_recommends_quality_for_lint() -> None:
    """skill_pack(operation=discover) recommends quality pack for lint/quality tasks."""
    result = await skill_pack(
        operation="discover",
        task_description="fix lint and run pre-commit quality",
        limit=5,
    )
    data = json.loads(result)
    assert data["status"] == "success"
    names = [p["name"] for p in data["packs"]]
    assert "quality" in names


@pytest.mark.asyncio
@pytest.mark.timeout(5)
async def test_skill_pack_discover_limit_clamped() -> None:
    """skill_pack(operation=discover) clamps limit to 1-10."""
    result = await skill_pack(
        operation="discover", task_description="implement", limit=0
    )
    data = json.loads(result)
    assert data["status"] == "success"
    assert len(data["packs"]) <= 1
    result2 = await skill_pack(
        operation="discover", task_description="implement", limit=100
    )
    data2 = json.loads(result2)
    assert len(data2["packs"]) <= 10


@pytest.mark.asyncio
@pytest.mark.timeout(5)
async def test_skill_pack_load_core_returns_manifest() -> None:
    """skill_pack(operation=load, pack_name=core) returns full manifest."""
    result = await skill_pack(operation="load", pack_name="core")
    data = json.loads(result)
    assert data["status"] == "success"
    pack = data["pack"]
    assert pack["name"] == "core"
    assert "session" in pack["tools"]
    assert "load_context" in pack["tools"]
    assert "workflow_sequences" in pack
    assert "example_invocations" in pack


@pytest.mark.asyncio
@pytest.mark.timeout(5)
async def test_skill_pack_load_quality_returns_manifest() -> None:
    """skill_pack(operation=load, pack_name=quality) returns manifest with execute_pre_commit_checks."""
    result = await skill_pack(operation="load", pack_name="quality")
    data = json.loads(result)
    assert data["status"] == "success"
    pack = data["pack"]
    assert pack["name"] == "quality"
    assert "execute_pre_commit_checks" in pack["tools"]


@pytest.mark.asyncio
@pytest.mark.timeout(5)
async def test_skill_pack_load_case_insensitive() -> None:
    """skill_pack(operation=load) accepts pack name case-insensitively."""
    result = await skill_pack(operation="load", pack_name="CORE")
    data = json.loads(result)
    assert data["status"] == "success"
    assert data["pack"]["name"] == "core"


@pytest.mark.asyncio
@pytest.mark.timeout(5)
async def test_skill_pack_load_not_found_returns_error() -> None:
    """skill_pack(operation=load) with unknown name returns error and lists available."""
    result = await skill_pack(operation="load", pack_name="nonexistent_pack_xyz")
    data = json.loads(result)
    assert data["status"] == "error"
    assert "not found" in data["error"].lower()
    assert "available" in data
    assert isinstance(data["available"], list)
    assert "core" in data["available"]


def test_skill_pack_internalized_not_in_tool_categories() -> None:
    """skill_pack was internalized (2026-02-26); no longer in TOOL_CATEGORIES."""
    assert get_tool_category("skill_pack") is None
