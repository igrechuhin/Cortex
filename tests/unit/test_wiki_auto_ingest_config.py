"""Tests for wiki auto-ingest pattern configuration."""

from __future__ import annotations

from pathlib import Path

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.wiki.auto_ingest_config import (
    DEFAULT_AUTO_INGEST_PATTERNS,
    load_auto_ingest_patterns,
    paths_matching_patterns,
)
from cortex.wiki.layout import ensure_default_wiki_layout


def test_default_auto_ingest_patterns_non_empty() -> None:
    assert DEFAULT_AUTO_INGEST_PATTERNS
    for pat in DEFAULT_AUTO_INGEST_PATTERNS:
        assert isinstance(pat, str)
        assert pat.strip()


def test_load_auto_ingest_patterns_fallback_without_schema(tmp_path: Path) -> None:
    assert load_auto_ingest_patterns(tmp_path) == list(DEFAULT_AUTO_INGEST_PATTERNS)


def test_load_auto_ingest_patterns_from_schema_frontmatter(tmp_path: Path) -> None:
    _ = (tmp_path / ".cortex").mkdir(parents=True)
    _bootstrap = ensure_default_wiki_layout(tmp_path)
    assert _bootstrap.wiki_root
    wiki = get_cortex_path(tmp_path, CortexResourceType.WIKI)
    custom = ["README.md", "custom/**/*.md"]
    fm = (
        "---\nauto_ingest_patterns:\n  - README.md\n  - custom/**/*.md\n---\n\n# body\n"
    )
    _bytes = (wiki / "schema.md").write_text(fm, encoding="utf-8")
    assert _bytes > 0
    assert load_auto_ingest_patterns(tmp_path) == custom


def test_paths_matching_patterns_docs_glob(tmp_path: Path) -> None:
    d = tmp_path / "docs" / "nested"
    d.mkdir(parents=True)
    f = d / "a.md"
    _ = f.write_text("# A\n", encoding="utf-8")
    matched = paths_matching_patterns(tmp_path, ["docs/**/*.md"])
    assert "docs/nested/a.md" in matched


def test_paths_matching_readme_star(tmp_path: Path) -> None:
    _ = (tmp_path / "README.md").write_text("# R\n", encoding="utf-8")
    _ = (tmp_path / "README.ja.md").write_text("# R\n", encoding="utf-8")
    matched = paths_matching_patterns(tmp_path, ["README*.md"])
    assert "README.md" in matched
    assert "README.ja.md" in matched
