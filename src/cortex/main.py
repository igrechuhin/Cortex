#!/usr/bin/env python3
"""
MCP Memory Bank - Main Entry Point

This is the main entry point for the Memory Bank MCP server.
All tool implementations are in the tools/ package.

By default the process runs once and exits when the connection drops (e.g. client
disconnect). The client (e.g. Cursor) starts a new process when it next needs
MCP, so the next session gets a fresh Initialize handshake with no user action.
Set CORTEX_AUTO_RESTART=1 to run an in-process restart loop (server respawns
under the same pipe; may require reloading MCP after disconnect to restore tools).
"""

import asyncio
import logging
import os
import subprocess
import sys
import traceback
from builtins import BaseExceptionGroup  # Python 3.11+
from typing import cast

import anyio

# Apply Cortex transport env to FastMCP settings before server is imported
from cortex.transport_config import apply_cortex_env_to_fastmcp

apply_cortex_env_to_fastmcp()

# Configure logging before FastMCP is created so root has our formatter first.
# FastMCP.__init__ calls configure_logging() → basicConfig(); basicConfig() is a
# no-op when root already has handlers, so we avoid RichHandler column format.
import cortex.core.logging_config  # noqa: F401, E402

# Import tools package to register all @mcp.tool() decorators
import cortex.setup.prompts_always  # noqa: F401, E402
import cortex.tools  # noqa: F401, E402
from cortex.server import mcp  # noqa: E402
from cortex.setup import should_mount_setup  # noqa: E402
from cortex.transport_config import (  # noqa: E402
    TRANSPORT_SSE,
    TRANSPORT_STREAMABLE_HTTP,
    get_effective_transport,
    get_mount_path,
)

cortex.core.logging_config.apply_cortex_format_to_third_party_loggers()

# Setup prompts (initialize_memory_bank, migration, etc.) only when project
# needs setup; setup_synapse is always available via prompts_always.
if should_mount_setup():
    import cortex.setup.prompts as _setup_prompts  # noqa: F401

    _ = _setup_prompts  # side-effect registration only

# Explicitly reference for side effects (tool/prompt registration)
_ = cortex.setup.prompts_always
_ = cortex.tools

logger = logging.getLogger(__name__)


def _is_connection_error(exc: BaseException) -> bool:
    """Check if exception is a connection-related or shutdown-related error."""
    if isinstance(
        exc,
        (
            anyio.BrokenResourceError,
            anyio.ClosedResourceError,
            BrokenPipeError,
            ConnectionResetError,
        ),
    ):
        return True
    if isinstance(exc, asyncio.CancelledError):
        return True  # Task cancellation often means client disconnect or timeout
    if isinstance(exc, OSError) and (
        "Broken pipe" in str(exc) or "Connection reset" in str(exc)
    ):
        return True
    # Handle nested exception groups recursively
    if isinstance(exc, BaseExceptionGroup):
        exc_group = cast(BaseExceptionGroup[BaseException], exc)
        for nested in exc_group.exceptions:
            if _is_connection_error(nested):
                return True
    return False


def _handle_broken_resource_in_group(eg: BaseExceptionGroup) -> bool:
    """Check if BaseExceptionGroup contains connection-related errors.

    Handles BrokenResourceError, ClosedResourceError, BrokenPipeError,
    ConnectionResetError, and nested exception groups that may contain these.

    Args:
        eg: BaseExceptionGroup to check

    Returns:
        True if connection error found (graceful shutdown), False otherwise
    """
    for exc in eg.exceptions:
        if _is_connection_error(exc):
            logger.info(
                (
                    "MCP stdio connection broken during TaskGroup cleanup "
                    "(client disconnected); group_msg=%s sub_count=%d "
                    "exc_type=%s exc_msg=%s"
                ),
                eg.message,
                len(eg.exceptions),
                type(exc).__name__,
                str(exc),
            )
            return True
    return False


def _handle_connection_error(e: Exception) -> None:
    """Handle connection-related errors with graceful shutdown.

    Args:
        e: Exception to handle
    """
    exc_type = type(e).__name__
    exc_msg = str(e)
    if isinstance(
        e, (anyio.BrokenResourceError, anyio.ClosedResourceError, BrokenPipeError)
    ):
        logger.warning(
            (
                "MCP stdio connection broken or closed (client disconnected); "
                "exc_type=%s exc_msg=%s"
            ),
            exc_type,
            exc_msg,
        )
        sys.exit(0)  # Graceful shutdown
    elif isinstance(e, ConnectionError):
        logger.error("MCP connection error; exc_type=%s exc_msg=%s", exc_type, exc_msg)
        sys.exit(1)
    elif isinstance(e, OSError):
        if "Broken pipe" in exc_msg or "Connection reset" in exc_msg:
            logger.warning(
                ("MCP connection reset (client disconnected); exc_type=%s exc_msg=%s"),
                exc_type,
                exc_msg,
            )
            sys.exit(0)  # Exit gracefully - client disconnected
        logger.error("MCP OS error; exc_type=%s exc_msg=%s", exc_type, exc_msg)
        sys.exit(1)


