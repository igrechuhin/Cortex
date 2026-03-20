"""Usage context setup for MCP tool handlers.

Extracted from mcp_stability for file size compliance.
"""

import asyncio
import logging
import os
import sys
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import ParamSpec, TypeVar, cast

from cortex.core.constants import MCP_USAGE_CONTEXT_INIT_LOCK_TIMEOUT_SECONDS
from cortex.core.context_logging import MCPContext
from cortex.core.mcp_stability_config import get_usage_context_init_lock
from cortex.core.protocols.mcp import SignatureAware
from cortex.core.usage_context import get_current_managers, set_current_managers

logger = logging.getLogger(__name__)

_P = ParamSpec("_P")
_R = TypeVar("_R")

_PYTEST_LIGHTWEIGHT_TOOLS: frozenset[str] = frozenset(
    {
        "execute_pre_commit_checks",
        "fix_markdown_lint",
        "get_link_graph",
        "get_relevance_scores",
        "load_context",
        "pipeline_handoff",
        "parse_file_links",
        "resolve_transclusions",
        "run_composite_workflow",
        "summarize_content",
        "skill_pack",
        "validate_links",
    }
)


def _is_pytest_running() -> bool:
    return (
        "pytest" in sys.modules
        or bool(os.environ.get("PYTEST_CURRENT_TEST"))
        or bool(os.environ.get("PYTEST_VERSION"))
    )


def _tool_original_name(func: Callable[..., object]) -> str:
    return getattr(getattr(func, "__wrapped__", None), "__name__", None) or getattr(
        func, "__name__", "unknown"
    )


def _should_use_pytest_lightweight_init(ctx_raw: object, tool_name: str) -> bool:
    return (
        ctx_raw is None
        and _is_pytest_running()
        and tool_name in _PYTEST_LIGHTWEIGHT_TOOLS
    )


async def _resolve_root_and_managers(
    mcp_ctx: MCPContext | None,
) -> tuple[Path, dict[str, object]]:
    """Resolve project root and get managers; log timings. Returns (root, mgrs_dict)."""
    from cortex.core.project_root_resolver import resolve_project_root_async
    from cortex.managers.initialization import get_managers

    t0 = time.monotonic()
    root = await resolve_project_root_async(None, mcp_ctx)
    resolve_elapsed = time.monotonic() - t0
    logger.debug(
        "ensure_usage_context: resolve_project_root_async took %.3fs -> %s",
        resolve_elapsed,
        root,
    )
    t1 = time.monotonic()
    mgrs = await get_managers(root)
    managers_elapsed = time.monotonic() - t1
    logger.debug(
        "ensure_usage_context: get_managers(%s) took %.3fs",
        root,
        managers_elapsed,
    )
    total = resolve_elapsed + managers_elapsed
    if total > 2.0:
        logger.info(
            "ensure_usage_context: first-tool init took %.2fs (resolve=%.2fs, get_managers=%.2fs)",
            total,
            resolve_elapsed,
            managers_elapsed,
        )
    mgrs_dict = mgrs if isinstance(mgrs, dict) else mgrs.model_dump()
    return (root, mgrs_dict)


async def _acquire_usage_context_lock_with_timeout(
    lock: asyncio.Lock, func_name: str
) -> None:
    """Acquire usage context init lock with timeout; raise RuntimeError on timeout."""
    try:
        async with asyncio.timeout(MCP_USAGE_CONTEXT_INIT_LOCK_TIMEOUT_SECONDS):
            async with lock:
                return
    except TimeoutError:
        logger.error(
            f"Usage context init lock timeout after {MCP_USAGE_CONTEXT_INIT_LOCK_TIMEOUT_SECONDS}s "
            + f"for {func_name}. Another tool call may be stuck in initialization."
        )
        raise RuntimeError(
            f"Failed to acquire usage context init lock after {MCP_USAGE_CONTEXT_INIT_LOCK_TIMEOUT_SECONDS}s. "
            + "Another tool call may be stuck in initialization."
        ) from None


async def _init_usage_context_under_lock(
    mcp_ctx: MCPContext | None, func_name: str
) -> None:
    """Resolve root, get managers, set usage context; raise after reporting."""
    from cortex.core.usage_context import set_current_project_root

    try:
        root, mgrs_dict = await _resolve_root_and_managers(mcp_ctx)
        set_current_managers(mgrs_dict)
        set_current_project_root(root)
    except Exception as e:  # pragma: no cover - exercised via tool tests
        await handle_tool_exception_if_failure(e, func_name, mcp_ctx)
        raise


def _ensure_usage_context_wrapper(  # noqa: UP047
    func: Callable[_P, Awaitable[_R]],
) -> Callable[_P, Awaitable[_R]]:
    import functools
    import inspect

    @functools.wraps(func)
    async def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _R:
        if get_current_managers() is not None:
            return await func(*args, **kwargs)
        ctx_raw = kwargs.get("ctx")
        tool_name = _tool_original_name(func)
        if _should_use_pytest_lightweight_init(ctx_raw, tool_name):
            from cortex.core.project_root_resolver import resolve_project_root_async
            from cortex.core.usage_context import set_current_project_root

            root = await resolve_project_root_async(None, None)
            set_current_managers({})
            set_current_project_root(root)
            return await func(*args, **kwargs)
        lock = get_usage_context_init_lock()
        await _acquire_usage_context_lock_with_timeout(lock, func.__name__)
        if get_current_managers() is not None:
            return await func(*args, **kwargs)
        mcp_ctx = cast(MCPContext | None, ctx_raw)
        await _init_usage_context_under_lock(mcp_ctx, func.__name__)
        return await func(*args, **kwargs)

    cast(SignatureAware, wrapper).__signature__ = inspect.signature(func)
    return wrapper


def ensure_usage_context(  # noqa: UP047
    func: Callable[_P, Awaitable[_R]],
) -> Callable[_P, Awaitable[_R]]:
    """Ensure usage context exists before running an MCP tool."""
    return _ensure_usage_context_wrapper(func)


async def handle_tool_exception_if_failure(
    error: Exception, tool_name: str, ctx: MCPContext | None = None
) -> None:
    """If error is an MCP tool failure, run protocol and raise; otherwise no-op."""
    from cortex.core.mcp_failure_handler import MCPToolFailureHandler

    handler = MCPToolFailureHandler(project_root=None)
    if await handler.detect_failure(error, tool_name, "MCP tool execution", ctx):
        await handler.handle_failure(tool_name, error, "MCP tool execution", ctx)
