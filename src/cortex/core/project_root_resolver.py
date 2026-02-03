"""Resolve project root for MCP tools, using MCP roots when available.

When project_root is None and the tool has MCP context, requests roots from
the client (roots/list). If the client returns file:// roots, uses the first
as the workspace path so the agent does not need to pass project_root.
Falls back to get_project_root(None) on timeout, error, or unsupported client.
"""

import asyncio
import logging
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
    if ctx is not None and getattr(ctx, "session", None) is not None:
        try:
            async with asyncio.timeout(MCP_ROOTS_LIST_TIMEOUT_SECONDS):
                result = await ctx.session.list_roots()
            if result.roots:
                first = result.roots[0]
                uri_str = str(first.uri)
                path = _file_uri_to_path(uri_str)
                if path is not None and path.exists():
                    return path
        except TimeoutError:
            logger.debug(
                "project_root_resolver: roots/list timed out after %ss, using fallback",
                MCP_ROOTS_LIST_TIMEOUT_SECONDS,
            )
        except Exception as e:
            logger.debug(
                "project_root_resolver: roots/list failed (%s), using fallback",
                type(e).__name__,
            )
    return get_project_root(None)
