#!/usr/bin/env python3
"""Stdio to Streamable HTTP bridge for Cortex MCP.

Runs Cortex with streamable-http transport and proxies between Cursor (stdio)
and Cortex (HTTP) so the user keeps a single on/off switch in Cursor while
Cortex handles requests concurrently over HTTP.

Requires: uv sync --extra server (or pip install cortex[server]).
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

import anyio
from anyio.streams.memory import (
    MemoryObjectReceiveStream,
    MemoryObjectSendStream,
)
from mcp.shared.message import SessionMessage

logging.basicConfig(
    level=logging.WARNING,
    format="%(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

# Default URL for Cortex streamable-http (must match port/host used by subprocess)
DEFAULT_BRIDGE_URL = "http://127.0.0.1:8000/mcp"
CORTEX_BRIDGE_URL_ENV = "CORTEX_BRIDGE_URL"
CORTEX_BRIDGE_PORT_ENV = "CORTEX_MCP_PORT"
BRIDGE_PORT_DEFAULT = 8000
WAIT_TIMEOUT_SECONDS = 30
WAIT_POLL_INTERVAL_SECONDS = 0.25


def _get_bridge_url() -> str:
    return os.environ.get(CORTEX_BRIDGE_URL_ENV, "").strip() or DEFAULT_BRIDGE_URL


def _get_bridge_port() -> int:
    raw = os.environ.get(CORTEX_BRIDGE_PORT_ENV, "").strip()
    if not raw:
        return BRIDGE_PORT_DEFAULT
    try:
        return int(raw, 10)
    except ValueError:
        return BRIDGE_PORT_DEFAULT


def _cortex_repo_root() -> Path:
    """Return Cortex repo root (parent of src/)."""
    # bridge.py is at src/cortex/bridge.py
    return Path(__file__).resolve().parent.parent.parent


def _require_server_deps() -> None:
    try:
        import httpx  # noqa: F401
        from mcp.client import streamable_http  # noqa: F401

        _ = (httpx, streamable_http)
    except ImportError as e:
        print(
            "Bridge requires server extra. Install with: uv sync --extra server",
            file=sys.stderr,
        )
        raise SystemExit(1) from e


def _start_cortex_subprocess(port: int) -> subprocess.Popen[bytes]:
    env = os.environ.copy()
    env["CORTEX_MCP_TRANSPORT"] = "streamable-http"
    env["CORTEX_MCP_PORT"] = str(port)
    cmd = [sys.executable, "-m", "cortex.main"]
    cwd = _cortex_repo_root()
    return subprocess.Popen(
        cmd,
        env=env,
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _read_subprocess_stderr(proc: subprocess.Popen[bytes]) -> str:
    """Read and return stderr from subprocess; non-blocking."""
    if proc.stderr is None:
        return ""
    try:
        proc.stderr.flush()
        return proc.stderr.read().decode("utf-8", errors="replace")
    except Exception:
        return ""


def _url_to_host_port(url: str) -> tuple[str, int]:
    """Parse URL and return (host, port). Default port 8000."""
    from urllib.parse import urlparse

    parsed = urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port if parsed.port is not None else 8000
    return host, port


def _tcp_connect(host: str, port: int) -> bool:
    """Try to open a TCP connection to host:port; return True if successful."""
    import socket

    sock = None
    try:
        sock = socket.create_connection((host, port), timeout=2)
        return True
    except OSError:
        return False
    finally:
        if sock is not None:
            sock.close()


async def _wait_for_url(url: str, proc: subprocess.Popen[bytes]) -> None:
    """Wait until the server accepts TCP connections on the URL's host:port."""
    host, port = _url_to_host_port(url)
    deadline = time.monotonic() + WAIT_TIMEOUT_SECONDS
    loop = asyncio.get_event_loop()
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            stderr = _read_subprocess_stderr(proc)
            msg = (
                f"Bridge: Cortex subprocess exited with {proc.returncode} before "
                f"server was ready. stderr:\n{stderr or '(empty)'}"
            )
            raise RuntimeError(msg)
        try:
            if await asyncio.wait_for(
                loop.run_in_executor(None, _tcp_connect, host, port),
                timeout=2.5,
            ):
                return
        except (TimeoutError, OSError):
            pass
        await anyio.sleep(WAIT_POLL_INTERVAL_SECONDS)
    # Only read stderr if process exited (otherwise read would block)
    stderr = _read_subprocess_stderr(proc) if proc.poll() is not None else ""
    extra = (
        f" Cortex stderr:\n{stderr}"
        if stderr
        else " (install server deps: uv sync --extra server)"
    )
    raise RuntimeError(f"Bridge: server at {url} did not become ready in time.{extra}")


async def _forward_stdio_to_http(
    stdio_read: MemoryObjectReceiveStream[SessionMessage | Exception],
    http_write: MemoryObjectSendStream[SessionMessage],
) -> None:
    async with stdio_read, http_write:
        async for msg in stdio_read:
            if isinstance(msg, SessionMessage):
                await http_write.send(msg)


async def _forward_http_to_stdio(
    http_read: MemoryObjectReceiveStream[SessionMessage | Exception],
    stdio_write: MemoryObjectSendStream[SessionMessage],
) -> None:
    async with http_read, stdio_write:
        async for msg in http_read:
            if isinstance(msg, SessionMessage):
                await stdio_write.send(msg)
            else:
                logger.warning(
                    "Dropping non-SessionMessage from HTTP: %s",
                    type(msg).__name__,
                )


async def _run_bridge(url: str) -> None:
    from mcp.client.streamable_http import streamable_http_client
    from mcp.server.stdio import stdio_server

    async with (
        stdio_server() as (stdio_read, stdio_write),
        streamable_http_client(url) as (http_read, http_write, _get_session_id),
    ):
        async with anyio.create_task_group() as tg:
            tg.start_soon(_forward_stdio_to_http, stdio_read, http_write)
            tg.start_soon(_forward_http_to_stdio, http_read, stdio_write)


async def _main(port: int, url: str, proc: subprocess.Popen[bytes]) -> None:
    await _wait_for_url(url, proc)
    try:
        await _run_bridge(url)
    finally:
        proc.terminate()
        try:
            _ = proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            _ = proc.wait()


def main() -> None:
    _require_server_deps()
    port = _get_bridge_port()
    url = _get_bridge_url()
    proc = _start_cortex_subprocess(port)
    try:

        async def _entry() -> None:
            await _main(port, url, proc)

        anyio.run(_entry)
    except KeyboardInterrupt:
        logger.info("Bridge interrupted")
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                _ = proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                _ = proc.wait()


if __name__ == "__main__":
    main()
