"""Resolve project root for MCP tools, using MCP roots when available.

When project_root is None and the tool has MCP context, requests roots from
the client (roots/list). If the client returns file:// roots, uses the first
as the workspace path so the agent does not need to pass project_root.
Falls back to get_project_root(None) on timeout, error, or unsupported client.

Set CORTEX_USE_FALLBACK_ROOT=1 to skip list_roots and use cwd/script-based
root immediately. Use this if the first tool call is slow and you suspect
the client is slow to respond to roots/list (then the delay is client-side).

Root caching
------------
The resolved root is cached after the first successful ``list_roots`` call and
reused for the lifetime of the server process.  Without a cache, every
concurrent tool call that calls :func:`resolve_project_root_async` issues its
own ``list_roots`` request.  When many tools run concurrently (e.g. five MCP
calls in the same agent step), those five simultaneous ``list_roots`` writes
to the stdio transport corrupt the protocol and crash the server.

Clients that support roots MAY send ``notifications/roots/list_changed`` when
the workspace root set changes.  The MCP server registers a handler that calls
:func:`handle_roots_list_changed` so the next resolution performs a fresh
``list_roots`` instead of returning a stale path.
"""

import asyncio
import logging
import os
import time
from pathlib import Path
from urllib.parse import unquote, urlparse

# AI: FastMCP v3 Context.session remains an MCP SDK ServerSession instance.
from mcp.server.session import ServerSession
from mcp.types import ClientCapabilities, RootsCapability

from cortex.managers.initialization import get_project_root

from .constants import MCP_ROOTS_LIST_TIMEOUT_SECONDS
from .context_logging import MCPContext

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Per-process root cache
# ---------------------------------------------------------------------------
# Populated on the first successful list_roots() call.  All subsequent calls
# return the cached value immediately without touching the transport.
cached_root: Path | None = None
_root_cache_lock: asyncio.Lock | None = None
# Wiki bootstrap once per resolved workspace (cleared with clear_cached_root).
wiki_bootstrapped_roots: set[str] = set()


def _get_root_cache_lock() -> asyncio.Lock:
    global _root_cache_lock
    if _root_cache_lock is None:
        _root_cache_lock = asyncio.Lock()
    return _root_cache_lock


def clear_cached_root() -> None:
    """Reset the root cache (used in tests and on explicit project-root override)."""
    global cached_root, wiki_bootstrapped_roots
    cached_root = None
    wiki_bootstrapped_roots.clear()


async def handle_roots_list_changed() -> None:
    """Clear the cached root when the client reports a roots change.

    Called when the MCP server receives ``notifications/roots/list_changed``.
    The next :func:`resolve_project_root_async` call issues a new ``list_roots``.
    """
    if cached_root is not None:
        logger.info(
            "project_root_resolver: roots/list_changed received, clearing cached root %s",
            cached_root,
        )
    clear_cached_root()


def file_uri_to_path(uri: str) -> Path | None:
    """Convert file:// URI to Path; return None if not file or invalid."""
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        return None
    path_str = unquote(parsed.path)
    if not path_str:
        return None
    return Path(path_str).resolve()


async def _bootstrap_wiki_once_per_root(root: Path) -> None:
    """Ensure ``.cortex/wiki/`` exists at most once per resolved root per process."""
    key = root.resolve().as_posix()
    if key in wiki_bootstrapped_roots:
        return

    def _work() -> None:
        try:
            from cortex.wiki.layout import bootstrap_wiki_if_cortex_present

            _ = bootstrap_wiki_if_cortex_present(root)
        except Exception:
            logger.warning(
                "wiki layout bootstrap failed for %s (non-fatal)",
                root,
                exc_info=True,
            )

    await asyncio.to_thread(_work)
    wiki_bootstrapped_roots.add(key)


async def _return_root_with_wiki_bootstrap(root: Path) -> Path:
    await _bootstrap_wiki_once_per_root(root)
    return root


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


_ROOTS_CAPABILITY = ClientCapabilities(roots=RootsCapability())


def _client_supports_roots(ctx: MCPContext) -> bool:
    """Return True if the client advertised roots capability.

    Clients that don't advertise it (e.g. Cursor's MCP bridge) close the
    transport when they receive ListRootsRequest, crashing the server.
    """
    return bool(ctx.session.check_client_capability(_ROOTS_CAPABILITY))


async def _fetch_roots_path(session: ServerSession) -> Path | None:
    """Call list_roots() and return the first valid file:// path, or None."""
    t0 = time.monotonic()
    try:
        async with asyncio.timeout(MCP_ROOTS_LIST_TIMEOUT_SECONDS):
            result = await session.list_roots()
        elapsed = time.monotonic() - t0
        logger.debug("project_root_resolver: list_roots() took %.3fs", elapsed)
        if elapsed > 1.0:
            logger.info(
                "project_root_resolver: list_roots() took %.2fs (client round-trip)",
                elapsed,
            )
        if result.roots:
            path = file_uri_to_path(str(result.roots[0].uri))
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
    # MCP transport/client implementations may raise varied exceptions
    # (e.g. McpError, ConnectionError, RuntimeError); fall back to
    # get_project_root() for all of them.
    except Exception as e:
        logger.debug(
            "project_root_resolver: roots/list failed (%s), using fallback",
            type(e).__name__,
        )
    return None


async def _try_roots_from_ctx(ctx: MCPContext) -> Path | None:
    """Request roots from client; return cached or freshly fetched file path.

    Uses a per-process cache so only the first call ever issues a
    ``list_roots`` request.  Concurrent callers wait on the lock and then
    return the cached value, avoiding simultaneous writes to the stdio
    transport that would corrupt the protocol.
    """
    global cached_root

    # Fast path: already resolved.
    if cached_root is not None:
        return cached_root

    if not _client_supports_roots(ctx):
        logger.debug(
            "project_root_resolver: client did not advertise roots capability, skipping list_roots()"
        )
        return None

    async with _get_root_cache_lock():
        # Re-check inside the lock (another coroutine may have populated it).
        if cached_root is not None:
            return cached_root
        path = await _fetch_roots_path(ctx.session)
        if path is not None:
            cached_root = path
            logger.debug("project_root_resolver: cached resolved root %s", cached_root)
        return path


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
        return await _return_root_with_wiki_bootstrap(get_project_root(project_root))
    use_fallback = os.environ.get("CORTEX_USE_FALLBACK_ROOT", "").strip().lower()
    if use_fallback in ("1", "true", "yes"):
        logger.info(
            "project_root_resolver: using fallback root (CORTEX_USE_FALLBACK_ROOT=1)"
        )
        root_fb = await asyncio.to_thread(_fallback_root)
        return await _return_root_with_wiki_bootstrap(root_fb)
    # Fast path: if a previous list_roots() call already resolved the root,
    # return it immediately even when ctx is None (e.g. inside list_prompts handler).
    if cached_root is not None:
        return await _return_root_with_wiki_bootstrap(cached_root)
    if ctx is not None and getattr(ctx, "session", None) is not None:
        path = await _try_roots_from_ctx(ctx)
        if path is not None:
            return await _return_root_with_wiki_bootstrap(path)
    root_fb2 = await asyncio.to_thread(_fallback_root)
    return await _return_root_with_wiki_bootstrap(root_fb2)
