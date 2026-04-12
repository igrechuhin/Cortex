"""Wiki ``sources/`` take precedence over memory-bank for recent-ingest context."""

from __future__ import annotations

from pathlib import Path

from cortex.tools.optimization.handlers import read_recent_ingested_sources_markdown
from cortex.wiki.layout import ensure_default_wiki_layout


def test_recent_ingested_sources_prefers_wiki_when_populated(tmp_path: Path) -> None:
    _ = (tmp_path / ".cortex").mkdir()
    _ = ensure_default_wiki_layout(tmp_path)
    mb_sources = tmp_path / ".cortex" / "memory-bank" / "sources"
    mb_sources.mkdir(parents=True)
    _ = (mb_sources / "memory-only.md").write_text("# Memory\n", encoding="utf-8")
    wiki_sources = tmp_path / ".cortex" / "wiki" / "sources"
    _ = (wiki_sources / "wiki-only.md").write_text("# Wiki\n", encoding="utf-8")

    out = read_recent_ingested_sources_markdown(tmp_path)
    assert out is not None
    assert "Wiki" in out
    assert "wiki-only.md" in out
    assert "memory-only" not in out


def test_recent_ingested_sources_falls_back_to_memory_bank(tmp_path: Path) -> None:
    _ = (tmp_path / ".cortex").mkdir()
    _ = ensure_default_wiki_layout(tmp_path)
    mb_sources = tmp_path / ".cortex" / "memory-bank" / "sources"
    mb_sources.mkdir(parents=True)
    _ = (mb_sources / "fallback.md").write_text("# Fallback\n", encoding="utf-8")

    out = read_recent_ingested_sources_markdown(tmp_path)
    assert out is not None
    assert "Fallback" in out
