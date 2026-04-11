"""Tests for ``TaskNode`` plan task graph model."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from cortex.core.models import TaskNode


def test_task_node_minimal_sequential() -> None:
    node = TaskNode(step_id=1, title="First step", parallel=False)
    assert node.depends_on == []
    assert node.content == ""


def test_task_node_parallel_with_dependencies() -> None:
    node = TaskNode(
        step_id=2,
        title="After others",
        parallel=True,
        depends_on=[1, 3],
        content="- do thing\n",
    )
    assert node.parallel is True
    assert node.depends_on == [1, 3]


def test_task_node_step_id_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        _ = TaskNode(step_id=0, title="bad", parallel=False)
