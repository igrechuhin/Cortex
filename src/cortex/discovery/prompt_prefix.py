"""Canonical rendering of the agent-visible prompt prefix (tool schemas).

Anthropic prompt caching is an exact-prefix byte match over the rendered
request in the order ``tools`` -> ``system`` -> ``messages``. Tool schemas sit
at position zero, so any byte that drifts between two otherwise identical
sessions invalidates the whole downstream prefix.

Cortex is an MCP server and cannot set ``cache_control`` breakpoints — that is
the host's job. What it *does* control is the content it contributes: the tool
names, descriptions, and JSON Schemas it registers. This module renders those
into a single canonical string so a regression test can assert byte equality
across processes with differing ``PYTHONHASHSEED`` values.

Not to be confused with :mod:`cortex.core.cache_warming`, which concerns
Cortex's own internal ``AdvancedCacheManager`` file cache and has nothing to do
with the host's prompt cache.
"""

from __future__ import annotations

import hashlib
import json

from cortex.tools.evaluation._agentic_models import ModelToolSchema


def canonical_json(payload: object) -> str:
    """Serialize ``payload`` deterministically for an agent-visible surface.

    ``sort_keys`` pins key order, which otherwise follows dict construction and
    can differ between processes. ``ensure_ascii`` is pinned so a future default
    change cannot silently shift bytes.
    """
    return json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False)


def render_tool_schema_payload(schemas: list[ModelToolSchema]) -> str:
    """Render tool schemas into the canonical, byte-stable prefix string.

    Schemas are sorted by name so registration/import order cannot leak into
    the rendered bytes.
    """
    entries = [
        {
            "name": schema.name,
            "description": schema.description,
            "input_schema": schema.input_schema,
        }
        for schema in sorted(schemas, key=lambda item: item.name)
    ]
    return canonical_json(entries)


def payload_digest(payload: str) -> str:
    """Stable SHA-256 hex digest of a rendered payload, for cheap comparison."""
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


__all__ = [
    "canonical_json",
    "payload_digest",
    "render_tool_schema_payload",
]
