"""MCP tool: stage raw external sources under memory-bank (ingest pipeline step 1)."""

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
from cortex.server import mcp
from cortex.tools.ingest.slug import allocate_unique_source_path, slugify_title
from cortex.tools.ingest.source_types import IngestSource, SourceType
from cortex.tools.response_builder import error_response, success_response


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


async def _ingest_store_and_build_json(
    payload: IngestSource,
    ctx: MCPContext | None,
) -> str:
    project_root = await get_or_resolve_project_root(ctx)
    memory_bank = get_cortex_path(project_root, CortexResourceType.MEMORY_BANK)
    sources_dir = memory_bank / "sources"
    base_slug = slugify_title(payload.title)
    slug_used, dest = allocate_unique_source_path(sources_dir, base_slug)
    try:
        _write_atomic(dest, payload.content)
    except OSError as exc:
        return json.dumps(
            error_response(
                error=f"Failed to write source file: {exc}", error_code="write_error"
            ),
            indent=2,
        )
    rel = dest.relative_to(project_root)
    base = success_response(
        slug=slug_used,
        source_path=str(rel).replace("\\", "/"),
        title=payload.title,
        source_type=payload.type.value,
    )
    if payload.tags is not None:
        base["tags"] = list(payload.tags)
    return json.dumps(base, indent=2)


@mcp.tool(annotations=safe_write_annotations("Ingest Raw Source (Memory Bank)"))
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def ingest(
    source_type: str,
    content: str,
    title: str,
    tags: list[str] | None = None,
    ctx: MCPContext | None = None,
) -> str:
    """Store raw external content immutably under ``.cortex/memory-bank/sources/``.

    USE WHEN: Staging external markdown or text for the ``/cortex/ingest`` workflow
    before synthesis updates memory-bank pages.

    DO NOT: Replace ``manage_file`` for curated pages; only immutable ``sources/`` snapshots.

    EXAMPLES:
    - ingest(source_type="text", content="# RFC\\n...", title="Draft RFC")
    - ingest(source_type="markdown_file", content=file_body, title="ADR 12")

    RETURNS: JSON with ``status``, ``slug``, ``source_path``, ``title``, ``source_type``.
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
