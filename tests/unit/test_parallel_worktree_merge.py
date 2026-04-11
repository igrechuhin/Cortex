"""Tests for parallel worktree merge ordering and path-level conflict markers."""

from __future__ import annotations

import pytest

from cortex.core.models import TaskNode
from cortex.core.parallel_worktree_merge import (
    clarification_markers_for_shared_paths,
    merge_order_for_parallel_batch,
)
from cortex.core.plan_utils import PlanValidationError


def test_merge_order_empty() -> None:
    assert merge_order_for_parallel_batch([]) == []


def test_merge_order_stable_when_independent() -> None:
    batch = (
        TaskNode(step_id=3, title="c", parallel=True, content=""),
        TaskNode(step_id=1, title="a", parallel=True, content=""),
        TaskNode(step_id=2, title="b", parallel=True, content=""),
    )
    assert merge_order_for_parallel_batch(batch) == [1, 2, 3]


def test_merge_order_respects_intra_batch_dependencies() -> None:
    batch = (
        TaskNode(step_id=2, title="b", parallel=True, depends_on=[1], content=""),
        TaskNode(step_id=1, title="a", parallel=True, content=""),
    )
    assert merge_order_for_parallel_batch(batch) == [1, 2]


def test_merge_order_rejects_cycle_inside_batch() -> None:
    batch = (
        TaskNode(step_id=1, title="a", parallel=True, depends_on=[2], content=""),
        TaskNode(step_id=2, title="b", parallel=True, depends_on=[1], content=""),
    )
    with pytest.raises(PlanValidationError, match="cyclic"):
        _ = merge_order_for_parallel_batch(batch)


def test_shared_paths_emit_blocking_markers() -> None:
    batch = (
        TaskNode(step_id=1, title="a", parallel=True, content=""),
        TaskNode(step_id=2, title="b", parallel=True, content=""),
    )
    paths = {1: {"src/x.py"}, 2: {"src/x.py", "src/y.py"}}
    markers = clarification_markers_for_shared_paths(batch, paths)
    assert len(markers) == 1
    assert markers[0].blocking is True
    assert "steps 1, 2" in markers[0].reason
    assert "src/x.py" in markers[0].reason


def test_shared_paths_no_marker_when_disjoint() -> None:
    batch = (
        TaskNode(step_id=1, title="a", parallel=True, content=""),
        TaskNode(step_id=2, title="b", parallel=True, content=""),
    )
    paths = {1: {"src/a.py"}, 2: {"src/b.py"}}
    assert clarification_markers_for_shared_paths(batch, paths) == []
