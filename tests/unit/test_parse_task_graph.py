"""Tests for ``parse_task_graph`` (parallel task markers)."""

from __future__ import annotations

import pytest

from cortex.core.plan_utils import (
    PlanValidationError,
    apply_independence_parallel_markers,
    is_task_execution_ready,
    next_execution_frontier,
    parse_task_graph,
    task_graph_can_parallelize,
)


def test_parse_task_graph_empty() -> None:
    assert parse_task_graph("") == []


def test_parse_task_graph_sequential_two_steps() -> None:
    md = """### Step 1: First

body one

### Step 2: Second

body two
"""
    nodes = parse_task_graph(md)
    assert len(nodes) == 2
    assert nodes[0].step_id == 1
    assert nodes[0].title == "First"
    assert nodes[0].parallel is False
    assert nodes[0].depends_on == []
    assert "body one" in nodes[0].content
    assert nodes[1].step_id == 2
    assert nodes[1].title == "Second"
    assert nodes[1].parallel is False


def test_parse_task_graph_parallel_marker() -> None:
    md = "### [P] Step 1: Solo\n\nparallel body\n"
    nodes = parse_task_graph(md)
    assert nodes[0].parallel is True
    assert nodes[0].depends_on == []


def test_parse_task_graph_parallel_after_dependencies() -> None:
    md = """### Step 1: Base

x

### [P:after=1] Step 2: After one

y
"""
    nodes = parse_task_graph(md)
    assert nodes[1].parallel is True
    assert nodes[1].depends_on == [1]


def test_parse_task_graph_parallel_after_multiple_dependencies() -> None:
    md = """### Step 1: A

a

### Step 2: B

b

### [P:after=1, 2] Step 3: After both

c
"""
    nodes = parse_task_graph(md)
    assert nodes[2].parallel is True
    assert nodes[2].depends_on == [1, 2]


def test_parse_task_graph_rejects_empty_token_in_after_list() -> None:
    md = "### [P:after=1,,2] Step 1: Bad\n\n"
    with pytest.raises(PlanValidationError, match="empty entry"):
        _ = parse_task_graph(md)


def test_parse_task_graph_rejects_self_dependency_cycle() -> None:
    md = "### [P:after=1] Step 1: Self\n\n"
    with pytest.raises(PlanValidationError, match="cyclic"):
        _ = parse_task_graph(md)


def test_parse_task_graph_ignores_headings_in_fence() -> None:
    md = """```markdown
### Step 1: Fake
```

### Step 1: Real

ok
"""
    nodes = parse_task_graph(md)
    assert len(nodes) == 1
    assert nodes[0].title == "Real"


def test_parse_task_graph_rejects_missing_dependency() -> None:
    md = "### [P:after=99] Step 1: Bad ref\n\n"
    with pytest.raises(PlanValidationError, match="missing step 99"):
        _ = parse_task_graph(md)


def test_parse_task_graph_rejects_cycle() -> None:
    md = """### [P:after=2] Step 1: A

### [P:after=1] Step 2: B

"""
    with pytest.raises(PlanValidationError, match="cyclic"):
        _ = parse_task_graph(md)


def test_parse_task_graph_rejects_duplicate_step_id() -> None:
    md = """### Step 1: One

### Step 1: Dup

"""
    with pytest.raises(PlanValidationError, match="duplicate Step 1"):
        _ = parse_task_graph(md)


def test_parse_task_graph_four_hash_heading() -> None:
    md = "#### Step 1: Deep\n\ninner\n"
    nodes = parse_task_graph(md)
    assert nodes[0].step_id == 1
    assert nodes[0].title == "Deep"


def test_apply_independence_parallel_markers_disjoint_paths() -> None:
    md = (
        "# Plan\n\n"
        "### Step 1: First\n\n"
        "Touch `src/a/foo.py`.\n\n"
        "### Step 2: Second\n\n"
        "Touch `src/b/bar.py`.\n"
    )
    out = apply_independence_parallel_markers(md)
    assert "### Step 1:" in out
    assert "### [P] Step 2:" in out


def test_apply_independence_parallel_markers_skips_when_overlap() -> None:
    md = (
        "### Step 1: One\n\n`src/x/a.py`\n\n"
        + "### Step 2: Two\n\n`src/x/a.py` again\n"
    )
    out = apply_independence_parallel_markers(md)
    assert out == md


def test_task_graph_can_parallelize() -> None:
    md = "### [P] Step 1: Solo\n\n"
    nodes = parse_task_graph(md)
    assert task_graph_can_parallelize(nodes) is True
    seq = parse_task_graph("### Step 1: Only\n\n")
    assert task_graph_can_parallelize(seq) is False


def test_task_graph_can_parallelize_mixed_graph() -> None:
    md = "### Step 1: Seq\n\n### [P] Step 2: Par\n\n### Step 3: Seq2\n\n"
    nodes = parse_task_graph(md)
    assert task_graph_can_parallelize(nodes) is True


def test_next_execution_frontier_sequential_before_parallel() -> None:
    md = """### Step 1: Seq

a

### [P] Step 2: Par

b
"""
    nodes = parse_task_graph(md)
    assert next_execution_frontier(nodes, set()) == [nodes[0]]
    assert next_execution_frontier(nodes, {1}) == [nodes[1]]


def test_next_execution_frontier_parallel_wave_and_cap() -> None:
    md = (
        "### [P] Step 1: A\n\n"
        "### [P] Step 2: B\n\n"
        "### [P] Step 3: C\n\n"
        "### [P] Step 4: D\n\n"
    )
    nodes = parse_task_graph(md)
    wave1 = next_execution_frontier(nodes, set(), max_parallel=3)
    assert [n.step_id for n in wave1] == [1, 2, 3]
    wave2 = next_execution_frontier(nodes, {1, 2, 3}, max_parallel=3)
    assert [n.step_id for n in wave2] == [4]


def test_next_execution_frontier_respects_p_after() -> None:
    md = """### Step 1: Base

x

### [P:after=1] Step 2: After

y

### [P:after=2] Step 3: Last

z
"""
    nodes = parse_task_graph(md)
    assert [n.step_id for n in next_execution_frontier(nodes, set())] == [1]
    assert [n.step_id for n in next_execution_frontier(nodes, {1})] == [2]
    assert [n.step_id for n in next_execution_frontier(nodes, {1, 2})] == [3]


def test_is_task_execution_ready_parallel_waits_sequential_predecessor() -> None:
    md = """### Step 1: Gate

x

### [P] Step 2: Par

y
"""
    nodes = parse_task_graph(md)
    by_id = {n.step_id: n for n in nodes}
    assert is_task_execution_ready(nodes[1], set(), by_id) is False
    assert is_task_execution_ready(nodes[1], {1}, by_id) is True
