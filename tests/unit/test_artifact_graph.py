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
from cortex.core.models import PlanExecutionMode, PlanStatus
from cortex.core.plan_frontmatter_normalize import normalize_plan_files
from cortex.core.plan_metadata import read_plan_status_metadata
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
    _write_plan(tmp_path, "leaf", "PENDING", ["base"])

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


def test_depends_on_tolerates_md_extension_and_path_prefix(tmp_path: Path) -> None:
    # Arrange
    _write_plan(tmp_path, "base", "DONE", [])
    content = '---\nstatus: PENDING\ndepends_on: [".cortex/plans/base.md"]\n---\n'
    _ = (tmp_path / "leaf.md").write_text(content, encoding="utf-8")

    # Act
    graph = compute_artifact_graph(tmp_path)

    # Assert
    assert graph.nodes["leaf"].depends_on == ["base"]
    assert graph.nodes["leaf"].blocked_by == []


def test_quoted_and_legacy_status_values_resolve() -> None:
    # Arrange / Act / Assert
    assert read_plan_status_from_content('---\nstatus: "DONE"\n---') == PlanStatus.DONE
    assert (
        read_plan_status_from_content('---\nstatus: "COMPLETED"\n---')
        == PlanStatus.DONE
    )
    assert (
        read_plan_status_from_content("---\nstatus: COMPLETE\n---") == PlanStatus.DONE
    )
    assert (
        read_plan_status_from_content('---\nstatus: "Completed (26-05-04-22-26)"\n---')
        == PlanStatus.DONE
    )
    assert (
        read_plan_status_from_content("---\nstatus: NOT_VIABLE\n---")
        == PlanStatus.PENDING
    )


def test_graph_preserves_non_actionable_status_intent(tmp_path: Path) -> None:
    # Arrange
    for slug, status in (
        ("manual", "BLOCKED"),
        ("working", "IN_PROGRESS"),
        ("declined", "DECLINED"),
    ):
        _write_plan(tmp_path, slug, status, [])

    # Act
    graph = compute_artifact_graph(tmp_path)

    # Assert
    assert graph.ready == []
    assert graph.blocked == ["manual"]
    assert graph.nodes["working"].status == PlanStatus.IN_PROGRESS
    assert graph.nodes["declined"].raw_status == "DECLINED"
    assert graph.nodes["declined"].status_recognized is False


def test_archived_non_done_vertex_is_resolvable_but_not_actionable(
    tmp_path: Path,
) -> None:
    # Arrange
    archive = tmp_path / "archive"
    archive.mkdir()
    _write_plan(archive, "old", "PENDING", [])
    _write_plan(tmp_path, "leaf", "PENDING", ["old"])

    # Act
    graph = compute_artifact_graph(tmp_path)

    # Assert
    assert "old" in graph.nodes
    assert "old" not in graph.ready
    assert graph.blocked == ["leaf"]


def test_duplicate_slug_is_reported_and_not_dependency_resolvable(
    tmp_path: Path,
) -> None:
    # Arrange
    archive = tmp_path / "archive"
    archive.mkdir()
    _write_plan(tmp_path, "base", "DONE", [])
    _write_plan(archive, "base", "DONE", [])
    _write_plan(tmp_path, "leaf", "PENDING", ["base"])

    # Act
    graph = compute_artifact_graph(tmp_path)

    # Assert
    assert "base" not in graph.nodes
    assert graph.ambiguous_slugs == {"base": ["archive/base.md", "base.md"]}
    assert graph.nodes["leaf"].blocked_by == ["base"]


def test_status_and_dependencies_are_scoped_to_frontmatter(tmp_path: Path) -> None:
    # Arrange
    _ = (tmp_path / "example.md").write_text(
        "".join(
            (
                "---\ntitle: Example\nstatus: PENDING\ndepends_on: []\n---\n",
                "\nExample:\nstatus: DONE\ndepends_on: [missing]\n",
            )
        ),
        encoding="utf-8",
    )

    # Act
    graph = compute_artifact_graph(tmp_path)

    # Assert
    assert graph.ready == ["example"]
    assert graph.nodes["example"].depends_on == []


