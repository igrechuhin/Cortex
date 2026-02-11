"""Tests for tool search operations (Phase 49 Step 5)."""

from __future__ import annotations

import json

import pytest

from cortex.tools.tool_search_operations import search_tools


@pytest.mark.asyncio
@pytest.mark.timeout(5)
async def test_search_tools_returns_valid_json() -> None:
    """search_tools returns JSON with status, query, count, tools."""
    result = await search_tools(query="refactor", limit=5)
    data = json.loads(result)
    assert data["status"] == "success"
    assert data["query"] == "refactor"
    assert "count" in data
    assert "tools" in data
    assert isinstance(data["tools"], list)
    for t in data["tools"]:
        assert "name" in t
        assert "category" in t
        assert "rationale" in t


@pytest.mark.asyncio
@pytest.mark.timeout(5)
async def test_search_tools_empty_query() -> None:
    """search_tools with empty-like query returns zero matches."""
    result = await search_tools(query="", limit=10)
    data = json.loads(result)
    assert data["status"] == "success"
    assert data["count"] == 0
    assert data["tools"] == []


@pytest.mark.asyncio
@pytest.mark.timeout(5)
async def test_search_tools_category_filter() -> None:
    """search_tools with category returns only that category."""
    result = await search_tools(query="tool", category="deferred_low", limit=20)
    data = json.loads(result)
    assert data["status"] == "success"
    for t in data["tools"]:
        assert t["category"] == "deferred_low"


@pytest.mark.asyncio
@pytest.mark.timeout(5)
async def test_search_tools_limit_clamped() -> None:
    """search_tools clamps limit to 1-50."""
    result = await search_tools(query="a", limit=0)
    data = json.loads(result)
    assert data["status"] == "success"
    assert len(data["tools"]) <= 1
    result2 = await search_tools(query="a", limit=100)
    data2 = json.loads(result2)
    assert len(data2["tools"]) <= 50
