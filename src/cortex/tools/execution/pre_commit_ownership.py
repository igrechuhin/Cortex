"""Bind detached request identity to an agent and its server process."""

import hashlib
import os
import uuid
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache

from cortex.core.context_logging import MCPContext
from cortex.core.session_logger import get_session_id

_REQUEST_SESSION: ContextVar[str | None] = ContextVar(
    "quality_request_session", default=None
)


@lru_cache(maxsize=8)
def _process_nonce(pid: int) -> str:
    """A fork or another server must not inherit ownership via environment alone."""
    _ = pid
    return uuid.uuid4().hex


def current_owner() -> str:
    """Return an opaque process-bound agent identity, independent of pipelines."""
    session = _REQUEST_SESSION.get() or get_session_id()
    identity = f"{session}:{os.getpid()}:{_process_nonce(os.getpid())}"
    return hashlib.sha256(identity.encode()).hexdigest()


def owned_request_id(arguments_digest: str) -> str:
    """Same arguments from a foreign agent never name this agent's result."""
    return hashlib.sha256(f"{current_owner()}:{arguments_digest}".encode()).hexdigest()[
        :12
    ]


def envelope_owned(envelope: Mapping[str, object] | None) -> bool:
    """A matching result name alone never establishes ownership."""
    return envelope is not None and envelope.get("owner") == current_owner()


@contextmanager
def request_owner(ctx: MCPContext | None) -> Iterator[None]:
    """Use the framework's session identity, never tool arguments or pipeline IDs."""
    if ctx is None:
        yield
        return
    session = ctx.session_id
    if not session:
        raise ValueError("Quality request requires an established MCP session")
    token = _REQUEST_SESSION.set(session)
    try:
        yield
    finally:
        _REQUEST_SESSION.reset(token)
