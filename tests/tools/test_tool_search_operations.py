"""Tests for tool search operations (Phase 49 Step 5–6)."""

from __future__ import annotations

import json

import pytest

from cortex.tools.structure.categories import (
    build_category_config,
    get_always_loaded_tool_names,
    get_deferred_tool_names,
    get_tool_category,
)
from cortex.tools.structure.tool_search import list_available_tools, search_tools


@pytest.mark.asyncio
@pytest.mark.timeout(15)
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
@pytest.mark.timeout(15)
async def test_search_tools_empty_query() -> None:
    """search_tools with empty-like query returns zero matches."""
    result = await search_tools(query="", limit=10)
    data = json.loads(result)
    assert data["status"] == "success"
    assert data["count"] == 0
    assert data["tools"] == []


@pytest.mark.asyncio
@pytest.mark.timeout(15)
async def test_search_tools_category_filter() -> None:
    """search_tools with category returns only that category."""
    result = await search_tools(query="tool", category="deferred_medium", limit=20)
    data = json.loads(result)
    assert data["status"] == "success"
    for t in data["tools"]:
        assert t["category"] == "deferred_medium"


@pytest.mark.asyncio
@pytest.mark.timeout(15)
async def test_search_tools_limit_clamped() -> None:
    """search_tools clamps limit to 1-50."""
    result = await search_tools(query="a", limit=0)
    data = json.loads(result)
    assert data["status"] == "success"
    assert len(data["tools"]) <= 1
    result2 = await search_tools(query="a", limit=100)
    data2 = json.loads(result2)
    assert len(data2["tools"]) <= 50


# ---------------------------------------------------------------------------
# Phase 49 Step 6: Token savings and tool discovery
# ---------------------------------------------------------------------------


def test_tool_search_token_savings_potential() -> None:
    """When tool_search is enabled, always_loaded count is less than total tools.

    Documents token savings: initial list size = always_loaded only; deferred
    tools are discovered via search_tools. When MCP supports defer_loading,
    this ratio implies expected token reduction.
    """
    config = build_category_config()
    always = len(config.always_loaded)
    deferred = len(config.deferred_medium) + len(config.deferred_low)
    total = always + deferred
    assert always < total, "always_loaded must be a subset to achieve token savings"
    assert always >= 7, "enough core tools for session start and quality gates"
    assert deferred >= 2, "enough deferred tools for on-demand discovery"


@pytest.mark.asyncio
@pytest.mark.timeout(15)
async def test_tool_search_discovery_returns_only_deferred_tools() -> None:
    """search_tools returns only tools from deferred_medium and deferred_low."""
    always = set(get_always_loaded_tool_names())
    deferred = set(get_deferred_tool_names())
    assert always.isdisjoint(deferred), "no tool may be in both always and deferred"
    result = await search_tools(query="refactor", limit=10)
    data = json.loads(result)
    assert data["status"] == "success"
    returned_names = {t["name"] for t in data["tools"]}
    assert returned_names <= deferred, "search_tools must return only deferred tools"
    assert returned_names.isdisjoint(
        always
    ), "search_tools must not return always_loaded"


def test_search_tools_was_removed() -> None:
    """search_tools was removed from registration (2026-03-18)."""
    assert get_tool_category("search_tools") is None


# ---------------------------------------------------------------------------
# list_available_tools (agent-skills Step 3)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.timeout(15)
async def test_list_available_tools_all_returns_by_category() -> None:
    """list_available_tools() with no category returns by_category and summary."""
    result = await list_available_tools(category=None)
    data = json.loads(result)
    assert data["status"] == "success"
    assert "by_category" in data
    assert "summary" in data
    assert "always_loaded" in data["by_category"]
    assert "deferred_medium" in data["by_category"]
    assert "deferred_low" in data["by_category"]


@pytest.mark.asyncio
@pytest.mark.timeout(15)
async def test_list_available_tools_filter_returns_tools() -> None:
    """list_available_tools(category=always_loaded) returns list of tools."""
    result = await list_available_tools(category="always_loaded")
    data = json.loads(result)
    assert data["status"] == "success"
    assert data["category"] == "always_loaded"
    assert "tools" in data
    assert "manage_file" in [t["name"] for t in data["tools"]]


@pytest.mark.asyncio
@pytest.mark.timeout(15)
async def test_list_available_tools_invalid_category_returns_error() -> None:
    """list_available_tools(invalid) returns error."""
    result = await list_available_tools(category="invalid_tier")
    data = json.loads(result)
    assert data["status"] == "error"
    assert "error" in data


def test_list_available_tools_internalized_not_in_tool_categories() -> None:
    """list_available_tools was internalized (2026-02-26); use search_tools for discovery."""
    assert get_tool_category("list_available_tools") is None
