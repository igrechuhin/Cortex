"""Lifecycle management components for Memory Bank structure."""

from cortex.structure.lifecycle.health import StructureHealthChecker
from cortex.structure.lifecycle.local_environment_context import (
    LOCAL_ENV_CONTEXT_FILENAME,
    LocalEnvironmentContextResult,
    ensure_local_environment_context,
)
from cortex.structure.lifecycle.setup import StructureSetup
from cortex.structure.lifecycle.symlinks import CursorSymlinkManager

__all__ = [
    "StructureSetup",
    "StructureHealthChecker",
    "CursorSymlinkManager",
    "LOCAL_ENV_CONTEXT_FILENAME",
    "LocalEnvironmentContextResult",
    "ensure_local_environment_context",
]
