"""Tests for Recently Ingested Sources section builder (cortex://context)."""

from __future__ import annotations

import os
from pathlib import Path

from cortex.tools.context.recent_ingested_sources_context import (
    build_recent_ingested_sources_markdown,
)


def test_build_recent_ingested_sources_returns_none_when_sources_dir_missing(
    tmp_path: Path,
) -> None:
    mb = tmp_path / ".cortex" / "memory-bank"
    mb.mkdir(parents=True)
    assert build_recent_ingested_sources_markdown(mb) is None


def test_build_recent_ingested_sources_lists_newest_first_and_limits_five(
    tmp_path: Path,
) -> None:
    mb = tmp_path / ".cortex" / "memory-bank"
    sources = mb / "sources"
    sources.mkdir(parents=True)
    for i in range(6):
        p = sources / f"source-{i}.md"
        _ = p.write_text(f"# Source {i}\n\nBody", encoding="utf-8")
        os.utime(p, (1_700_000_000 + i, 1_700_000_000 + i))

    out = build_recent_ingested_sources_markdown(mb)
    assert out is not None
    assert "## Recently Ingested Sources" in out
    assert out.count("- [Source ") == 5
    assert "(sources/source-5.md)" in out
    assert "(sources/source-0.md)" not in out


def test_build_recent_ingested_sources_falls_back_to_slug_title(tmp_path: Path) -> None:
    mb = tmp_path / ".cortex" / "memory-bank"
    sources = mb / "sources"
    sources.mkdir(parents=True)
    _ = (sources / "my-ingested-rfc-2.md").write_text("", encoding="utf-8")

    out = build_recent_ingested_sources_markdown(mb)
    assert out is not None
    assert "- [My Ingested Rfc](sources/my-ingested-rfc-2.md)" in out
