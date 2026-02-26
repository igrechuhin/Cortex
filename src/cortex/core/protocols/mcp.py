"""MCP-related protocols.

Shared protocol definitions for MCP tool decorators and wrappers.
"""

from inspect import Signature
from typing import Protocol


class SignatureAware(Protocol):
    """Protocol for callable wrappers that preserve __signature__ (e.g. functools.wraps)."""

    __signature__: Signature
