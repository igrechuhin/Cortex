"""Ingest staged markdown docs into the project wiki (commit pipeline helper)."""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from typing import NamedTuple, cast

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.ingest.ingest_handler import ingest_source_at_project_root
from cortex.tools.ingest.source_types import IngestSource, SourceType
from cortex.tools.wiki.auto_ingest_config import (
    load_auto_ingest_patterns,
    paths_matching_patterns,
)
from cortex.wiki.ingest_wiki import wiki_ingest_enabled


class WikiStagedIngestResult(BaseModel):
    """Outcome of attempting wiki ingest for a list of staged paths."""

    model_config = ConfigDict(extra="forbid")

    ingested: list[str] = Field(
        default_factory=list,
        description="Staged repo-relative paths that were ingested",
    )
    skipped: list[str] = Field(
        default_factory=list,
        description="Staged paths skipped (no match, wiki disabled, unreadable, …)",
    )
    errors: list[str] = Field(
        default_factory=list, description="Human-readable failures"
    )
    wiki_files_written: list[str] = Field(
        default_factory=list,
        description="Project-root-relative posix paths under ``.cortex/wiki/`` written",
    )


def _title_from_markdown(path: Path, content: str) -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            title = stripped.lstrip("#").strip()
            if title:
                return title
    stem = path.stem.replace("-", " ").replace("_", " ").strip()
    return stem or path.name


def _posix_norm(path_str: str) -> str:
    return PurePosixPath(path_str.replace("\\", "/")).as_posix()


class _ReadBodyResult(NamedTuple):
    """File read for ingest: ``body`` set, or ``error``, or ``skip_empty``."""

    body: str | None
    error: str | None
    skip_empty: bool


def _read_body_for_ingest(project_root: Path, rel: str) -> _ReadBodyResult:
    rel_parts = PurePosixPath(rel)
    if ".." in rel_parts.parts:
        return _ReadBodyResult(None, f"path escapes root: {rel}", False)
    abs_path = project_root.joinpath(rel_parts)
    if not abs_path.is_file():
        return _ReadBodyResult(None, f"not a file: {rel}", False)
    try:
        body = abs_path.read_text(encoding="utf-8")
    except OSError as exc:
        return _ReadBodyResult(None, f"read failed {rel}: {exc}", False)
    if not body.strip():
        return _ReadBodyResult(None, None, True)
    return _ReadBodyResult(body, None, False)


def _parse_ingest_response_json(
    out: str, rel: str
) -> tuple[dict[str, object] | None, str | None]:
    try:
        parsed: object = json.loads(out)
    except json.JSONDecodeError:
        return None, f"ingest invalid JSON for {rel}"
    if not isinstance(parsed, dict):
        return None, f"ingest unexpected payload for {rel}"
    return cast(dict[str, object], parsed), None


def _wiki_paths_from_success_payload(payload_dict: dict[str, object]) -> list[str]:
    found: list[str] = []
    for val in payload_dict.values():
        if (
            isinstance(val, str)
            and val.startswith(".cortex/wiki/")
            and val not in found
        ):
            found.append(val)
    return found


def _ingest_staged_file_body(
    project_root: Path, rel: str, body: str
) -> tuple[str, list[str], str | None]:
    """Return ``(ingested|unchanged|error, wiki_paths, error_message)``."""
    title = _title_from_markdown(Path(rel), body)
    payload = IngestSource(
        type=SourceType.MARKDOWN_FILE,
        content=body,
        title=title,
        tags=None,
        stable_ingest_rel=rel,
    )
    out = ingest_source_at_project_root(project_root, payload)
    payload_dict, parse_err = _parse_ingest_response_json(out, rel)
    if parse_err is not None:
        return "error", [], parse_err
    assert payload_dict is not None
    if payload_dict.get("status") != "success":
        err_obj = payload_dict.get("error", "unknown error")
        err = err_obj if isinstance(err_obj, str) else "unknown error"
        return "error", [], f"{rel}: {err}"
    if payload_dict.get("ingest_outcome") == "unchanged":
        return "unchanged", [], None
    return "ingested", _wiki_paths_from_success_payload(payload_dict), None


def _single_staged_wiki_outcome(
    project_root: Path, rel: str, eligible: set[str]
) -> tuple[str, str, list[str]]:
    """Return ``(kind, rel_or_error_message, wiki_paths)`` for one normalized path."""
    if rel.startswith(".cortex/wiki/") or rel not in eligible:
        return "skipped", rel, []
    read_out = _read_body_for_ingest(project_root, rel)
    if read_out.error is not None:
        return "error", read_out.error, []
    if read_out.skip_empty:
        return "skipped", rel, []
    assert read_out.body is not None
    outcome, wpaths, err = _ingest_staged_file_body(project_root, rel, read_out.body)
    if outcome == "error":
        return "error", err or "unknown ingest failure", []
    if outcome == "unchanged":
        return "skipped", rel, []
    return "ingested", rel, wpaths


def _empty_wiki_skip_result(staged_files: list[str]) -> WikiStagedIngestResult:
    return WikiStagedIngestResult(
        ingested=[],
        skipped=[_posix_norm(p) for p in staged_files],
        errors=[],
        wiki_files_written=[],
    )


def _merge_wiki_paths(wiki_written: list[str], wpaths: list[str]) -> None:
    for p in wpaths:
        if p not in wiki_written:
            wiki_written.append(p)


def _accumulate_staged_wiki_results(
    project_root: Path, staged_files: list[str], eligible: set[str]
) -> tuple[list[str], list[str], list[str], list[str]]:
    ingested: list[str] = []
    skipped: list[str] = []
    errors: list[str] = []
    wiki_written: list[str] = []
    seen: set[str] = set()
    for raw in staged_files:
        rel = _posix_norm(raw)
        if rel in seen:
            continue
        seen.add(rel)
        kind, key, wpaths = _single_staged_wiki_outcome(project_root, rel, eligible)
        if kind == "skipped":
            skipped.append(key)
        elif kind == "error":
            errors.append(key)
        else:
            ingested.append(key)
            _merge_wiki_paths(wiki_written, wpaths)
    return ingested, skipped, errors, wiki_written


def wiki_ingest_staged_docs(
    staged_files: list[str], project_root: Path
) -> WikiStagedIngestResult:
    """Ingest staged markdown files that match auto-ingest patterns into the wiki."""
    wiki_root = get_cortex_path(project_root, CortexResourceType.WIKI)
    if not wiki_ingest_enabled(wiki_root):
        return _empty_wiki_skip_result(staged_files)

    eligible = paths_matching_patterns(
        project_root, load_auto_ingest_patterns(project_root)
    )
    ingested, skipped, errors, wiki_written = _accumulate_staged_wiki_results(
        project_root, staged_files, eligible
    )
    return WikiStagedIngestResult(
        ingested=ingested,
        skipped=skipped,
        errors=errors,
        wiki_files_written=wiki_written,
    )
