#!/usr/bin/env python3
"""Cortex MCP transport configuration.

Reads CORTEX_MCP_TRANSPORT, CORTEX_MCP_PORT, CORTEX_MCP_HOST from environment.
Default transport is stdio when port unset; explicit transport optional.
When port is set, default transport is streamable-http unless overridden.
"""

from __future__ import annotations

import os

# Valid transport values for FastMCP.run()
TRANSPORT_STDIO = "stdio"
TRANSPORT_SSE = "sse"
TRANSPORT_STREAMABLE_HTTP = "streamable-http"
VALID_TRANSPORTS = frozenset(
    {TRANSPORT_STDIO, TRANSPORT_SSE, TRANSPORT_STREAMABLE_HTTP}
)

# Default mount path for SSE (FastMCP sse_path)
DEFAULT_SSE_MOUNT_PATH = "/sse"


def _env(key: str, default: str = "") -> str:
    """Read env var and strip; return default if unset or empty."""
    return (os.environ.get(key) or default).strip()


def get_port() -> int | None:
    """Return CORTEX_MCP_PORT as int, or None if unset/invalid."""
    raw = _env("CORTEX_MCP_PORT")
    if not raw:
        return None
    try:
        return int(raw, 10)
    except ValueError:
        return None


def get_host() -> str:
    """Return CORTEX_MCP_HOST or default 127.0.0.1 (localhost)."""
    raw = _env("CORTEX_MCP_HOST")
    return raw if raw else "127.0.0.1"


def get_effective_transport() -> str:
    """Resolve effective transport from env.

    When CORTEX_MCP_PORT is set, default transport is streamable-http unless
    CORTEX_MCP_TRANSPORT is set. When port is unset, default is stdio.
    Explicit CORTEX_MCP_TRANSPORT overrides in both cases.
    """
    explicit = _env("CORTEX_MCP_TRANSPORT").lower()
    if explicit and explicit in VALID_TRANSPORTS:
        return explicit
    port = get_port()
    if port is not None:
        return TRANSPORT_STREAMABLE_HTTP
    return TRANSPORT_STDIO


def get_mount_path(transport: str) -> str:
    """Return mount path for HTTP transport. Used for SSE; streamable-http uses its own path."""
    if transport == TRANSPORT_SSE:
        return DEFAULT_SSE_MOUNT_PATH
    return "/mcp"
