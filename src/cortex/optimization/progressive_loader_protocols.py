"""
Protocols for progressive loader helpers.

Shared protocol definitions—define once, reuse across modules (DRY).

Uses concrete types for LoaderProtocol attributes to satisfy type checker
invariance. Protocol alignment (FileSystemProtocol, ContextOptimizerProtocol,
etc.) is complete per docs/design/architecture-layering.md; switching
LoaderProtocol to protocol types is deferred until type checker variance
handling is resolved.
"""

from typing import Protocol

from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex

from .context_optimizer import ContextOptimizer


class LoaderProtocol(Protocol):
    """Protocol for loader passed to progressive loader helpers."""

    file_system: FileSystemManager
    context_optimizer: ContextOptimizer
    metadata_index: MetadataIndex
