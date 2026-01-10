"""Async file I/O utilities with proper typing.

This module provides typed wrappers around aiofiles to work around
incomplete type stubs in the aiofiles library.
"""

from contextlib import AbstractAsyncContextManager
from pathlib import Path
from typing import Literal, cast

import aiofiles

from cortex.core.types import AsyncTextIO

# Type for file modes supported by aiofiles
AsyncTextFileMode = Literal["r", "w", "a", "x", "r+", "w+", "a+", "x+"]


def open_async_text_file(
    file_path: Path, mode: AsyncTextFileMode, encoding: str
) -> AbstractAsyncContextManager[AsyncTextIO]:
    """Open an async text file with proper typing.

    This helper function wraps aiofiles.open() to provide proper type information
    for the type checker, since aiofiles has incomplete type stubs.

    Args:
        file_path: Path to the file to open
        mode: File mode (e.g., 'r', 'w')
        encoding: Text encoding (e.g., 'utf-8')

    Returns:
        Properly typed async context manager
    """
    return cast(
        AbstractAsyncContextManager[AsyncTextIO],
        aiofiles.open(file_path, mode, encoding=encoding),
    )
