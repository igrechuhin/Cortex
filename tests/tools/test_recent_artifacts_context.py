"""Tests for Recent Artifacts section builder (cortex://context)."""

from __future__ import annotations

import json
import os
from pathlib import Path

from cortex.tools.context.recent_artifacts_context import (
    build_recent_artifacts_markdown,
)
from cortex.tools.optimization.context_appenders import (
    append_recent_artifacts_to_context_payload,
    read_recent_artifacts_markdown,
)


def test_build_recent_artifacts_returns_none_without_creating_dirs(
    tmp_path: Path,
) -> None:
    assert build_recent_artifacts_markdown(tmp_path) is None
    assert not (tmp_path / ".cortex").exists()


def test_build_recent_artifacts_lists_newest_first_and_limits_five(
    tmp_path: Path,
) -> None:
    reviews = tmp_path / ".cortex" / "reviews"
    reviews.mkdir(parents=True)
    for i in range(6):
        path = reviews / f"review-x-{i}.md"
        _ = path.write_text(f"# T{i}\n\nBody {i}.", encoding="utf-8")
        os.utime(path, (1_700_000_000 + i, 1_700_000_000 + i))
    out = build_recent_artifacts_markdown(tmp_path)
    assert out is not None
    assert out.count("- [../reviews/") == 5
    assert "review-x-5.md" in out
    assert "review-x-0.md" not in out
    assert out.index("review-x-5.md") < out.index("review-x-1.md")


def test_build_recent_artifacts_includes_only_canonical_report_dirs(
    tmp_path: Path,
) -> None:
    for directory, name, body in (
        ("reviews", "r.md", "Review summary."),
        ("analyses", "a.md", "---\ntitle: X\n---\n\nAfter frontmatter."),
        ("queries", "q.md", "Query summary."),
    ):
        folder = tmp_path / ".cortex" / directory
        folder.mkdir(parents=True)
        _ = (folder / name).write_text(body, encoding="utf-8")
    memory_bank = tmp_path / ".cortex" / "memory-bank"
    for directory in ("reviews", "analyses", "queries", "findings"):
        folder = memory_bank / directory
        folder.mkdir(parents=True)
        _ = (folder / "excluded.md").write_text("Legacy or finding.", encoding="utf-8")
    out = build_recent_artifacts_markdown(tmp_path)
    assert out is not None
    for directory, name in (
        ("reviews", "r.md"),
        ("analyses", "a.md"),
        ("queries", "q.md"),
    ):
        assert f"[../{directory}/{name}](../{directory}/{name})" in out
    assert "After frontmatter." in out
    assert "excluded.md" not in out


def test_build_recent_artifacts_breaks_equal_mtime_ties_alphabetically(
    tmp_path: Path,
) -> None:
    reviews = tmp_path / ".cortex" / "reviews"
    reviews.mkdir(parents=True)
    for name in ("b-review.md", "a-review.md"):
        path = reviews / name
        _ = path.write_text(f"# {name}\n\nBody.", encoding="utf-8")
        os.utime(path, (1_700_000_000, 1_700_000_000))
    out = build_recent_artifacts_markdown(tmp_path)
    assert out is not None
    assert out.index("a-review.md") < out.index("b-review.md")


def test_one_line_summary_truncates_long_first_line(tmp_path: Path) -> None:
    reviews = tmp_path / ".cortex" / "reviews"
    reviews.mkdir(parents=True)
    _ = (reviews / "long.md").write_text("w" * 250, encoding="utf-8")
    out = build_recent_artifacts_markdown(tmp_path)
    assert out is not None
    assert "..." in out


def test_context_appender_reads_canonical_queries_without_creating_bank_dirs(
    tmp_path: Path,
) -> None:
    queries = tmp_path / ".cortex" / "queries"
    queries.mkdir(parents=True)
    _ = (queries / "query.md").write_text("Query conclusion.", encoding="utf-8")
    result = json.loads(
        append_recent_artifacts_to_context_payload(
            '{"status": "success"}', read_recent_artifacts_markdown(tmp_path)
        )
    )
    assert "../queries/query.md" in result["recent_artifacts"]
    assert not (tmp_path / ".cortex" / "memory-bank").exists()
