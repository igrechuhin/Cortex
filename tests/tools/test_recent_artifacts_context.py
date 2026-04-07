"""Tests for Recent Artifacts section builder (cortex://context)."""

from __future__ import annotations

import os
from pathlib import Path

from cortex.tools.context.recent_artifacts_context import (
    build_recent_artifacts_markdown,
)


def test_build_recent_artifacts_returns_none_when_empty(tmp_path: Path) -> None:
    mb = tmp_path / ".cortex" / "memory-bank"
    mb.mkdir(parents=True)
    assert build_recent_artifacts_markdown(mb) is None


def test_build_recent_artifacts_lists_newest_first_and_limits_five(
    tmp_path: Path,
) -> None:
    mb = tmp_path / ".cortex" / "memory-bank"
    reviews = mb / "reviews"
    reviews.mkdir(parents=True)
    # Six files; only five should appear, newest by mtime win.
    for i in range(6):
        p = reviews / f"review-x-{i}.md"
        _ = p.write_text(f"# T{i}\n\nBody {i}.", encoding="utf-8")
        # Older files get lower index; bump mtime so review-x-5 is newest.
        os.utime(p, (1_700_000_000 + i, 1_700_000_000 + i))

    out = build_recent_artifacts_markdown(mb)
    assert out is not None
    assert "## Recent Artifacts" in out
    assert out.count("- [reviews/") == 5
    assert "review-x-5.md" in out
    assert "review-x-0.md" not in out


def test_build_recent_artifacts_includes_analyses_and_reviews(tmp_path: Path) -> None:
    mb = tmp_path / ".cortex" / "memory-bank"
    (mb / "reviews").mkdir(parents=True)
    (mb / "analyses").mkdir(parents=True)
    _ = (mb / "reviews" / "r.md").write_text("Summary line one.", encoding="utf-8")
    _ = (mb / "analyses" / "a.md").write_text(
        "---\ntitle: X\n---\n\nAfter frontmatter.", encoding="utf-8"
    )
    os.utime(mb / "analyses" / "a.md", (2_000_000_000, 2_000_000_000))
    os.utime(mb / "reviews" / "r.md", (1_000_000_000, 1_000_000_000))

    out = build_recent_artifacts_markdown(mb)
    assert out is not None
    assert "analyses/a.md" in out
    assert "After frontmatter" in out
    assert "reviews/r.md" in out
    assert "Summary line one" in out


def test_one_line_summary_truncates_long_first_line(tmp_path: Path) -> None:
    mb = tmp_path / ".cortex" / "memory-bank"
    (mb / "reviews").mkdir(parents=True)
    long_line = "w" * 250
    _ = (mb / "reviews" / "long.md").write_text(long_line, encoding="utf-8")
    out = build_recent_artifacts_markdown(mb)
    assert out is not None
    assert "..." in out
