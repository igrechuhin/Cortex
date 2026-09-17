"""Context graph previews stay bounded while detailed graph reads stay complete."""

from __future__ import annotations

import json
import statistics
import time
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from tiktoken.registry import get_encoding

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.token_counter import TokenCounter
from cortex.tools.optimization.context_budget import enforce_context_budget
from cortex.tools.optimization.handlers_format import (
    inject_plan_graph_into_context_result,
)
from cortex.tools.plans.plan_graph import plan_graph_json


def _write_plan(path: Path, dependencies: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(
        "---\nstatus: PENDING\ndepends_on: "
        + json.dumps(dependencies)
        + "\n---\n\n## Goal\n\nGraph preview fixture.\n",
        encoding="utf-8",
    )


@pytest.fixture
def graph_heavy_project(tmp_path: Path) -> Path:
    """Use reverse creation order and hundreds of real plans, not mocked graphs."""
    plans = get_cortex_path(tmp_path, CortexResourceType.PLANS)
    ready = [f"ready-{index:03}" for index in range(100)]
    for slug in reversed(ready):
        _write_plan(plans / f"{slug}.md", [])
    for index in reversed(range(100)):
        _write_plan(plans / f"blocked-{index:03}.md", list(reversed(ready)))
    for index in reversed(range(12)):
        slug = f"duplicate-{index:03}"
        _write_plan(plans / f"{slug}.md", [])
        for duplicate in reversed(range(12)):
            _write_plan(plans / "archive" / f"copy-{duplicate:03}" / f"{slug}.md", [])
    return tmp_path


def test_context_graph_bounds_details_and_preserves_totals(
    graph_heavy_project: Path,
) -> None:
    # Arrange
    base = json.dumps({"status": "success"})
    ready = [f"ready-{index:03}" for index in range(10)]
    blocked = [f"blocked-{index:03}" for index in range(10)]
    ambiguous = [f"duplicate-{index:03}" for index in range(10)]
    # Act
    result = inject_plan_graph_into_context_result(base, graph_heavy_project)
    data = json.loads(result)
    repeated = inject_plan_graph_into_context_result(base, graph_heavy_project)
    # Assert
    assert result == repeated
    assert data["plan_graph_ready"] == ready
    assert list(data["plan_graph_blocked"]) == blocked
    assert all(values == ready for values in data["plan_graph_blocked"].values())
    assert list(data["plan_graph_ambiguous"]) == ambiguous
    for slug, paths in data["plan_graph_ambiguous"].items():
        assert paths == [f"archive/copy-{i:03}/{slug}.md" for i in range(10)]
    assert "100 plans READY, 100 plans BLOCKED" in data["plan_graph_summary"]
    assert "10000 outstanding dependency" in data["plan_graph_summary"]
    assert "12 ambiguous plan identity" in data["plan_graph_summary"]
    assert data["plan_graph_details"] == {
        "limit": 10,
        "ready_omitted": 90,
        "blocked_omitted": 90,
        "ambiguous_omitted": 2,
        "blocked_dependencies_omitted": 9900,
        "ambiguous_paths_omitted": 56,
        "full_details": {"tool": "plan", "operation": "graph", "include_archive": True},
    }


@pytest.mark.asyncio
async def test_full_graph_retains_details_omitted_from_context(
    graph_heavy_project: Path,
) -> None:
    # Arrange
    ready = [f"ready-{index:03}" for index in range(100)]
    # Act
    with patch(
        "cortex.tools.plans.plan_graph.get_or_resolve_project_root",
        new_callable=AsyncMock,
        return_value=str(graph_heavy_project),
    ):
        data = json.loads(await plan_graph_json(None, include_archive=True))
    # Assert
    assert data["ready"] == ready
    assert list(data["blocked"]) == [f"blocked-{i:03}" for i in range(100)]
    assert all(values == ready for values in data["blocked"].values())
    assert list(data["ambiguous"]) == [f"duplicate-{i:03}" for i in range(12)]
    for slug, paths in data["ambiguous"].items():
        assert paths == [
            *(f"archive/copy-{i:03}/{slug}.md" for i in range(12)),
            f"{slug}.md",
        ]


@pytest.mark.slow
def test_graph_heavy_budgeted_assembly_latency(graph_heavy_project: Path) -> None:
    # Arrange: real encoding and hundreds of plans, with no resource cache shortcut.
    counter = TokenCounter()
    counter.encoding_impl = get_encoding("cl100k_base")
    base = json.dumps(
        {
            "status": "success",
            "session_scope": "Keep governance.",
            "layered_context": "Essential",
            "context_layers_loaded": ["L0"],
        }
    )
    samples: list[float] = []
    for iteration in range(8):
        start = time.perf_counter()
        graph = inject_plan_graph_into_context_result(base, graph_heavy_project)
        serialized = enforce_context_budget(graph, 10000, "Essential", ["L0"], counter)
        elapsed = time.perf_counter() - start
        if iteration:
            samples.append(elapsed)
        result = json.loads(serialized)
        assert result["status"] == "success", result
        assert result["total_tokens"] == counter.count_tokens(serialized) <= 10000
        assert result["session_scope"] == "Keep governance."
    # Assert: retain the documented warm context median/p95 envelope.
    assert statistics.median(samples) < 0.1, samples
    assert max(samples) < 0.25, samples