def test_status_duplicates_and_legacy_lines_preserve_intent() -> None:
    # Arrange / Act
    same = read_plan_status_metadata("---\nstatus: PENDING\nstatus: READY\n---\n")
    custom = read_plan_status_metadata("---\nstatus: COMPLETE pending review\n---\n")
    dated = read_plan_status_metadata("---\nstatus: COMPLETED (26-05-04-22-26)\n---\n")
    legacy = read_plan_status_metadata("# Plan\n\n**Status**: IN PROGRESS.\n")
    empty = read_plan_status_metadata("---\nstatus:\nDONE\n---\n")
    malformed_quote = read_plan_status_metadata('---\nstatus: "DONE\n---\n')
    quoted_comment = read_plan_status_metadata(
        '---\nstatus: "DONE" # "reviewed"\n---\n'
    )
    four_digit_date = read_plan_status_metadata(
        "---\nstatus: COMPLETED (2026-05-04)\n---\n"
    )
    fenced = read_plan_status_metadata("# Plan\n\n```markdown\n**Status**: DONE\n```\n")

    # Assert
    assert same.conflicting is True
    assert same.recognized is False
    assert custom.recognized is False
    assert dated.status == PlanStatus.DONE
    assert dated.recognized is True
    assert legacy.status == PlanStatus.IN_PROGRESS
    assert legacy.recognized is True
    assert empty.recognized is False
    assert malformed_quote.recognized is False
    assert quoted_comment.status == PlanStatus.DONE
    assert quoted_comment.recognized is True
    assert four_digit_date.status == PlanStatus.DONE
    assert four_digit_date.recognized is True
    assert fenced.recognized is False


def test_legacy_status_ignores_tilde_fence() -> None:
    # Act
    metadata = read_plan_status_metadata(
        "# Plan\n\n~~~markdown\n**Status**: DONE\n~~~\n"
    )

    # Assert
    assert metadata.recognized is False


def test_nested_yaml_fields_are_not_root_plan_metadata(tmp_path: Path) -> None:
    # Arrange
    _ = (tmp_path / "nested.md").write_text(
        "".join(
            (
                "---\ntitle: Nested\nmetadata:\n  status: DONE\n",
                "  depends_on: [missing]\n  execution: operator\n---\n",
            )
        ),
        encoding="utf-8",
    )

    # Act
    graph = compute_artifact_graph(tmp_path)

    # Assert
    node = graph.nodes["nested"]
    assert node.status_recognized is False
    assert node.depends_on == []
    assert node.execution == PlanExecutionMode.AGENT
    assert graph.ready == []


def test_execution_frontmatter_parsed(tmp_path: Path) -> None:
    # Arrange
    for slug, line in (("a", "execution: operator"), ("b", 'execution: "agent"')):
        _ = (tmp_path / f"{slug}.md").write_text(
            f"---\nstatus: PENDING\n{line}\ndepends_on: []\n---\n", encoding="utf-8"
        )
    _ = (tmp_path / "c.md").write_text(
        "---\nstatus: PENDING\ndepends_on: []\n---\n", encoding="utf-8"
    )

    # Act
    graph = compute_artifact_graph(tmp_path)

    # Assert
    assert graph.nodes["a"].execution == PlanExecutionMode.OPERATOR
    assert graph.nodes["b"].execution == PlanExecutionMode.AGENT
    assert graph.nodes["c"].execution == PlanExecutionMode.AGENT


