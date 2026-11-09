"""Tests for wiki ingest routing helpers."""

from __future__ import annotations

from pathlib import Path

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.wiki.categories import WikiCategoryDir
from cortex.wiki.ingest_wiki import (
    index_catalog_linked_page_paths,
    resolve_ingest_summary_category,
    upsert_wiki_ingest_summary_for_stable_source,
    wiki_ingest_enabled,
    write_wiki_ingest_summary_and_index,
)
from cortex.wiki.layout import ensure_default_wiki_layout
from cortex.wiki.wiki_root_files import WikiRootDocument


def test_index_catalog_linked_page_paths_parses_pipe_table() -> None:
    text = (
        "| Page | Category |\n"
        "|------|----------|\n"
        "| [A](concepts/a.md) | concepts |\n"
        "| [B](entities/b.md) | entities |\n"
    )
    paths = index_catalog_linked_page_paths(text)
    assert paths == {"concepts/a.md", "entities/b.md"}


def test_resolve_ingest_summary_category_defaults_to_concepts() -> None:
    assert resolve_ingest_summary_category(None) == WikiCategoryDir.CONCEPTS.value
    assert resolve_ingest_summary_category([]) == WikiCategoryDir.CONCEPTS.value
    assert resolve_ingest_summary_category(["nope"]) == WikiCategoryDir.CONCEPTS.value


def test_resolve_ingest_summary_category_from_tags() -> None:
    assert (
        resolve_ingest_summary_category(["Entities"]) == WikiCategoryDir.ENTITIES.value
    )
    assert resolve_ingest_summary_category(["noise", "workflows"]) == (
        WikiCategoryDir.WORKFLOWS.value
    )


def test_wiki_ingest_enabled_requires_directory(tmp_path: Path) -> None:
    wiki_root = get_cortex_path(tmp_path, CortexResourceType.WIKI)
    assert wiki_ingest_enabled(wiki_root) is False
    _ = (tmp_path / ".cortex").mkdir()
    _ = ensure_default_wiki_layout(tmp_path)
    assert wiki_ingest_enabled(wiki_root) is True


def test_write_wiki_ingest_skips_index_when_row_already_present(tmp_path: Path) -> None:
    """Do not append a second index row when the page link is already cataloged."""
    _ = (tmp_path / ".cortex").mkdir()
    wiki_root = get_cortex_path(tmp_path, CortexResourceType.WIKI)
    _ = ensure_default_wiki_layout(tmp_path)
    sources = wiki_root / WikiCategoryDir.SOURCES.value
    _ = (sources / "keep.md").write_text("# Keep\n", encoding="utf-8")
    index_path = wiki_root / WikiRootDocument.INDEX.value
    existing = index_path.read_text(encoding="utf-8").rstrip() + (
        f"\n| [Keep]({WikiCategoryDir.CONCEPTS.value}/keep.md) | {WikiCategoryDir.CONCEPTS.value} | existing | [keep.md]({WikiCategoryDir.SOURCES.value}/keep.md) |\n"
    )
    _ = index_path.write_text(existing, encoding="utf-8")

    _ = write_wiki_ingest_summary_and_index(
        project_root=tmp_path,
        wiki_root=wiki_root,
        source_slug="keep",
        title="Keep Title",
        content="First line used as one-line summary.\n\nMore detail.\n",
        tags=None,
    )
    text = index_path.read_text(encoding="utf-8")
    assert text.count(f"{WikiCategoryDir.CONCEPTS.value}/keep.md") == 1
    assert "First line used as one-line summary" in (
        wiki_root / WikiCategoryDir.CONCEPTS.value / "keep.md"
    ).read_text(encoding="utf-8")


def test_stable_upsert_separates_revision_heading_with_blank_line(
    tmp_path: Path,
) -> None:
    """Stable re-ingest emits a blank line before the revision heading and one EOF newline."""
    _ = (tmp_path / ".cortex").mkdir()
    wiki_root = get_cortex_path(tmp_path, CortexResourceType.WIKI)
    _ = ensure_default_wiki_layout(tmp_path)
    sources = wiki_root / WikiCategoryDir.SOURCES.value
    _ = (sources / "doc.md").write_text("# Doc\n", encoding="utf-8")

    _ = upsert_wiki_ingest_summary_for_stable_source(
        project_root=tmp_path,
        wiki_root=wiki_root,
        source_slug="doc",
        title="Doc Title",
        content="Summary line one.\n\nMore detail.\n",
        tags=None,
        revision_note="2026-11-09: Source content changed (prior snapshot archived).",
    )
    page_path = wiki_root / WikiCategoryDir.CONCEPTS.value / "doc.md"
    page = page_path.read_text(encoding="utf-8")
    assert "\n\n## Revision\n\n" in page
    assert page.endswith("\n") and not page.endswith("\n\n")

    _ = upsert_wiki_ingest_summary_for_stable_source(
        project_root=tmp_path,
        wiki_root=wiki_root,
        source_slug="doc",
        title="Doc Title",
        content="Summary line one.\n\nMore detail.\n",
        tags=None,
        revision_note=None,
    )
    assert page_path.read_text(encoding="utf-8") == page
