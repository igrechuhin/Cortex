"""Async file I/O utilities with proper typing.

This module provides typed wrappers around aiofiles to work around
incomplete type stubs in the aiofiles library.
"""

from contextlib import AbstractAsyncContextManager
from enum import Enum
from pathlib import Path
from typing import Literal, cast

import aiofiles

from cortex.core.types import AsyncTextIO

# Type for aiofiles.open mode argument (stubs expect Literal, not str).
_OpenTextMode = Literal["r", "w", "a", "x", "r+", "w+", "a+", "x+"]


class AsyncTextFileMode(str, Enum):
    """File open modes supported by aiofiles for text I/O."""

    R = "r"
    W = "w"
    A = "a"
    X = "x"
    R_PLUS = "r+"
    W_PLUS = "w+"
    A_PLUS = "a+"
    X_PLUS = "x+"


def open_async_text_file(
    file_path: Path,
    mode: AsyncTextFileMode | str,
    encoding: str,
) -> AbstractAsyncContextManager[AsyncTextIO]:
    """Open an async text file with proper typing.

    This helper function wraps aiofiles.open() to provide proper type information
    for the type checker, since aiofiles has incomplete type stubs.

    Args:
        file_path: Path to the file to open
        mode: File mode (e.g., 'r', 'w') or AsyncTextFileMode member
        encoding: Text encoding (e.g., 'utf-8')

    Returns:
        Properly typed async context manager
    """
    mode_str = mode.value if isinstance(mode, AsyncTextFileMode) else mode
    return cast(
        AbstractAsyncContextManager[AsyncTextIO],
        aiofiles.open(file_path, cast(_OpenTextMode, mode_str), encoding=encoding),
    )
