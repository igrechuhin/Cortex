"""Canonical discovery and unique identity indexing for plan documents."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.pydantic_extra import EXTRA_FORBID

_ARCHIVE_DIR_NAME = "archive"
_NON_PLAN_FILENAMES = frozenset(
    {"readme.md", "quick_start.md", "dependency-graph.md", "index.md"}
)
_DRAFT_MARKER = "<!-- CORTEX_STEP_PLAN_STATE\n"


class PlanFileRow(BaseModel):
    """One discovered real plan document and its lifecycle location."""

    model_config = ConfigDict(extra=EXTRA_FORBID)

    slug: str
    path: Path
    relative_path: str
    archived: bool


class PlanIdentityIndex(BaseModel):
    """Unique plan identities plus duplicate-slug diagnostics."""

    model_config = ConfigDict(extra=EXTRA_FORBID)

    unique: dict[str, PlanFileRow] = Field(default_factory=dict)
    ambiguous: dict[str, list[PlanFileRow]] = Field(default_factory=dict)


def is_plan_document(path: Path) -> bool:
    """Return whether a Markdown file is a real plan rather than scaffolding."""
    name = path.name.casefold()
    return (
        path.suffix.casefold() == ".md"
        and name not in _NON_PLAN_FILENAMES
        and not name.startswith("template")
    )


def _is_step_plan_draft(content: str) -> bool:
    marker = content.rfind(_DRAFT_MARKER)
    return marker >= 0 and content[marker:].rstrip().endswith("-->")


def _has_symlink_ancestry(path: Path, plans_dir: Path) -> bool:
    current = plans_dir
    if current.is_symlink():
        return True
    for part in path.relative_to(plans_dir).parts:
        current = current / part
        if current.is_symlink():
            return True
    return False


def iter_plan_file_rows(plans_dir: Path, *, include_archive: bool) -> list[PlanFileRow]:
    """Discover contained regular plan documents in deterministic path order."""
    if not plans_dir.is_dir() or plans_dir.is_symlink():
        return []
    rows: list[PlanFileRow] = []
    for path in plans_dir.rglob("*.md"):
        if _has_symlink_ancestry(path, plans_dir):
            continue
        if not path.is_file() or not is_plan_document(path):
            continue
        rel = path.relative_to(plans_dir)
        archived = bool(rel.parts) and rel.parts[0] == _ARCHIVE_DIR_NAME
        if archived and not include_archive:
            continue
        try:
            if _is_step_plan_draft(path.read_text(encoding="utf-8")):
                continue
        except (OSError, UnicodeError):
            continue
        rows.append(
            PlanFileRow(
                slug=path.stem,
                path=path,
                relative_path=rel.as_posix(),
                archived=archived,
            )
        )
    return sorted(rows, key=lambda row: (row.relative_path, row.slug))


def build_plan_identity_index(
    plans_dir: Path, *, include_archive: bool = True
) -> PlanIdentityIndex:
    """Group discovered plans by slug without silently selecting duplicates."""
    grouped: dict[str, list[PlanFileRow]] = {}
    for row in iter_plan_file_rows(plans_dir, include_archive=include_archive):
        grouped.setdefault(row.slug, []).append(row)
    unique: dict[str, PlanFileRow] = {}
    ambiguous: dict[str, list[PlanFileRow]] = {}
    for slug, rows in sorted(grouped.items()):
        if len(rows) == 1:
            unique[slug] = rows[0]
        else:
            ambiguous[slug] = rows
    return PlanIdentityIndex(unique=unique, ambiguous=ambiguous)


def find_plan_slug_paths(
    plans_dir: Path, slug: str, *, include_archive: bool = True
) -> list[Path]:
    """Return every real plan path matching one exact slug."""
    return [
        row.path
        for row in iter_plan_file_rows(plans_dir, include_archive=include_archive)
        if row.slug == slug
    ]
