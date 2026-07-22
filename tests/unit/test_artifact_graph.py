"""Tests for upstream plan dependency resolution and artifact graph computation."""

from pathlib import Path

from cortex.core.artifact_graph import (
    compute_artifact_graph,
    list_plan_slug_paths,
    plan_slug_in_dependency_cycle,
    read_plan_status_from_content,
    register_plan_file_status_from_graph,
    resolve_upstream_plans,
)
from cortex.core.models import PlanStatus
from cortex.tools.plans.register_artifact_graph import replace_plan_frontmatter_status


def _write_plan(plans_dir: Path, slug: str, status: str, depends_on: list[str]) -> None:
    deps = ", ".join(f'"{dep}"' for dep in depends_on)
    content = f"---\ntitle: {slug}\nstatus: {status}\ndepends_on: [{deps}]\n---\n"
    _ = (plans_dir / f"{slug}.md").write_text(content, encoding="utf-8")


def test_resolve_upstream_plans_transitive_order(tmp_path: Path) -> None:
    # Arrange
    _write_plan(tmp_path, "base", "DONE", [])
    _write_plan(tmp_path, "mid", "DONE", ["base"])
    _write_plan(tmp_path, "leaf", "PENDING", ["mid"])

    # Act
    upstream = resolve_upstream_plans("leaf", tmp_path)

    # Assert
    assert upstream == ["base", "mid"]


def test_resolve_upstream_plans_excludes_non_done_dependencies(tmp_path: Path) -> None:
    # Arrange
    _write_plan(tmp_path, "base", "IN_PROGRESS", [])
    _write_plan(tmp_path, "leaf", "PENDING", ["base"])

    # Act
    upstream = resolve_upstream_plans("leaf", tmp_path)

    # Assert
    assert upstream == []


def test_compute_artifact_graph_all_independent_ready(tmp_path: Path) -> None:
    _write_plan(tmp_path, "a", "PENDING", [])
    _write_plan(tmp_path, "b", "PENDING", [])

    graph = compute_artifact_graph(tmp_path)

    assert graph.ready == ["a", "b"]
    assert graph.blocked == []
    assert graph.cycles == []


def test_compute_artifact_graph_linear_chain_only_first_ready(tmp_path: Path) -> None:
    _write_plan(tmp_path, "first", "PENDING", [])
    _write_plan(tmp_path, "second", "PENDING", ["first"])
    _write_plan(tmp_path, "third", "PENDING", ["second"])

    graph = compute_artifact_graph(tmp_path)

    assert graph.ready == ["first"]
    assert set(graph.blocked) == {"second", "third"}
    assert graph.nodes["second"].blocked_by == ["first"]
    assert graph.cycles == []


def test_compute_artifact_graph_diamond(tmp_path: Path) -> None:
    _write_plan(tmp_path, "root", "DONE", [])
    _write_plan(tmp_path, "left", "DONE", ["root"])
    _write_plan(tmp_path, "right", "DONE", ["root"])
    _write_plan(tmp_path, "join", "PENDING", ["left", "right"])

    graph = compute_artifact_graph(tmp_path)

    assert graph.ready == ["join"]
    assert graph.blocked == []
    assert graph.cycles == []


def test_compute_artifact_graph_cycle_detection(tmp_path: Path) -> None:
    _write_plan(tmp_path, "a", "PENDING", ["b"])
    _write_plan(tmp_path, "b", "PENDING", ["a"])

    graph = compute_artifact_graph(tmp_path)

    assert graph.ready == []
    assert set(graph.blocked) == {"a", "b"}
    assert len(graph.cycles) == 1
    assert set(graph.cycles[0]) == {"a", "b"}


def test_compute_artifact_graph_self_cycle(tmp_path: Path) -> None:
    _write_plan(tmp_path, "solo", "PENDING", ["solo"])

    graph = compute_artifact_graph(tmp_path)

    assert graph.ready == []
    assert graph.blocked == ["solo"]
    assert graph.cycles == [["solo"]]


