"""Slug allocation for `.cortex/memory-bank/sources/` files."""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath


def slugify_title(title: str) -> str:
    """Turn a title into a filesystem-safe slug (lowercase, hyphen-separated)."""
    lowered = title.lower().strip()
    # AI: Collapse punctuation and whitespace to single hyphens so titles with
    # slashes or special characters still produce stable, reviewable filenames.
    slug = re.sub(r"[^a-z0-9]+", "-", lowered)
    slug = slug.strip("-")
    return slug or "untitled"


def slugify_repo_rel_path(rel: str) -> str:
    """Stable slug from a repo-relative path (used for idempotent wiki ingest)."""
    norm = PurePosixPath(rel.replace("\\", "/")).as_posix().lstrip("./")
    return slugify_title(norm)


def allocate_unique_source_path(sources_dir: Path, base_slug: str) -> tuple[str, Path]:
    """Return ``(slug_used, path)`` for a new file that does not yet exist.

    If ``{base_slug}.md`` exists, tries ``{base_slug}-2.md``, ``-3``, … per plan.
    """
    candidate_slug = base_slug
    suffix = 2
    while True:
        path = sources_dir / f"{candidate_slug}.md"
        if not path.exists():
            return candidate_slug, path
        candidate_slug = f"{base_slug}-{suffix}"
        suffix += 1
