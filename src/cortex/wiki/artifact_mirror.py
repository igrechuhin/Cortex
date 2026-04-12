"""Mirror selected memory-bank artifacts into ``.cortex/wiki/analyses/``."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.artifacts.artifact_types import (
    ArtifactType,
    get_artifact_type_metadata,
)
from cortex.tools.files.artifact_operations import FileArtifactParams
from cortex.wiki.categories import WikiCategoryDir
from cortex.wiki.ingest_wiki import (
    append_wiki_catalog_row,
    wiki_catalog_summary_line,
    wiki_ingest_enabled,
)


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return normalized or "artifact"


def _dedupe_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    counter = 2
    while True:
        candidate = path.with_name(f"{stem}-{counter}{suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def _artifact_frontmatter(
    *,
    title: str,
    category: str,
    iso: str,
    tags: list[str] | None,
) -> str:
    lines = [
        "---",
        f"title: {json.dumps(title)}",
        f"category: {json.dumps(category)}",
        f"last_updated: {json.dumps(iso)}",
    ]
    if tags:
        lines.append("tags:")
        for t in tags:
            lines.append(f"  - {json.dumps(t)}")
    lines.append("---")
    return "\n".join(lines)


def _is_wiki_mirror_candidate(params: FileArtifactParams) -> bool:
    return params.artifact_type in (
        ArtifactType.REVIEW_REPORT,
        ArtifactType.SESSION_ANALYSIS,
    )


def _allocate_wiki_mirror_path(wiki_root: Path, params: FileArtifactParams) -> Path:
    metadata = get_artifact_type_metadata(params.artifact_type)
    slug = _slugify(params.title)
    date_iso = datetime.now(tz=UTC).date().isoformat()
    file_name = metadata.filename_template.format(slug=slug, date=date_iso)
    analyses_dir = wiki_root / WikiCategoryDir.ANALYSES.value
    analyses_dir.mkdir(parents=True, exist_ok=True)
    return _dedupe_path(analyses_dir / file_name)


def _write_wiki_mirror_page(target: Path, params: FileArtifactParams, iso: str) -> None:
    # AI: Body is the agent-authored report; frontmatter satisfies wiki schema for tooling.
    fm = _artifact_frontmatter(
        title=params.title,
        category=WikiCategoryDir.ANALYSES.value,
        iso=iso,
        tags=params.tags,
    )
    _write_markdown_atomic(target, f"{fm}\n\n{params.content}")


def _register_wiki_mirror_index(
    wiki_root: Path, target: Path, params: FileArtifactParams
) -> None:
    page_rel = target.relative_to(wiki_root).as_posix()
    one_line = wiki_catalog_summary_line(params.title, params.content)
    append_wiki_catalog_row(
        wiki_root,
        page_rel_posix=page_rel,
        title=params.title,
        category=WikiCategoryDir.ANALYSES.value,
        summary=one_line,
        sources_cell="memory-bank artifact mirror",
    )


def mirror_file_artifact_to_wiki_if_enabled(
    project_root: Path, params: FileArtifactParams
) -> Path | None:
    """When wiki is present, copy review / session-analysis artifacts into wiki analyses.

    Returns the wiki path written, or None when mirroring is skipped.
    """
    if not _is_wiki_mirror_candidate(params):
        return None
    wiki_root = get_cortex_path(project_root, CortexResourceType.WIKI)
    if not wiki_ingest_enabled(wiki_root):
        return None
    target = _allocate_wiki_mirror_path(wiki_root, params)
    iso = datetime.now(tz=UTC).date().isoformat()
    _write_wiki_mirror_page(target, params, iso)
    _register_wiki_mirror_index(wiki_root, target, params)
    return target


def _write_markdown_atomic(path: Path, body: str) -> None:
    tmp = path.with_suffix(f"{path.suffix}.tmp")
    _ = tmp.write_text(body, encoding="utf-8")
    _ = tmp.replace(path)