def _log_exception_with_traceback(exc: BaseException, prefix: str = "") -> None:
    """Log a single exception with full traceback; recurse into exception groups."""
    if isinstance(exc, BaseExceptionGroup):
        nested = cast(BaseExceptionGroup[BaseException], exc)
        for i, sub in enumerate(nested.exceptions):
            _log_exception_with_traceback(sub, prefix=f"{prefix}[{i}] ")
        return
    lines = traceback.format_exception(type(exc), exc, exc.__traceback__)
    tb_text = "".join(lines).strip()
    logger.error("%sMCP TaskGroup sub-exception: %s\n%s", prefix, exc, tb_text)


def _log_and_exit_on_task_group_error(eg: BaseExceptionGroup) -> None:
    """Log TaskGroup error details (including full nested tracebacks) and exit with code 1."""
    sub_summary = "; ".join(
        f"{type(e).__name__}: {str(e)[:200]}" for e in eg.exceptions[:5]
    )
    if len(eg.exceptions) > 5:
        sub_summary += f" ... and {len(eg.exceptions) - 5} more"
    logger.error(
        (
            "MCP server TaskGroup error (not connection-related); "
            "group_msg=%s sub_count=%d sub_exceptions=[%s]"
        ),
        eg.message,
        len(eg.exceptions),
        sub_summary,
    )
    for i, exc in enumerate(eg.exceptions):
        _log_exception_with_traceback(exc, prefix=f"[{i}] ")
    sys.exit(1)


def _require_http_deps() -> None:
    """Ensure uvicorn/starlette available for HTTP transport; exit with message if not."""
    try:
        import starlette as _starlette
        import uvicorn as _uvicorn

        _ = (_starlette, _uvicorn)
    except ImportError as e:
        msg = (
            "HTTP/SSE transport requires optional dependencies. "
            "Install with: uv sync --extra server (or pip install cortex[server]). %s"
        )
        logger.error(msg, e)
        sys.exit(1)


def _inject_sequential_thinking_core() -> None:
    """Inject SequentialThinkingCore at composition root (Phase 9.2 DI)."""
    from cortex.tools.sequential_thinking import (
        SequentialThinkingCore,
        configure_sequential_thinking_core,
    )

    configure_sequential_thinking_core(SequentialThinkingCore())


def _run_server_once() -> None:
    """Run the MCP server once (stdio or HTTP). Exits on disconnect or error."""
    _inject_sequential_thinking_core()
    transport = get_effective_transport()
    if transport in (TRANSPORT_SSE, TRANSPORT_STREAMABLE_HTTP):
        _require_http_deps()
    try:
        if transport == "stdio":
            mcp.run(transport="stdio")
        elif transport == TRANSPORT_SSE:
            mcp.run(transport="sse", mount_path=get_mount_path(transport))
        else:
            mcp.run(transport="streamable-http")
    except KeyboardInterrupt:
        logger.info("MCP server interrupted by user")
        sys.exit(0)
    except BaseExceptionGroup as eg:
        if _handle_broken_resource_in_group(eg):
            sys.exit(0)  # Graceful shutdown
        _log_and_exit_on_task_group_error(eg)
    except (
        anyio.BrokenResourceError,
        anyio.ClosedResourceError,
        BrokenPipeError,
        ConnectionError,
        OSError,
    ) as e:
        _handle_connection_error(e)
    except Exception as e:
        logger.exception("Unexpected error in MCP server: %s", e)
        sys.exit(1)


def _run_auto_restart_loop() -> None:
    """Spawn the server in a loop; restart on exit 0 (e.g. disconnect), propagate other exits."""
    inner_env = {**os.environ, "CORTEX_INNER": "1"}
    cmd = [sys.executable, "-m", "cortex.main", "--inner"]
    while True:
        code = subprocess.call(cmd, env=inner_env)
        if code != 0:
            sys.exit(code)


def main() -> None:
    """Entry point for the application when run with uvx.

    By default runs the server once; when the connection drops the process exits.
    The client starts a new process when it next needs MCP, so the next session
    gets a fresh Initialize handshake (no user reload needed). Set
    CORTEX_AUTO_RESTART=1 to run an in-process restart loop instead.

    Handles MCP stdio or HTTP/SSE connection. Transport is selected via
    CORTEX_MCP_TRANSPORT (stdio|sse|streamable-http); default stdio.
    When using sse or streamable-http, set CORTEX_MCP_PORT and optionally
    CORTEX_MCP_HOST. Ensures graceful shutdown on connection errors.

    The server does not invoke any tools on startup; tools (including
    execute_pre_commit_checks) run only when the client sends CallTool.
    """
    if "--inner" in sys.argv or os.environ.get("CORTEX_INNER") == "1":
        if "--inner" in sys.argv:
            sys.argv = [a for a in sys.argv if a != "--inner"]
        _run_server_once()
        return
    if os.environ.get("CORTEX_AUTO_RESTART") == "1":
        _run_auto_restart_loop()
        return
    _run_server_once()


if __name__ == "__main__":
    main()