def test_normalize_plan_files_canonicalizes_frontmatter(tmp_path: Path) -> None:
    # Arrange
    path = tmp_path / "leaf.md"
    messy = (
        '---\ntitle: "Leaf"\nwork_type: "Fix"\nstatus: "COMPLETED"\n'
        'priority: "medium"\ncreated: "26-08-30"\nexecution: "Operator"\n'
        'depends_on: ["base.md", ".cortex/plans/other.md"]\n---\n\nBody\n'
    )
    _ = path.write_text(messy, encoding="utf-8")
    keep = tmp_path / "keep.md"
    _ = keep.write_text(
        "---\nstatus: NOT_VIABLE\ndepends_on: []\n---\n", encoding="utf-8"
    )

    # Act
    changed = normalize_plan_files(tmp_path)

    # Assert
    assert changed == [path]
    expected = (
        '---\ntitle: "Leaf"\nwork_type: fix\nstatus: DONE\n'
        "priority: Medium\ncreated: 2026-08-30\nexecution: operator\n"
        'depends_on: ["base", "other"]\n---\n\nBody\n'
    )
    assert path.read_text(encoding="utf-8") == expected
    assert "NOT_VIABLE" in keep.read_text(encoding="utf-8")


def test_normalize_plan_files_canonicalizes_extended_enum_values(
    tmp_path: Path,
) -> None:
    # Arrange
    path = tmp_path / "leaf.md"
    messy = (
        '---\nwork_type: "MIGRATION"\nstatus: PENDING\npriority: "blocker"\n'
        "depends_on: []\n---\n"
    )
    _ = path.write_text(messy, encoding="utf-8")

    # Act
    _ = normalize_plan_files(tmp_path)

    # Assert
    text = path.read_text(encoding="utf-8")
    assert "work_type: migration" in text
    assert "priority: Blocker" in text


def test_normalize_plan_files_aliases_legacy_work_types(tmp_path: Path) -> None:
    # Arrange
    aliased = {"bugfix": "fix", "Refactoring": "refactor", "infra": "infrastructure"}
    for raw in (*aliased, "ops"):
        _ = (tmp_path / f"{raw}.md").write_text(
            f"---\nwork_type: {raw}\nstatus: PENDING\ndepends_on: []\n---\n",
            encoding="utf-8",
        )

    # Act
    _ = normalize_plan_files(tmp_path)

    # Assert
    for raw, canonical in aliased.items():
        text = (tmp_path / f"{raw}.md").read_text(encoding="utf-8")
        assert f"work_type: {canonical}" in text
    assert "work_type: infrastructure" in (tmp_path / "ops.md").read_text(
        encoding="utf-8"
    )


def test_normalize_plan_files_migrates_created_dates(tmp_path: Path) -> None:
    # Arrange
    cases = {
        "iso": ('created: "2026-03-07"', "created: 2026-03-07"),
        "short_year": ('created: "26-02-15"', "created: 2026-02-15"),
        "unpadded": ("created: 2026-3-7", "created: 2026-03-07"),
        "placeholder": ('created: "<YYYY-MM-DD>"', 'created: "<YYYY-MM-DD>"'),
        "impossible": ('created: "2026-13-45"', 'created: "2026-13-45"'),
    }
    for slug, (raw, _) in cases.items():
        _ = (tmp_path / f"{slug}.md").write_text(
            f"---\nstatus: PENDING\n{raw}\ndepends_on: []\n---\n", encoding="utf-8"
        )

    # Act
    _ = normalize_plan_files(tmp_path)

    # Assert
    for slug, (_, expected) in cases.items():
        assert expected in (tmp_path / f"{slug}.md").read_text(encoding="utf-8")


def test_normalize_plan_files_strips_template_comments(tmp_path: Path) -> None:
    # Arrange
    path = tmp_path / "leaf.md"
    messy = (
        '---\nwork_type: "fix"   # fix | refactor | feature\n'
        "status: PENDING   # PENDING | DONE\n"
        "priority: Critical   # Blocker | Critical\n"
        "execution: agent   # agent | operator\n"
        "depends_on: []   # plan slugs\n---\n"
    )
    _ = path.write_text(messy, encoding="utf-8")

    # Act
    _ = normalize_plan_files(tmp_path)

    # Assert
    assert path.read_text(encoding="utf-8") == (
        "---\nwork_type: fix\nstatus: PENDING\npriority: Critical\n"
        "execution: agent\ndepends_on: []\n---\n"
    )
