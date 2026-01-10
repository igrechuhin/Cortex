"""Shared type definitions for the Cortex codebase."""

from typing import Protocol


class AsyncTextIO(Protocol):
    """
    Protocol for async text file handles from aiofiles.

    This Protocol defines the interface that aiofiles file handles implement.
    We use this Protocol with typing.cast() to help the type checker understand
    the types returned by aiofiles.open(), since aiofiles has incomplete type stubs.

    Note: The warnings about aiofiles.open() being "partially unknown" are due to
    limitations in the aiofiles library's type stubs, not our code. The actual
    runtime types are compatible with this Protocol.
    """

    async def read(self) -> str:
        """Read file content."""
        ...

    async def write(self, content: str) -> int:
        """Write content to file."""
        ...
