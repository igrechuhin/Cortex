"""MCP tool: stage raw external sources (memory-bank or wiki ``sources/``)."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from cortex.core.constants import MCP_TOOL_TIMEOUT_MEDIUM
from cortex.core.context_logging import MCPContext
from cortex.core.mcp_annotations import safe_write_annotations
from cortex.core.mcp_stability import ensure_usage_context, mcp_tool_wrapper
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.usage_context import get_or_resolve_project_root
from cortex.server import ingest_caller_auth, mcp
from cortex.tools.ingest.slug import allocate_unique_source_path, slugify_title
from cortex.tools.ingest.source_types import IngestSource, SourceType
from cortex.tools.ingest.stable_path_ingest import ingest_source_with_stable_rel_path
from cortex.tools.response_builder import error_response, success_response
from cortex.wiki.ingest_wiki import (
    WikiIngestWriteResult,
    wiki_ingest_enabled,
    write_wiki_ingest_summary_and_index,
)


def _write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(f"{path.suffix}.tmp")
    _ = tmp_path.write_text(content, encoding="utf-8")
    _ = tmp_path.replace(path)


def _json_invalid_source_type(source_type: str) -> str:
    allowed = ", ".join(sorted(x.value for x in SourceType))
    return json.dumps(
        error_response(
            error=f"Invalid source_type {source_type!r}. Use one of: {allowed}.",
            error_code="invalid_source_type",
        ),
        indent=2,
    )


def _ingest_sources_dir(project_root: Path) -> tuple[Path, Path, bool]:
    memory_bank = get_cortex_path(project_root, CortexResourceType.MEMORY_BANK)
    wiki_root = get_cortex_path(project_root, CortexResourceType.WIKI)
    use_wiki = wiki_ingest_enabled(wiki_root)
    sources = (wiki_root / "sources") if use_wiki else (memory_bank / "sources")
    return wiki_root, sources, use_wiki


def _write_source_snapshot(dest: Path, content: str) -> str | None:
    """Return JSON error string or None when write succeeds."""
    try:
        _write_atomic(dest, content)
    except OSError as exc:
        return json.dumps(
            error_response(
                error=f"Failed to write source file: {exc}", error_code="write_error"
            ),
            indent=2,
        )
    return None


def _wiki_follow_up_or_error(
    project_root: Path,
    wiki_root: Path,
    slug_used: str,
    payload: IngestSource,
) -> WikiIngestWriteResult | str:
    try:
        return write_wiki_ingest_summary_and_index(
            project_root=project_root,
            wiki_root=wiki_root,
            source_slug=slug_used,
            title=payload.title,
            content=payload.content,
            tags=list(payload.tags) if payload.tags is not None else None,
        )
    except OSError as exc:
        return json.dumps(
            error_response(
                error=f"Failed to write wiki summary or index: {exc}",
                error_code="write_error",
            ),
            indent=2,
        )


def ingest_source_at_project_root(project_root: Path, payload: IngestSource) -> str:
    # AI: Sync entrypoint so commit-pipeline helpers can ingest without an MCP context.
    """Run ingest synchronously for ``project_root`` (MCP tool uses async resolver).

    Returns a JSON string: either a success payload (same shape as ``ingest``) or an
    ``error_response`` JSON string on failure.
    """
    wiki_root, sources_dir, use_wiki = _ingest_sources_dir(project_root)
    if payload.stable_ingest_rel is not None:
        return ingest_source_with_stable_rel_path(
            project_root, wiki_root, sources_dir, use_wiki, payload
        )

    base_slug = slugify_title(payload.title)
    slug_used, dest = allocate_unique_source_path(sources_dir, base_slug)
    err = _write_source_snapshot(dest, payload.content)
    if err is not None:
        return err
    rel = dest.relative_to(project_root)
    base = success_response(
        slug=slug_used,
        source_path=str(rel).replace("\\", "/"),
        title=payload.title,
        source_type=payload.type.value,
        ingest_target="wiki" if use_wiki else "memory_bank",
    )
    if payload.tags is not None:
        base["tags"] = list(payload.tags)
    if use_wiki:
        wiki_part = _wiki_follow_up_or_error(
            project_root, wiki_root, slug_used, payload
        )
        if isinstance(wiki_part, str):
            return wiki_part
        base["wiki_summary_path"] = wiki_part.summary_project_posix
        base["wiki_category"] = wiki_part.summary_category
    return json.dumps(base, indent=2)


async def _ingest_store_and_build_json(
    payload: IngestSource,
    ctx: MCPContext | None,
) -> str:
    project_root = await get_or_resolve_project_root(ctx)
    return ingest_source_at_project_root(project_root, payload)


@mcp.tool(
    annotations=safe_write_annotations("Ingest Raw Source (Wiki / Memory Bank)"),
    auth=ingest_caller_auth,
)
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def ingest(
    source_type: str,
    content: str,
    title: str,
    tags: list[str] | None = None,
    ctx: MCPContext | None = None,
) -> str:
    """Store raw external content immutably under ``sources/``.

    When ``.cortex/wiki/`` exists, writes to ``.cortex/wiki/sources/`` and creates a
    summary page plus a wiki catalog table row (tag ``decisions`` / ``entities`` / … selects
    the category directory; default ``concepts``). Otherwise uses
    ``.cortex/memory-bank/sources/`` (legacy memory-bank ingest path).

    USE WHEN: Preserving an external artifact (RFC, ADR, design doc, spec, decision record)
    that informs or justifies a project decision — content that came from *outside* the
    codebase and whose provenance matters long-term.

    DO NOT use for:
    - Intermediate working files, scratch notes, or temporary read buffers.
    - Content you just read from the project's own source tree (code, configs, existing docs).
    - Summaries of your own reasoning or in-progress analysis.
    - Any file whose title would be "temp", "test", or a transient label.
    Only call ``ingest`` when the content is an external artifact worth archiving permanently.

    EXAMPLES:
    - ingest(source_type="text", content="# RFC\\n...", title="RFC 42: Auth token storage")
    - ingest(source_type="markdown_file", content=file_body, title="ADR 12: Switch to Pydantic v2")

    RETURNS: JSON with ``status``, ``slug``, ``source_path``, ``title``, ``source_type``,
    ``ingest_target``, and when wiki mode: ``wiki_summary_path``, ``wiki_category``.
    """
    try:
        st = SourceType(source_type)
    except ValueError:
        return _json_invalid_source_type(source_type)
    try:
        payload = IngestSource(type=st, content=content, title=title.strip(), tags=tags)
    except ValidationError as exc:
        return json.dumps(error_response(error=str(exc)), indent=2)
    return await _ingest_store_and_build_json(payload, ctx)
