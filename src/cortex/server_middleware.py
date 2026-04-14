"""FastMCP middleware wiring for disconnect handling and logging."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import anyio
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from fastmcp.server.middleware.logging import LoggingMiddleware
from fastmcp.server.middleware.response_limiting import ResponseLimitingMiddleware

from cortex.optimization.config import OptimizationConfig

logger = logging.getLogger(__name__)

DEFAULT_RESPONSE_LIMIT_BYTES = 1_000_000
TOKEN_TO_BYTE_MULTIPLIER = 4


class DisconnectMiddleware(Middleware):
    """Absorb disconnect write errors for request handlers."""

    async def on_message(
        self,
        context: MiddlewareContext[object],
        call_next: CallNext[object, object],
    ) -> object | None:
        try:
            return await call_next(context)
        except anyio.ClosedResourceError:
            logger.debug(
                "Response for method %s dropped: client disconnected",
                context.method,
            )
            return None


def is_debug_logging_enabled() -> bool:
    """Return whether FastMCP request/response logging should be enabled."""
    return os.environ.get("CORTEX_DEBUG") == "1" or (
        os.environ.get("CORTEX_MCP_LOG_LEVEL", "").lower() == "debug"
    )


def _response_limit_bytes_from_optimization(project_root: Path) -> int:
    """Load response size limit from optimization config."""
    config = OptimizationConfig(project_root)
    max_tokens = config.get_max_response_tokens()
    if max_tokens <= 0:
        return DEFAULT_RESPONSE_LIMIT_BYTES
    return max_tokens * TOKEN_TO_BYTE_MULTIPLIER


def create_server_middleware(project_root: Path) -> list[Middleware]:
    """Build middleware chain for FastMCP server startup."""
    middleware: list[Middleware] = [
        DisconnectMiddleware(),
        ResponseLimitingMiddleware(
            max_size=_response_limit_bytes_from_optimization(project_root)
        ),
    ]
    if is_debug_logging_enabled():
        middleware.append(LoggingMiddleware(log_level=logging.DEBUG))
    return middleware
