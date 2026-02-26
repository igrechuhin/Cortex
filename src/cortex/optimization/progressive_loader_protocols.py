"""
Protocols for progressive loader helpers.

Shared protocol definitions—define once, reuse across modules (DRY).
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
