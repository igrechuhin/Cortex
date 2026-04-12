"""Tests for ``wiki_ingest_staged_docs``."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from cortex.tools.wiki import staged_ingest as staged_ingest_mod
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


def test_wiki_ingest_deduplicates_staged_paths(tmp_path: Path) -> None:
    _ = (tmp_path / ".cortex").mkdir(parents=True)
    _bootstrap = ensure_default_wiki_layout(tmp_path)
    assert _bootstrap.wiki_root
    doc = tmp_path / "docs" / "once.md"
    doc.parent.mkdir(parents=True)
    _ = doc.write_text("# One\n\nbody\n", encoding="utf-8")
    result = wiki_ingest_staged_docs(["docs/once.md", "docs/once.md"], tmp_path)
    assert result.ingested == ["docs/once.md"]
    assert result.errors == []


def test_wiki_ingest_skips_empty_file(tmp_path: Path) -> None:
    _ = (tmp_path / ".cortex").mkdir(parents=True)
    _bootstrap = ensure_default_wiki_layout(tmp_path)
    assert _bootstrap.wiki_root
    doc = tmp_path / "docs" / "empty.md"
    doc.parent.mkdir(parents=True)
    _ = doc.write_text("   \n\t\n", encoding="utf-8")
    result = wiki_ingest_staged_docs(["docs/empty.md"], tmp_path)
    assert result.ingested == []
    assert "docs/empty.md" in result.skipped


def test_wiki_ingest_errors_on_path_escape(tmp_path: Path) -> None:
    _ = (tmp_path / ".cortex").mkdir(parents=True)
    _bootstrap = ensure_default_wiki_layout(tmp_path)
    assert _bootstrap.wiki_root
    with patch.object(
        staged_ingest_mod,
        "paths_matching_patterns",
        return_value={"docs/../secret.md"},
    ):
        result = wiki_ingest_staged_docs(["docs/../secret.md"], tmp_path)
    assert result.ingested == []
    assert any("path escapes root" in e for e in result.errors)


def test_wiki_ingest_errors_when_eligible_file_missing(tmp_path: Path) -> None:
    _ = (tmp_path / ".cortex").mkdir(parents=True)
    _bootstrap = ensure_default_wiki_layout(tmp_path)
    assert _bootstrap.wiki_root
    with patch.object(
        staged_ingest_mod,
        "paths_matching_patterns",
        return_value={"docs/missing.md"},
    ):
        result = wiki_ingest_staged_docs(["docs/missing.md"], tmp_path)
    assert result.ingested == []
    assert any("not a file" in e for e in result.errors)


def test_wiki_ingest_errors_on_read_oserror(tmp_path: Path) -> None:
    _ = (tmp_path / ".cortex").mkdir(parents=True)
    _bootstrap = ensure_default_wiki_layout(tmp_path)
    assert _bootstrap.wiki_root
    doc = tmp_path / "docs" / "blocked.md"
    doc.parent.mkdir(parents=True)
    _ = doc.write_text("# B\n\nx\n", encoding="utf-8")
    real_read_text = Path.read_text

    def selective_read(
        self: Path,
        encoding: str | None = None,
        errors: str | None = None,
        newline: str | None = None,
    ) -> str:
        if self.resolve() == doc.resolve():
            raise OSError("denied")
        return real_read_text(self, encoding=encoding, errors=errors, newline=newline)

    with patch.object(Path, "read_text", selective_read):
        result = wiki_ingest_staged_docs(["docs/blocked.md"], tmp_path)
    assert result.ingested == []
    assert any("read failed" in e for e in result.errors)


def test_wiki_ingest_title_fallback_without_heading(tmp_path: Path) -> None:
    _ = (tmp_path / ".cortex").mkdir(parents=True)
    _bootstrap = ensure_default_wiki_layout(tmp_path)
    assert _bootstrap.wiki_root
    doc = tmp_path / "docs" / "plain-prose.md"
    doc.parent.mkdir(parents=True)
    _ = doc.write_text("no hash lines at all\n", encoding="utf-8")
    result = wiki_ingest_staged_docs(["docs/plain-prose.md"], tmp_path)
    assert result.errors == []
    assert result.ingested == ["docs/plain-prose.md"]


def test_wiki_ingest_skips_only_hash_heading_lines(tmp_path: Path) -> None:
    _ = (tmp_path / ".cortex").mkdir(parents=True)
    _bootstrap = ensure_default_wiki_layout(tmp_path)
    assert _bootstrap.wiki_root
    doc = tmp_path / "docs" / "hash-only.md"
    doc.parent.mkdir(parents=True)
    _ = doc.write_text("\n##\n###   \n\nbody after blanks\n", encoding="utf-8")
    result = wiki_ingest_staged_docs(["docs/hash-only.md"], tmp_path)
    assert result.errors == []
    assert result.ingested == ["docs/hash-only.md"]


def test_wiki_ingest_errors_on_invalid_ingest_json(tmp_path: Path) -> None:
    _ = (tmp_path / ".cortex").mkdir(parents=True)
    _bootstrap = ensure_default_wiki_layout(tmp_path)
    assert _bootstrap.wiki_root
    doc = tmp_path / "docs" / "bad-json.md"
    doc.parent.mkdir(parents=True)
    _ = doc.write_text("# X\n\ny\n", encoding="utf-8")
    with patch.object(
        staged_ingest_mod,
        "ingest_source_at_project_root",
        return_value="not json",
    ):
        result = wiki_ingest_staged_docs(["docs/bad-json.md"], tmp_path)
    assert result.ingested == []
    assert any("invalid JSON" in e for e in result.errors)


def test_wiki_ingest_errors_on_non_dict_ingest_payload(tmp_path: Path) -> None:
    _ = (tmp_path / ".cortex").mkdir(parents=True)
    _bootstrap = ensure_default_wiki_layout(tmp_path)
    assert _bootstrap.wiki_root
    doc = tmp_path / "docs" / "list-payload.md"
    doc.parent.mkdir(parents=True)
    _ = doc.write_text("# X\n\ny\n", encoding="utf-8")
    with patch.object(
        staged_ingest_mod,
        "ingest_source_at_project_root",
        return_value='["unexpected"]',
    ):
        result = wiki_ingest_staged_docs(["docs/list-payload.md"], tmp_path)
    assert result.ingested == []
    assert any("unexpected payload" in e for e in result.errors)


def test_wiki_ingest_errors_on_ingest_failure_status(tmp_path: Path) -> None:
    _ = (tmp_path / ".cortex").mkdir(parents=True)
    _bootstrap = ensure_default_wiki_layout(tmp_path)
    assert _bootstrap.wiki_root
    doc = tmp_path / "docs" / "fail-ingest.md"
    doc.parent.mkdir(parents=True)
    _ = doc.write_text("# X\n\ny\n", encoding="utf-8")
    with patch.object(
        staged_ingest_mod,
        "ingest_source_at_project_root",
        return_value='{"status": "error", "error": "boom"}',
    ):
        result = wiki_ingest_staged_docs(["docs/fail-ingest.md"], tmp_path)
    assert result.ingested == []
    assert any("boom" in e for e in result.errors)


def test_wiki_ingest_errors_on_non_string_ingest_error_field(tmp_path: Path) -> None:
    _ = (tmp_path / ".cortex").mkdir(parents=True)
    _bootstrap = ensure_default_wiki_layout(tmp_path)
    assert _bootstrap.wiki_root
    doc = tmp_path / "docs" / "weird-err.md"
    doc.parent.mkdir(parents=True)
    _ = doc.write_text("# X\n\ny\n", encoding="utf-8")
    with patch.object(
        staged_ingest_mod,
        "ingest_source_at_project_root",
        return_value='{"status": "error", "error": {"nested": true}}',
    ):
        result = wiki_ingest_staged_docs(["docs/weird-err.md"], tmp_path)
    assert result.ingested == []
    assert any("unknown error" in e for e in result.errors)
