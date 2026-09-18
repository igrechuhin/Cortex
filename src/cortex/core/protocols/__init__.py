#!/usr/bin/env python3
"""Protocol definitions for MCP Memory Bank.

All protocols are re-exported from this module for convenience.
Import structure:
    from cortex.core.protocols import FileSystemProtocol

This works because __init__.py re-exports all protocols from submodules.
"""

# File system protocols
from cortex.core.protocols.file_system import (
    FileSystemProtocol,
    MetadataIndexProtocol,
)

# Token and dependency protocols
from cortex.core.protocols.token import (
    DependencyGraphProtocol,
    TokenCounterProtocol,
)

__all__ = [
    # File system
    "FileSystemProtocol",
    "MetadataIndexProtocol",
    # Token and dependency
    "TokenCounterProtocol",
    "DependencyGraphProtocol",
]
