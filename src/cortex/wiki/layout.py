"""Create and validate the default `.cortex/wiki/` directory layout."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.models_base import StrictBaseModel
from cortex.wiki.categories import (
    WIKI_CATEGORY_DIR_ORDER,
    WIKI_INGEST_SUMMARY_CATEGORY_DIRS,
)
from cortex.wiki.wiki_root_files import WikiRootDocument

_INDEX_TEMPLATE = """## Wiki index

Catalog of wiki pages. Add a row for each page as the wiki grows.

| Page | Category | Summary | Sources |
|------|----------|---------|---------|
"""


class WikiPathKind(str, Enum):
    """Which path entry in WikiBootstrapResult lists."""

    DIRECTORY = "directory"
    FILE = "file"


class WikiBootstrapResult(StrictBaseModel):
    """Report from ``ensure_default_wiki_layout``."""

    wiki_root: str
    created: list[str]
    skipped: list[str]


def wiki_schema_document_path(project_root: Path) -> Path:
    """Return the path to `.cortex/wiki/schema.md`."""
    return (
        get_cortex_path(project_root, CortexResourceType.WIKI)
        / WikiRootDocument.SCHEMA.value
    )


def _default_schema_markdown() -> str:
    """Bundled default body for ``schema.md`` when the wiki tree is first created."""
    bundled = Path(__file__).resolve().parent / "default_wiki_schema.md"
    if bundled.is_file():
        return bundled.read_text(encoding="utf-8")
    # AI: uvx / wheel installs keep markdown next to package data, not always beside .py.
    from importlib.resources import files

    pkg = files("cortex.wiki")
    resource = pkg / "default_wiki_schema.md"
    return resource.read_text(encoding="utf-8")


def _record(
    path: Path,
    kind: WikiPathKind,
    created: list[str],
    skipped: list[str],
    *,
    existed: bool,
) -> None:
    label = f"{kind.value}:{path.as_posix()}"
    if existed:
        skipped.append(label)
    else:
        created.append(label)


def _ensure_category_trees(
    wiki_root: Path, created: list[str], skipped: list[str]
) -> None:
    for category in WIKI_CATEGORY_DIR_ORDER:
        sub = wiki_root / category.value
        existed = sub.is_dir()
        sub.mkdir(parents=True, exist_ok=True)
        keep = sub / ".gitkeep"
        keep_existed = keep.is_file()
        if not keep_existed:
            _ = keep.write_text("", encoding="utf-8")
        _record(sub, WikiPathKind.DIRECTORY, created, skipped, existed=existed)
        _record(keep, WikiPathKind.FILE, created, skipped, existed=keep_existed)


def _ensure_schema_markdown(
    wiki_root: Path, created: list[str], skipped: list[str]
) -> None:
    doc = wiki_root / WikiRootDocument.SCHEMA.value
    existed = doc.is_file()
    if not existed:
        _ = doc.write_text(_default_schema_markdown(), encoding="utf-8")
    _record(doc, WikiPathKind.FILE, created, skipped, existed=existed)


def _ensure_starter_files(
    wiki_root: Path, created: list[str], skipped: list[str]
) -> None:
    _ensure_schema_markdown(wiki_root, created, skipped)

    index_path = wiki_root / WikiRootDocument.INDEX.value
    index_existed = index_path.is_file()
    if not index_existed:
        _ = index_path.write_text(_INDEX_TEMPLATE, encoding="utf-8")
    _record(index_path, WikiPathKind.FILE, created, skipped, existed=index_existed)


def bootstrap_wiki_if_cortex_present(project_root: Path) -> WikiBootstrapResult | None:
    """Create default ``.cortex/wiki/`` when this tree is a Cortex project.

    Called after MCP resolves the attached workspace root so other projects get
    the same layout as the Cortex repo without committing ``.cortex/wiki/``.
    """
    if not get_cortex_path(project_root, CortexResourceType.CORTEX_DIR).is_dir():
        return None
    return ensure_default_wiki_layout(project_root)


def ensure_default_wiki_layout(project_root: Path) -> WikiBootstrapResult:
    """Ensure `.cortex/wiki/` exists with category dirs and starter index/schema files.

    Idempotent: existing paths are reported in ``skipped`` and left unchanged.
    """
    wiki_root = get_cortex_path(project_root, CortexResourceType.WIKI)
    created: list[str] = []
    skipped: list[str] = []

    existed_root = wiki_root.is_dir()
    wiki_root.mkdir(parents=True, exist_ok=True)
    _record(wiki_root, WikiPathKind.DIRECTORY, created, skipped, existed=existed_root)
    _ensure_category_trees(wiki_root, created, skipped)
    _ensure_starter_files(wiki_root, created, skipped)

    return WikiBootstrapResult(
        wiki_root=wiki_root.as_posix(),
        created=created,
        skipped=skipped,
    )


def expected_wiki_category_dirs() -> tuple[str, ...]:
    """Return the canonical wiki category directory names (for tests and tooling)."""
    return tuple(d.value for d in WIKI_CATEGORY_DIR_ORDER)


def wiki_scaffold_present(project_root: Path) -> bool:
    """Return True when the normative wiki schema file exists (layout bootstrapped)."""
    return wiki_schema_document_path(project_root).is_file()


def wiki_has_content(project_root: Path) -> bool:
    """Return True when any wiki *page* exists under summary categories.

    Raw snapshots under ``sources/`` do not count — ``/cortex/init-wiki`` seeds
    categorized pages; ingest may populate ``sources/`` before summaries exist.
    """
    wiki_root = get_cortex_path(project_root, CortexResourceType.WIKI)
    for cat in WIKI_INGEST_SUMMARY_CATEGORY_DIRS:
        sub = wiki_root / cat.value
        if not sub.is_dir():
            continue
        for path in sub.rglob("*.md"):
            if path.is_file():
                return True
    return False
