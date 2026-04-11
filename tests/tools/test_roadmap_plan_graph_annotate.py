"""Tests for roadmap read-time plan dependency annotations."""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, patch

import pytest

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.optimization.handlers import build_context_resource_payload_async
from cortex.tools.optimization.handlers_format import (
    inject_plan_graph_into_context_result,
)
from cortex.tools.plans.plan_graph import build_plan_graph_surface_bundle
from cortex.tools.plans.roadmap_plan_graph_annotate import annotate_roadmap_for_project

_CONTEXT_BASE_JSON = json.dumps(
    {
        "status": "success",
        "task_description": "t",
        "token_budget": 1000,
        "strategy": "dependency_aware",
        "total_tokens": 0,
        "utilization": 0.0,
        "selected_files": {},
    }
)


def _passthrough_payload(payload: object, *_args: object) -> object:
    return payload


def _passthrough_single(payload: object) -> object:
    return payload


async def _async_passthrough_payload(payload: object, *_args: object) -> object:
    return payload


def _register_context_goals_and_scope(stack: ExitStack) -> None:
    _ = stack.enter_context(
        patch(
            "cortex.tools.optimization.handlers.append_session_goal_to_context_payload",
            side_effect=_passthrough_payload,
        )
    )
    _ = stack.enter_context(
        patch(
            "cortex.tools.optimization.handlers._append_session_scope_to_context_payload",
            side_effect=_passthrough_single,
        )
    )


def _register_context_scoped_and_sources(stack: ExitStack) -> None:
    _ = stack.enter_context(
        patch(
            "cortex.tools.optimization.handlers._append_scoped_context_to_payload",
            new_callable=AsyncMock,
            side_effect=_async_passthrough_payload,
        )
    )
    _ = stack.enter_context(
        patch(
            "cortex.tools.optimization.handlers._append_recent_ingested_sources_to_context_payload",
            side_effect=_passthrough_payload,
        )
    )


def _register_context_summaries_ops_artifacts(stack: ExitStack) -> None:
    _ = stack.enter_context(
        patch(
            "cortex.tools.optimization.handlers._append_explore_summary_to_context_payload",
            side_effect=_passthrough_payload,
        )
    )
    _ = stack.enter_context(
        patch(
            "cortex.tools.optimization.handlers._append_recent_operations_to_context_payload",
            side_effect=_passthrough_payload,
        )
    )
    _ = stack.enter_context(
        patch(
            "cortex.tools.optimization.handlers._append_recent_artifacts_to_context_payload",
            side_effect=_passthrough_payload,
        )
    )


def _register_context_read_stubs(stack: ExitStack) -> None:
    _ = stack.enter_context(
        patch(
            "cortex.tools.optimization.handlers._read_recent_operations_lines",
            return_value=[],
        )
    )
    _ = stack.enter_context(
        patch(
            "cortex.tools.optimization.handlers._read_recent_artifacts_markdown",
            return_value="",
        )
    )
    _ = stack.enter_context(
        patch(
            "cortex.tools.optimization.handlers._read_recent_ingested_sources_markdown",
            return_value="",
        )
    )
    _ = stack.enter_context(
        patch(
            "cortex.tools.optimization.handlers._read_explore_summary_markdown",
            return_value="",
        )
    )


@contextmanager
def _context_build_dependency_patches() -> Iterator[None]:
    with ExitStack() as stack:
        _register_context_goals_and_scope(stack)
        _register_context_scoped_and_sources(stack)
        _register_context_summaries_ops_artifacts(stack)
        _register_context_read_stubs(stack)
        yield


def _write_plan(
    path: Path, *, slug: str, depends: list[str], status: str = "PENDING"
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    deps_yaml = ", ".join(f'"{d}"' for d in depends) if depends else ""
    _ = path.write_text(
        "\n".join(
            [
                "---",
                f'title: "{slug}"',
                "component: test",
                "work_type: feature",
                f"status: {status}",
                "priority: low",
                "created: 2026-04-11",
                f"depends_on: [{deps_yaml}]",
                "---",
                "",
                "## Goal",
                "",
            ]
        ),
        encoding="utf-8",
    )


@pytest.fixture
def project_with_blocked_child(tmp_path: Path) -> Path:
    root = tmp_path
    plans = get_cortex_path(root, CortexResourceType.PLANS)
    _write_plan(plans / "parent.md", slug="parent", depends=[])
    _write_plan(plans / "child.md", slug="child", depends=["parent"])
    return root


def test_annotate_roadmap_appends_blocked_hint(
    project_with_blocked_child: Path,
) -> None:
    roadmap = "- Plan: [Child plan](../plans/child.md) — work. PENDING.\n"
    out = annotate_roadmap_for_project(roadmap, project_with_blocked_child)
    assert "_(BLOCKED by: parent)_" in out
    assert out.startswith("- Plan:")


def test_build_plan_graph_surface_bundle_counts(
    project_with_blocked_child: Path,
) -> None:
    plans = get_cortex_path(project_with_blocked_child, CortexResourceType.PLANS)
    bundle = build_plan_graph_surface_bundle(
        plans, include_archive=False, max_ascii_edges=10
    )
    assert bundle is not None
    assert "READY" in str(bundle["plan_graph_summary"])
    assert "BLOCKED" in str(bundle["plan_graph_summary"])
    blocked = cast(dict[str, list[str]], bundle["plan_graph_blocked"])
    assert "child" in blocked
    assert blocked["child"] == ["parent"]


def test_inject_plan_graph_into_context_result_merges_keys(
    project_with_blocked_child: Path,
) -> None:
    base = json.dumps(
        {
            "status": "success",
            "task_description": "t",
            "token_budget": 100,
            "strategy": "dependency_aware",
            "total_tokens": 0,
            "utilization": 0.0,
        }
    )
    merged = inject_plan_graph_into_context_result(base, project_with_blocked_child)
    data = json.loads(merged)
    assert data["plan_graph_ready"] == ["parent"]
    assert data["plan_graph_blocked"] == {"child": ["parent"]}
    assert "child → parent" in data["plan_graph_ascii_edges"]


@pytest.mark.asyncio
async def test_build_context_resource_payload_includes_plan_graph(
    project_with_blocked_child: Path,
) -> None:
    """cortex://context resource payload includes plan graph keys (Step 7)."""
    with _context_build_dependency_patches():
        result = await build_context_resource_payload_async(
            _CONTEXT_BASE_JSON, project_with_blocked_child
        )
    data = json.loads(result)
    assert "plan_graph_ready" in data
    assert "plan_graph_blocked" in data
    assert data["plan_graph_ready"] == ["parent"]
    assert data["plan_graph_blocked"] == {"child": ["parent"]}
