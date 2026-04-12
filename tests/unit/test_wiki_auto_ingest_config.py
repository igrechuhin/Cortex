"""Tests for wiki auto-ingest pattern configuration."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

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


def test_load_auto_ingest_patterns_no_closing_fence(tmp_path: Path) -> None:
    """Schema with unclosed ``---`` frontmatter falls back to defaults."""
    _ = (tmp_path / ".cortex").mkdir(parents=True)
    _bootstrap = ensure_default_wiki_layout(tmp_path)
    assert _bootstrap.wiki_root
    wiki = get_cortex_path(tmp_path, CortexResourceType.WIKI)
    _ = (wiki / "schema.md").write_text(
        "---\ntitle: no close fence\n", encoding="utf-8"
    )
    assert load_auto_ingest_patterns(tmp_path) == list(DEFAULT_AUTO_INGEST_PATTERNS)


def test_load_auto_ingest_patterns_schema_no_frontmatter(tmp_path: Path) -> None:
    """Schema file that does not start with ``---`` falls back to defaults (line 26)."""
    _ = (tmp_path / ".cortex").mkdir(parents=True)
    _bootstrap = ensure_default_wiki_layout(tmp_path)
    assert _bootstrap.wiki_root
    wiki = get_cortex_path(tmp_path, CortexResourceType.WIKI)
    _ = (wiki / "schema.md").write_text("# No frontmatter here\n", encoding="utf-8")
    assert load_auto_ingest_patterns(tmp_path) == list(DEFAULT_AUTO_INGEST_PATTERNS)


def test_load_auto_ingest_patterns_empty_yaml_block(tmp_path: Path) -> None:
    """Schema with whitespace-only content between fences falls back to defaults (line 33)."""
    _ = (tmp_path / ".cortex").mkdir(parents=True)
    _bootstrap = ensure_default_wiki_layout(tmp_path)
    assert _bootstrap.wiki_root
    wiki = get_cortex_path(tmp_path, CortexResourceType.WIKI)
    # "---\n   \n---" — fences present, block strips to empty string → hits line 33
    _ = (wiki / "schema.md").write_text("---\n   \n---\n\n# body\n", encoding="utf-8")
    assert load_auto_ingest_patterns(tmp_path) == list(DEFAULT_AUTO_INGEST_PATTERNS)


def test_load_auto_ingest_patterns_non_dict_yaml(tmp_path: Path) -> None:
    """Schema with YAML scalar (not a mapping) falls back to defaults."""
    _ = (tmp_path / ".cortex").mkdir(parents=True)
    _bootstrap = ensure_default_wiki_layout(tmp_path)
    assert _bootstrap.wiki_root
    wiki = get_cortex_path(tmp_path, CortexResourceType.WIKI)
    _ = (wiki / "schema.md").write_text(
        "---\njust a string\n---\n\n# body\n", encoding="utf-8"
    )
    assert load_auto_ingest_patterns(tmp_path) == list(DEFAULT_AUTO_INGEST_PATTERNS)


def test_load_auto_ingest_patterns_non_list_value(tmp_path: Path) -> None:
    """``auto_ingest_patterns`` present but not a list falls back to defaults."""
    _ = (tmp_path / ".cortex").mkdir(parents=True)
    _bootstrap = ensure_default_wiki_layout(tmp_path)
    assert _bootstrap.wiki_root
    wiki = get_cortex_path(tmp_path, CortexResourceType.WIKI)
    fm = "---\nauto_ingest_patterns: not-a-list\n---\n\n# body\n"
    _ = (wiki / "schema.md").write_text(fm, encoding="utf-8")
    assert load_auto_ingest_patterns(tmp_path) == list(DEFAULT_AUTO_INGEST_PATTERNS)


def test_load_auto_ingest_patterns_empty_list_falls_back(tmp_path: Path) -> None:
    """``auto_ingest_patterns: []`` falls back to defaults (empty list is not useful)."""
    _ = (tmp_path / ".cortex").mkdir(parents=True)
    _bootstrap = ensure_default_wiki_layout(tmp_path)
    assert _bootstrap.wiki_root
    wiki = get_cortex_path(tmp_path, CortexResourceType.WIKI)
    fm = "---\nauto_ingest_patterns: []\n---\n\n# body\n"
    _ = (wiki / "schema.md").write_text(fm, encoding="utf-8")
    assert load_auto_ingest_patterns(tmp_path) == list(DEFAULT_AUTO_INGEST_PATTERNS)


def test_paths_matching_patterns_skips_value_error(tmp_path: Path) -> None:
    """Paths that raise ValueError in relative_to are silently skipped (lines 68-69)."""
    f = tmp_path / "README.md"
    _ = f.write_text("# R\n", encoding="utf-8")

    real_relative_to = Path.relative_to

    def raise_for_target(
        self: Path,
        other: Path | str,
        /,
        *,
        walk_up: bool = False,
    ) -> Path:
        if self == f:
            raise ValueError("simulated outside-root path")
        return real_relative_to(self, other, walk_up=walk_up)

    with patch.object(Path, "relative_to", raise_for_target):
        matched = paths_matching_patterns(tmp_path, ["README*.md"])
    assert "README.md" not in matched
