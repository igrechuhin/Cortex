"""Tests for propose_framework_optimization diff generation."""

from __future__ import annotations

from pathlib import Path

from cortex.tools.optimization.propose_framework_optimization_diff import (
    build_diff_and_rationale,
)
from cortex.tools.optimization.propose_framework_optimization_models import (
    ProposedFileChange,
)


def test_diff_for_new_file_shows_additions(tmp_path: Path) -> None:
    change = ProposedFileChange(
        relative_path=".cortex/rules/new.mdc", new_content="---\ndescription: x\n---\n"
    )

    diff = build_diff_and_rationale(tmp_path, [change])

    assert "+---" in diff
    assert "a/.cortex/rules/new.mdc" in diff
    assert "b/.cortex/rules/new.mdc" in diff


def test_diff_for_modified_file_shows_changes(tmp_path: Path) -> None:
    live_path = tmp_path / ".cortex" / "rules" / "existing.mdc"
    live_path.parent.mkdir(parents=True)
    _ = live_path.write_text("---\ndescription: old\n---\n", encoding="utf-8")
    change = ProposedFileChange(
        relative_path=".cortex/rules/existing.mdc",
        new_content="---\ndescription: new\n---\n",
    )

    diff = build_diff_and_rationale(tmp_path, [change])

    assert "-description: old" in diff
    assert "+description: new" in diff


def test_diff_for_unchanged_content_reports_no_changes(tmp_path: Path) -> None:
    live_path = tmp_path / ".cortex" / "rules" / "same.mdc"
    live_path.parent.mkdir(parents=True)
    content = "---\ndescription: same\n---\n"
    _ = live_path.write_text(content, encoding="utf-8")
    change = ProposedFileChange(
        relative_path=".cortex/rules/same.mdc", new_content=content
    )

    diff = build_diff_and_rationale(tmp_path, [change])

    assert "no changes: .cortex/rules/same.mdc" in diff
