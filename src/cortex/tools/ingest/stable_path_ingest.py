"""Idempotent ingest keyed by repo-relative path (commit-time wiki staged ingest)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from cortex.core.models import ModelDict
from cortex.tools.ingest.slug import slugify_repo_rel_path
from cortex.tools.ingest.source_types import IngestSource
from cortex.tools.response_builder import error_response, success_response
from cortex.wiki.ingest_wiki import (
    WikiIngestWriteResult,
    resolve_ingest_summary_category,
    upsert_wiki_ingest_summary_for_stable_source,
)


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f"{path.suffix}.tmp")
    _ = tmp.write_text(content, encoding="utf-8")
    _ = tmp.replace(path)


def _write_source_or_json_error(dest: Path, content: str) -> str | None:
    try:
        _atomic_write(dest, content)
    except OSError as exc:
        return json.dumps(
            error_response(
                error=f"Failed to write source file: {exc}", error_code="write_error"
            ),
            indent=2,
        )
    return None


def _archive_prior_raw_to_versioned(sources_dir: Path, stable_slug: str) -> str | None:
    main = sources_dir / f"{stable_slug}.md"
    if not main.is_file():
        return None
    n = 2
    while (sources_dir / f"{stable_slug}-v{n}.md").is_file():
        n += 1
    archive_name = f"{stable_slug}-v{n}.md"
    _atomic_write(sources_dir / archive_name, main.read_text(encoding="utf-8"))
    return archive_name


def _json_response_unchanged(
    project_root: Path,
    *,
    stable_slug: str,
    dest: Path,
    payload: IngestSource,
    use_wiki: bool,
) -> str:
    base = success_response(
        slug=stable_slug,
        source_path=str(dest.relative_to(project_root)).replace("\\", "/"),
        title=payload.title,
        source_type=payload.type.value,
        ingest_target="wiki" if use_wiki else "memory_bank",
        ingest_outcome="unchanged",
    )
    if payload.tags is not None:
        base["tags"] = list(payload.tags)
    if use_wiki:
        cat = resolve_ingest_summary_category(
            list(payload.tags) if payload.tags is not None else None
        )
        base["wiki_summary_path"] = f".cortex/wiki/{cat}/{stable_slug}.md"
        base["wiki_category"] = cat
    return json.dumps(base, indent=2)


def _revision_note_for_archive(archived_name: str) -> str:
    iso = datetime.now(tz=UTC).date().isoformat()
    return (
        f"{iso}: Source content changed "
        f"(prior snapshot archived as sources/{archived_name})."
    )


def _wiki_upsert_or_error_json(
    project_root: Path,
    wiki_root: Path,
    *,
    stable_slug: str,
    payload: IngestSource,
    revision_note: str | None,
) -> WikiIngestWriteResult | str:
    try:
        return upsert_wiki_ingest_summary_for_stable_source(
            project_root=project_root,
            wiki_root=wiki_root,
            source_slug=stable_slug,
            title=payload.title,
            content=payload.content,
            tags=list(payload.tags) if payload.tags is not None else None,
            revision_note=revision_note,
        )
    except OSError as exc:
        return json.dumps(
            error_response(
                error=f"Failed to write wiki summary or index: {exc}",
                error_code="write_error",
            ),
            indent=2,
        )


def _attach_wiki_to_stable_success_base(
    base: ModelDict,
    project_root: Path,
    wiki_root: Path,
    stable_slug: str,
    payload: IngestSource,
    archived_name: str | None,
) -> str:
    note = _revision_note_for_archive(archived_name) if archived_name else None
    wiki_part = _wiki_upsert_or_error_json(
        project_root,
        wiki_root,
        stable_slug=stable_slug,
        payload=payload,
        revision_note=note,
    )
    if isinstance(wiki_part, str):
        return wiki_part
    base["wiki_summary_path"] = wiki_part.summary_project_posix
    base["wiki_category"] = wiki_part.summary_category
    return json.dumps(base, indent=2)


def _stable_ingest_success_payload_json(
    project_root: Path,
    wiki_root: Path,
    use_wiki: bool,
    dest: Path,
    stable_slug: str,
    payload: IngestSource,
    archived_name: str | None,
) -> str:
    base = success_response(
        slug=stable_slug,
        source_path=str(dest.relative_to(project_root)).replace("\\", "/"),
        title=payload.title,
        source_type=payload.type.value,
        ingest_target="wiki" if use_wiki else "memory_bank",
    )
    if payload.tags is not None:
        base["tags"] = list(payload.tags)
    if not use_wiki:
        return json.dumps(base, indent=2)
    return _attach_wiki_to_stable_success_base(
        base, project_root, wiki_root, stable_slug, payload, archived_name
    )


def _stable_slug_dest_or_error_json(
    sources_dir: Path, payload: IngestSource
) -> tuple[str | None, str | None, Path | None]:
    raw_rel = (payload.stable_ingest_rel or "").strip()
    if not raw_rel:
        return (
            json.dumps(
                error_response(
                    error="stable_ingest_rel must be a non-empty repo-relative path",
                    error_code="invalid_stable_rel",
                ),
                indent=2,
            ),
            None,
            None,
        )
    stable_slug = slugify_repo_rel_path(raw_rel)
    return None, stable_slug, sources_dir / f"{stable_slug}.md"


def _stable_write_raw_and_finish_json(
    project_root: Path,
    wiki_root: Path,
    sources_dir: Path,
    use_wiki: bool,
    stable_slug: str,
    dest: Path,
    payload: IngestSource,
) -> str:
    archived_name = (
        _archive_prior_raw_to_versioned(sources_dir, stable_slug)
        if dest.is_file()
        else None
    )
    err = _write_source_or_json_error(dest, payload.content)
    if err is not None:
        return err
    return _stable_ingest_success_payload_json(
        project_root,
        wiki_root,
        use_wiki,
        dest,
        stable_slug,
        payload,
        archived_name,
    )


def ingest_source_with_stable_rel_path(
    project_root: Path,
    wiki_root: Path,
    sources_dir: Path,
    use_wiki: bool,
    payload: IngestSource,
) -> str:
    # AI: Stable path ingest supports commit-time wiki refresh without duplicating pages.
    err_json, stable_slug, dest = _stable_slug_dest_or_error_json(sources_dir, payload)
    if err_json is not None:
        return err_json
    assert stable_slug is not None and dest is not None
    if dest.is_file() and dest.read_text(encoding="utf-8") == payload.content:
        return _json_response_unchanged(
            project_root,
            stable_slug=stable_slug,
            dest=dest,
            payload=payload,
            use_wiki=use_wiki,
        )
    return _stable_write_raw_and_finish_json(
        project_root, wiki_root, sources_dir, use_wiki, stable_slug, dest, payload
    )
