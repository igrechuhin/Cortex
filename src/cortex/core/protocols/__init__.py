#!/usr/bin/env python3
"""Protocol definitions for MCP Memory Bank.

All protocols are re-exported from this module for convenience.
Import structure:
    from cortex.core.protocols import FileSystemProtocol

This works because __init__.py re-exports all protocols from submodules.
"""

# Analysis protocols
from cortex.core.protocols.analysis import (
    PatternAnalyzerProtocol,
    StructureAnalyzerProtocol,
)

# File system protocols
from cortex.core.protocols.file_system import (
    FileSystemProtocol,
    MetadataIndexProtocol,
)

# Optimization protocols
from cortex.core.protocols.optimization import ContextOptimizerProtocol

# Refactoring protocols
from cortex.core.protocols.refactoring import SplitRecommenderProtocol

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
    # Optimization
    "ContextOptimizerProtocol",
    # Analysis
    "PatternAnalyzerProtocol",
    "StructureAnalyzerProtocol",
    # Refactoring
    "SplitRecommenderProtocol",
]
