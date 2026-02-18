"""Resolve project root for MCP tools, using MCP roots when available.

When project_root is None and the tool has MCP context, requests roots from
the client (roots/list). If the client returns file:// roots, uses the first
as the workspace path so the agent does not need to pass project_root.
Falls back to get_project_root(None) on timeout, error, or unsupported client.

Set CORTEX_USE_FALLBACK_ROOT=1 to skip list_roots and use cwd/script-based
root immediately. Use this if the first tool call is slow and you suspect
the client is slow to respond to roots/list (then the delay is client-side).
"""

import asyncio
import logging
import os
import time
from pathlib import Path
from urllib.parse import unquote, urlparse

from cortex.managers.initialization import get_project_root

from .constants import MCP_ROOTS_LIST_TIMEOUT_SECONDS
from .context_logging import MCPContext

logger = logging.getLogger(__name__)


def _file_uri_to_path(uri: str) -> Path | None:
    """Convert file:// URI to Path; return None if not file or invalid."""
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        return None
    path_str = unquote(parsed.path)
    if not path_str:
        return None
    return Path(path_str).resolve()


def _fallback_root() -> Path:
    """Resolve project root via get_project_root(None) and log elapsed time."""
    t0 = time.monotonic()
    root = get_project_root(None)
    logger.debug(
        "project_root_resolver: fallback get_project_root() took %.3fs -> %s",
        time.monotonic() - t0,
        root,
    )
    return root


async def _try_roots_from_ctx(ctx: MCPContext) -> Path | None:
    """Request roots from client; return first valid file path or None."""
    t0 = time.monotonic()
    try:
        async with asyncio.timeout(MCP_ROOTS_LIST_TIMEOUT_SECONDS):
            result = await ctx.session.list_roots()
        elapsed = time.monotonic() - t0
        logger.debug("project_root_resolver: list_roots() took %.3fs", elapsed)
        if elapsed > 1.0:
            logger.info(
                "project_root_resolver: list_roots() took %.2fs (client round-trip)",
                elapsed,
            )
        if result.roots:
            first = result.roots[0]
            path = _file_uri_to_path(str(first.uri))
            if path is not None and path.exists():
                logger.debug("project_root_resolver: using root from client: %s", path)
                return path
    except TimeoutError:
        elapsed = time.monotonic() - t0
        logger.debug(
            "project_root_resolver: roots/list timed out after %.3fs (limit %ss), using fallback",
            elapsed,
            MCP_ROOTS_LIST_TIMEOUT_SECONDS,
        )
    except Exception as e:
        logger.debug(
            "project_root_resolver: roots/list failed (%s), using fallback",
            type(e).__name__,
        )
    return None


async def resolve_project_root_async(
    project_root: str | None,
    ctx: MCPContext | None,
) -> Path:
    """Resolve project root, using MCP roots when project_root is None.

    When project_root is provided, returns that path (via get_project_root).
    When project_root is None and ctx has a session, requests roots from the
    client (roots/list). If the client supports roots and returns at least one
    file:// root, uses the first as the project path. Otherwise falls back to
    get_project_root(None) (cwd/script-based detection).

    Args:
        project_root: Optional path from tool argument.
        ctx: MCP context (injected in tools); may be None in tests.

    Returns:
        Resolved absolute Path to project root.
    """
    if project_root:
        return get_project_root(project_root)
    use_fallback = os.environ.get("CORTEX_USE_FALLBACK_ROOT", "").strip().lower()
    if use_fallback in ("1", "true", "yes"):
        logger.info(
            "project_root_resolver: using fallback root (CORTEX_USE_FALLBACK_ROOT=1)"
        )
        return await asyncio.to_thread(_fallback_root)
    if ctx is not None and getattr(ctx, "session", None) is not None:
        path = await _try_roots_from_ctx(ctx)
        if path is not None:
            return path
    return await asyncio.to_thread(_fallback_root)
