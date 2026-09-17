"""Behavioral regressions for contained plan discovery and unique identities."""

from pathlib import Path
from unittest.mock import patch

import pytest

from cortex.core.artifact_graph import compute_artifact_graph
from cortex.core.plan_identity import (
    build_plan_identity_index,
    find_plan_slug_paths,
    is_plan_document,
    iter_plan_file_rows,
)
from cortex.tools.plans.step_draft_core import STEP_STATE_BEGIN, STEP_STATE_CLOSE


def write_plan(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text("---\nstatus: PENDING\n---\n\n## Goal\n\nWork.\n")


@pytest.mark.parametrize(
    "name",
    [
        "README.md",
        "readme.MD",
        "QUICK_START.md",
        "index.md",
        "dependency-graph.md",
        "TEMPLATE.md",
        "template-feature.md",
        "plan.json",
    ],
)
def test_scaffolding_predicate_never_reads_files(name: str) -> None:
    with patch.object(Path, "read_text", side_effect=AssertionError("Unexpected read")):
        assert not is_plan_document(Path(name))


@pytest.mark.parametrize("name", ["feature.md", "legacy.plan.md", "draft-feature.md"])
def test_real_plan_filename_predicate_is_pure(name: str) -> None:
    with patch.object(Path, "read_text", side_effect=AssertionError("Unexpected read")):
        assert is_plan_document(Path(name))


def test_discovery_preserves_active_and_archived_locations(tmp_path: Path) -> None:
    write_plan(tmp_path / "z.md")
    write_plan(tmp_path / "archive" / "Other" / "a.md")

    active = iter_plan_file_rows(tmp_path, include_archive=False)
    all_rows = iter_plan_file_rows(tmp_path, include_archive=True)

    assert [row.slug for row in active] == ["z"]
    assert [row.relative_path for row in all_rows] == ["archive/Other/a.md", "z.md"]
    assert [row.archived for row in all_rows] == [True, False]


def test_discovery_ignores_scaffolds_and_actual_draft_footer(tmp_path: Path) -> None:
    for name in ["README.md", "TEMPLATE.md", "index.md", "QUICK_START.md"]:
        write_plan(tmp_path / name)
    draft = tmp_path / "draft-feature.md"
    write_plan(draft)
    footer = STEP_STATE_BEGIN + '{"sections": []}\n' + STEP_STATE_CLOSE + "\n"
    _ = draft.write_text(draft.read_text() + footer)
    write_plan(tmp_path / "feature.md")

    rows = iter_plan_file_rows(tmp_path, include_archive=True)

    assert [row.slug for row in rows] == ["feature"]


def test_draft_marker_discussion_does_not_hide_real_plan(tmp_path: Path) -> None:
    path = tmp_path / "draft-format-design.md"
    write_plan(path)
    discussion = "\nDocument CORTEX_STEP_PLAN_STATE and how draft footers work.\n"
    _ = path.write_text(path.read_text() + discussion)

    rows = iter_plan_file_rows(tmp_path, include_archive=True)

    assert [row.slug for row in rows] == ["draft-format-design"]


def test_duplicate_active_and_archived_slugs_are_not_unique(tmp_path: Path) -> None:
    write_plan(tmp_path / "same.md")
    write_plan(tmp_path / "archive" / "same.md")
    write_plan(tmp_path / "unique.md")

    index = build_plan_identity_index(tmp_path)

    assert set(index.unique) == {"unique"}
    assert set(index.ambiguous) == {"same"}
    candidates = index.ambiguous.get("same", [])
    assert {row.relative_path for row in candidates} == {"same.md", "archive/same.md"}
    assert len(find_plan_slug_paths(tmp_path, "same")) == 2


def test_file_symlink_target_is_never_read(tmp_path: Path) -> None:
    plans = tmp_path / "plans"
    plans.mkdir()
    sentinel = tmp_path / "external.md"
    _ = sentinel.write_text("External sentinel")
    (plans / "escape.md").symlink_to(sentinel)

    with patch.object(Path, "read_text", side_effect=AssertionError("External read")):
        rows = iter_plan_file_rows(plans, include_archive=True)

    assert rows == []
    assert sentinel.read_text() == "External sentinel"


def test_symlink_directory_is_not_traversed(tmp_path: Path) -> None:
    plans = tmp_path / "plans"
    plans.mkdir()
    outside = tmp_path / "outside"
    write_plan(outside / "external.md")
    (plans / "nested").symlink_to(outside, target_is_directory=True)

    with patch.object(Path, "read_text", side_effect=AssertionError("External read")):
        rows = iter_plan_file_rows(plans, include_archive=True)

    assert rows == []


def test_symlinked_plans_root_is_not_read(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    write_plan(outside / "external.md")
    plans = tmp_path / "plans"
    plans.symlink_to(outside, target_is_directory=True)

    with patch.object(Path, "read_text", side_effect=AssertionError("External read")):
        index = build_plan_identity_index(plans)

    assert index.unique == {}
    assert index.ambiguous == {}


def test_invalid_utf8_plan_does_not_break_discovery_or_graph(tmp_path: Path) -> None:
    _ = (tmp_path / "invalid.md").write_bytes(b"\xff\xfe\x80")
    write_plan(tmp_path / "valid.md")

    rows = iter_plan_file_rows(tmp_path, include_archive=True)
    graph = compute_artifact_graph(tmp_path)

    assert [row.slug for row in rows] == ["valid"]
    assert graph.ready == ["valid"]


def test_nonexistent_plan_directory_has_empty_index(tmp_path: Path) -> None:
    index = build_plan_identity_index(tmp_path / "missing")

    assert index.unique == {}
    assert index.ambiguous == {}


def test_only_canonical_archive_root_changes_lifecycle_location(tmp_path: Path) -> None:
    write_plan(tmp_path / "archive" / "historical.md")
    write_plan(tmp_path / "component" / "archive" / "current.md")

    rows = iter_plan_file_rows(tmp_path, include_archive=False)

    assert [row.relative_path for row in rows] == ["component/archive/current.md"]
    assert rows[0].archived is False