def test_compute_artifact_graph_missing_dependency_blocks(tmp_path: Path) -> None:
    _write_plan(tmp_path, "orphan", "PENDING", ["missing"])

    graph = compute_artifact_graph(tmp_path)

    assert graph.ready == []
    assert graph.blocked == ["orphan"]
    assert graph.nodes["orphan"].blocked_by == ["missing"]
    assert graph.nodes["orphan"].status == PlanStatus.PENDING


def test_compute_artifact_graph_archived_done_satisfies_dependency(
    tmp_path: Path,
) -> None:
    arch = tmp_path / "archive" / "sub"
    arch.mkdir(parents=True)
    _write_plan(arch, "base", "DONE", [])
    _write_plan(tmp_path, "leaf", "BLOCKED", ["base"])

    without = compute_artifact_graph(tmp_path, include_archive=False)
    assert "leaf" in without.blocked

    with_arch = compute_artifact_graph(tmp_path, include_archive=True)
    assert "leaf" in with_arch.ready
    assert with_arch.nodes["leaf"].blocked_by == []


def test_compute_artifact_graph_archived_not_done_still_blocks(
    tmp_path: Path,
) -> None:
    arch = tmp_path / "archive" / "sub"
    arch.mkdir(parents=True)
    _write_plan(arch, "base", "IN_PROGRESS", [])
    _write_plan(tmp_path, "leaf", "PENDING", ["base"])

    with_arch = compute_artifact_graph(tmp_path, include_archive=True)

    assert "leaf" in with_arch.blocked
    assert with_arch.nodes["leaf"].blocked_by == ["base"]


def test_list_plan_slug_paths_excludes_archive_by_default(tmp_path: Path) -> None:
    arch = tmp_path / "archive"
    arch.mkdir(parents=True)
    _write_plan(tmp_path, "root", "PENDING", [])
    _write_plan(arch, "old", "DONE", [])

    active = list_plan_slug_paths(tmp_path, include_archive=False)
    assert {p.stem for _, p in active} == {"root"}

    all_rows = list_plan_slug_paths(tmp_path, include_archive=True)
    assert {p.stem for _, p in all_rows} == {"old", "root"}


def test_read_plan_status_from_content_defaults_pending() -> None:
    assert read_plan_status_from_content("no frontmatter") == PlanStatus.PENDING
    assert (
        read_plan_status_from_content("---\nstatus: BLOCKED\n---\n")
        == PlanStatus.BLOCKED
    )


def test_plan_slug_in_dependency_cycle(tmp_path: Path) -> None:
    _write_plan(tmp_path, "a", "PENDING", ["b"])
    _write_plan(tmp_path, "b", "PENDING", ["a"])
    graph = compute_artifact_graph(tmp_path)
    assert plan_slug_in_dependency_cycle("a", graph) is True
    assert plan_slug_in_dependency_cycle("b", graph) is True


def test_register_plan_file_status_from_graph_clarification_wins(
    tmp_path: Path,
) -> None:
    _write_plan(tmp_path, "solo", "PENDING", [])
    graph = compute_artifact_graph(tmp_path)
    st = register_plan_file_status_from_graph(
        clarification_blocked=True, graph=graph, slug="solo"
    )
    assert st == PlanStatus.BLOCKED


def test_replace_plan_frontmatter_status_updates_and_inserts() -> None:
    with_status = "---\ntitle: t\nstatus: PENDING\ndepends_on: []\n---\n\nbody"
    out = replace_plan_frontmatter_status(with_status, PlanStatus.BLOCKED)
    assert "status: BLOCKED" in out
    assert "status: PENDING" not in out

    no_status = "---\ntitle: t\ndepends_on: []\n---\n\nbody"
    out2 = replace_plan_frontmatter_status(no_status, PlanStatus.BLOCKED)
    assert "status: BLOCKED" in out2
