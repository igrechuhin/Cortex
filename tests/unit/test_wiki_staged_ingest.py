"""Tests for ``wiki_ingest_staged_docs``."""

from __future__ import annotations

from pathlib import Path

from cortex.tools.wiki.staged_ingest import wiki_ingest_staged_docs
from cortex.wiki.layout import ensure_default_wiki_layout


def test_wiki_ingest_skips_when_no_wiki(tmp_path: Path) -> None:
    doc = tmp_path / "docs" / "a.md"
    doc.parent.mkdir(parents=True)
    _ = doc.write_text("# Title\n\nbody\n", encoding="utf-8")
    result = wiki_ingest_staged_docs(["docs/a.md"], tmp_path)
    assert result.ingested == []
    assert "docs/a.md" in result.skipped
    assert result.wiki_files_written == []


def test_wiki_ingest_staged_doc_writes_wiki_paths(tmp_path: Path) -> None:
    _ = (tmp_path / ".cortex").mkdir(parents=True)
    _bootstrap = ensure_default_wiki_layout(tmp_path)
    assert _bootstrap.wiki_root
    doc = tmp_path / "docs" / "auth.md"
    doc.parent.mkdir(parents=True)
    _ = doc.write_text("# Auth\n\nHow auth works.\n", encoding="utf-8")
    result = wiki_ingest_staged_docs(["docs/auth.md"], tmp_path)
    assert result.errors == []
    assert result.ingested == ["docs/auth.md"]
    assert result.skipped == []
    assert result.wiki_files_written
    for p in result.wiki_files_written:
        assert p.startswith(".cortex/wiki/")
    raw = tmp_path / ".cortex" / "wiki" / "sources"
    assert any(raw.glob("*.md"))


def test_wiki_ingest_unchanged_on_second_identical_run(tmp_path: Path) -> None:
    _ = (tmp_path / ".cortex").mkdir(parents=True)
    _bootstrap = ensure_default_wiki_layout(tmp_path)
    assert _bootstrap.wiki_root
    doc = tmp_path / "docs" / "auth.md"
    doc.parent.mkdir(parents=True)
    body = "# Auth\n\nHow auth works.\n"
    _ = doc.write_text(body, encoding="utf-8")
    first = wiki_ingest_staged_docs(["docs/auth.md"], tmp_path)
    assert first.errors == []
    assert first.ingested == ["docs/auth.md"]
    second = wiki_ingest_staged_docs(["docs/auth.md"], tmp_path)
    assert second.errors == []
    assert second.ingested == []
    assert "docs/auth.md" in second.skipped
    assert second.wiki_files_written == []


def test_wiki_ingest_updates_in_place_on_content_change(tmp_path: Path) -> None:
    _ = (tmp_path / ".cortex").mkdir(parents=True)
    _bootstrap = ensure_default_wiki_layout(tmp_path)
    assert _bootstrap.wiki_root
    doc = tmp_path / "docs" / "auth.md"
    doc.parent.mkdir(parents=True)
    _ = doc.write_text("# Auth\n\nv1\n", encoding="utf-8")
    first = wiki_ingest_staged_docs(["docs/auth.md"], tmp_path)
    assert first.errors == []
    assert first.ingested == ["docs/auth.md"]
    _ = doc.write_text("# Auth\n\nv2\n", encoding="utf-8")
    second = wiki_ingest_staged_docs(["docs/auth.md"], tmp_path)
    assert second.errors == []
    assert second.ingested == ["docs/auth.md"]
    sources = tmp_path / ".cortex" / "wiki" / "sources"
    names = {p.name for p in sources.glob("docs-auth-md*.md")}
    assert "docs-auth-md.md" in names
    assert any(n.startswith("docs-auth-md-v") for n in names)
    summary = list((tmp_path / ".cortex" / "wiki" / "concepts").glob("docs-auth-md.md"))
    assert len(summary) == 1
    text = summary[0].read_text(encoding="utf-8")
    assert "v2" in text
    assert "## Revision" in text


def test_wiki_ingest_skips_dot_cortex_wiki_paths(tmp_path: Path) -> None:
    _ = (tmp_path / ".cortex").mkdir(parents=True)
    _bootstrap = ensure_default_wiki_layout(tmp_path)
    assert _bootstrap.wiki_root
    p = ".cortex/wiki/concepts/x.md"
    inner = tmp_path / p
    inner.parent.mkdir(parents=True, exist_ok=True)
    _ = inner.write_text("# X\n", encoding="utf-8")
    result = wiki_ingest_staged_docs([p], tmp_path)
    assert p in result.skipped
    assert result.ingested == []
