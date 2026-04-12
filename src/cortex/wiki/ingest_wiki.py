"""Wiki routing for MCP ``ingest`` when ``.cortex/wiki/`` exists."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from cortex.tools.ingest.slug import allocate_unique_source_path
from cortex.wiki.categories import (
    WIKI_INGEST_SUMMARY_CATEGORY_DIRS,
    WikiCategoryDir,
)
from cortex.wiki.wiki_root_files import WikiRootDocument

# AI: Summary pages never land in ``sources/`` (immutable raw only) or ``WikiRootDocument`` files.
_WIKI_SUMMARY_CATEGORY_VALUES: frozenset[str] = frozenset(
    d.value for d in WIKI_INGEST_SUMMARY_CATEGORY_DIRS
)


def wiki_ingest_enabled(wiki_root: Path) -> bool:
    """Return True when the wiki tree is present (ingest writes wiki + memory-bank policy)."""
    return wiki_root.is_dir()


def resolve_ingest_summary_category(tags: list[str] | None) -> str:
    """Pick a category dir for the auto-generated ingest summary page."""
    if tags:
        for raw in tags:
            norm = raw.strip().lower()
            if norm in _WIKI_SUMMARY_CATEGORY_VALUES:
                return norm
    return WikiCategoryDir.CONCEPTS.value


def _strip_table_cell(value: str) -> str:
    """Remove characters that break the pipe table in the wiki catalog file."""
    collapsed = " ".join(value.split())
    cleaned = collapsed.replace("|", "/")
    if len(cleaned) > 200:
        return f"{cleaned[:197]}..."
    return cleaned


def wiki_catalog_summary_line(title: str, content: str) -> str:
    """Public wrapper for index and wiki mirror one-line summaries."""
    return _first_summary_line(title, content)


def _first_summary_line(title: str, content: str) -> str:
    """Derive a single-line summary from title + body (no LLM)."""
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            stripped = stripped.lstrip("#").strip()
        if stripped.casefold() == title.strip().casefold():
            continue
        return _strip_table_cell(stripped)
    return _strip_table_cell(title)


_INDEX_ROW_PATTERN = re.compile(
    r"\|\s*\[[^\]]+\]\((?P<rel>[^)]+)\)\s*\|", re.IGNORECASE
)


def _index_already_lists_page(index_text: str, page_rel_posix: str) -> bool:
    for m in _INDEX_ROW_PATTERN.finditer(index_text):
        if m.group("rel").replace("\\", "/") == page_rel_posix:
            return True
    return False


def index_catalog_linked_page_paths(index_text: str) -> set[str]:
    """Wiki-root-relative paths linked from the catalog ``WikiRootDocument.INDEX`` table."""
    return {
        m.group("rel").strip().replace("\\", "/")
        for m in _INDEX_ROW_PATTERN.finditer(index_text)
    }


def _append_index_row_atomic(wiki_root: Path, row: str) -> None:
    index_path = wiki_root / WikiRootDocument.INDEX.value
    text = index_path.read_text(encoding="utf-8") if index_path.is_file() else ""
    if not text.endswith("\n"):
        text += "\n"
    updated = f"{text}{row}"
    tmp_path = index_path.with_suffix(f"{index_path.suffix}.tmp")
    _ = tmp_path.write_text(updated, encoding="utf-8")
    _ = tmp_path.replace(index_path)


def append_wiki_catalog_row(
    wiki_root: Path,
    *,
    page_rel_posix: str,
    title: str,
    category: str,
    summary: str,
    sources_cell: str,
) -> None:
    """Append one catalog row when ``page_rel_posix`` is not already linked."""
    index_path = wiki_root / WikiRootDocument.INDEX.value
    index_text = index_path.read_text(encoding="utf-8") if index_path.is_file() else ""
    if _index_already_lists_page(index_text, page_rel_posix):
        return
    row = (
        f"| [{_strip_table_cell(title)}]({page_rel_posix}) | {category} | "
        f"{_strip_table_cell(summary)} | {_strip_table_cell(sources_cell)} |\n"
    )
    _append_index_row_atomic(wiki_root, row)


@dataclass(frozen=True)
class WikiIngestWriteResult:
    """Paths written under ``.cortex/wiki/`` for one ingest call."""

    summary_category: str
    summary_project_posix: str
    source_project_posix: str


def _frontmatter_lines(
    title: str, category: str, iso: str, tags: list[str] | None
) -> list[str]:
    lines = [
        "---",
        f"title: {json.dumps(title)}",
        f"category: {category}",
        "source_count: 1",
        f"last_updated: {json.dumps(iso)}",
    ]
    if tags:
        lines.append("tags:")
        for t in tags:
            lines.append(f"  - {json.dumps(t)}")
    lines.append("---")
    return lines


def _build_summary_page_markdown(
    *,
    title: str,
    category: str,
    iso: str,
    tags: list[str] | None,
    source_slug: str,
    content: str,
) -> tuple[str, str]:
    """Return ``(markdown_body, one_line_summary)``."""
    rel = f"../{WikiCategoryDir.SOURCES.value}/{source_slug}.md"
    one_line = _first_summary_line(title, content)
    fm = "\n".join(_frontmatter_lines(title, category, iso, tags))
    body = (
        f"{fm}\n\n# {title}\n\nIngested source: "
        f"[{source_slug}.md]({rel})\n\n## Summary\n\n{one_line}\n"
    )
    return body, one_line


def _write_markdown_atomic(path: Path, body: str) -> None:
    tmp = path.with_suffix(f"{path.suffix}.tmp")
    _ = tmp.write_text(body, encoding="utf-8")
    _ = tmp.replace(path)


def _append_index_if_needed(
    wiki_root: Path,
    summary_path: Path,
    title: str,
    category: str,
    one_line: str,
    source_slug: str,
) -> None:
    page_rel = summary_path.relative_to(wiki_root).as_posix()
    index_text = (wiki_root / WikiRootDocument.INDEX.value).read_text(encoding="utf-8")
    if _index_already_lists_page(index_text, page_rel):
        return
    src = f"{WikiCategoryDir.SOURCES.value}/{source_slug}.md"
    row = (
        f"| [{title}]({page_rel}) | {category} | {one_line} | "
        f"[{source_slug}.md]({src}) |\n"
    )
    _append_index_row_atomic(wiki_root, row)


def _wiki_ingest_write_result(
    project_root: Path,
    wiki_root: Path,
    summary_path: Path,
    category: str,
    source_slug: str,
) -> WikiIngestWriteResult:
    summary_rel = summary_path.relative_to(project_root).as_posix()
    raw = wiki_root / WikiCategoryDir.SOURCES.value / f"{source_slug}.md"
    source_rel = raw.relative_to(project_root).as_posix()
    return WikiIngestWriteResult(
        summary_category=category,
        summary_project_posix=summary_rel.replace("\\", "/"),
        source_project_posix=source_rel.replace("\\", "/"),
    )


def _revision_markdown_block(bullets: list[str]) -> str:
    if not bullets:
        return ""
    return "\n## Revision\n\n" + "\n".join(f"- {b}" for b in bullets) + "\n"


def _parse_revision_bullets(text: str) -> list[str]:
    needle = "\n## Revision\n"
    if needle not in text:
        return []
    part = text.split(needle, 1)[1]
    out: list[str] = []
    for line in part.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            out.append(stripped[2:].strip())
    return out


def _stable_summary_path_and_category(
    wiki_root: Path, source_slug: str, tags: list[str] | None
) -> tuple[Path, str]:
    category = resolve_ingest_summary_category(tags)
    category_dir = wiki_root / category
    category_dir.mkdir(parents=True, exist_ok=True)
    return category_dir / f"{source_slug}.md", category


def _stable_upsert_markdown_body(
    summary_path: Path,
    *,
    source_slug: str,
    title: str,
    category: str,
    tags: list[str] | None,
    content: str,
    revision_note: str | None,
) -> tuple[str, str]:
    iso = datetime.now(tz=UTC).date().isoformat()
    body, one_line = _build_summary_page_markdown(
        title=title,
        category=category,
        iso=iso,
        tags=tags,
        source_slug=source_slug,
        content=content,
    )
    prior = summary_path.read_text(encoding="utf-8") if summary_path.is_file() else ""
    bullets = _parse_revision_bullets(prior)
    if revision_note is not None:
        bullets.append(revision_note)
    final_body = f"{body.rstrip()}{_revision_markdown_block(bullets)}\n"
    return final_body, one_line


def upsert_wiki_ingest_summary_for_stable_source(
    *,
    project_root: Path,
    wiki_root: Path,
    source_slug: str,
    title: str,
    content: str,
    tags: list[str] | None,
    revision_note: str | None,
) -> WikiIngestWriteResult:
    """Write or replace the summary page at ``{category}/{source_slug}.md`` (stable-ingest path)."""
    summary_path, category = _stable_summary_path_and_category(
        wiki_root, source_slug, tags
    )
    final_body, one_line = _stable_upsert_markdown_body(
        summary_path,
        source_slug=source_slug,
        title=title,
        category=category,
        tags=tags,
        content=content,
        revision_note=revision_note,
    )
    _write_markdown_atomic(summary_path, final_body)
    _append_index_if_needed(
        wiki_root, summary_path, title, category, one_line, source_slug
    )
    return _wiki_ingest_write_result(
        project_root, wiki_root, summary_path, category, source_slug
    )


def write_wiki_ingest_summary_and_index(
    *,
    project_root: Path,
    wiki_root: Path,
    source_slug: str,
    title: str,
    content: str,
    tags: list[str] | None,
) -> WikiIngestWriteResult:
    """Create summary page and catalog row; raw ``sources/{slug}.md`` must exist."""
    category = resolve_ingest_summary_category(tags)
    category_dir = wiki_root / category
    category_dir.mkdir(parents=True, exist_ok=True)
    _, summary_path = allocate_unique_source_path(category_dir, source_slug)
    iso = datetime.now(tz=UTC).date().isoformat()
    body, one_line = _build_summary_page_markdown(
        title=title,
        category=category,
        iso=iso,
        tags=tags,
        source_slug=source_slug,
        content=content,
    )
    _write_markdown_atomic(summary_path, body)
    _append_index_if_needed(
        wiki_root, summary_path, title, category, one_line, source_slug
    )
    return _wiki_ingest_write_result(
        project_root, wiki_root, summary_path, category, source_slug
    )
