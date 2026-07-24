"""Lifecycle management components for Memory Bank structure."""

from cortex.structure.lifecycle.health import StructureHealthChecker
from cortex.structure.lifecycle.legacy_cursor_cleanup import (
    LegacyCursorCleanupReport,
    cleanup_legacy_cursor_artifacts,
)
from cortex.structure.lifecycle.local_environment_context import (
    LOCAL_ENV_CONTEXT_FILENAME,
    LocalEnvironmentContextResult,
    ensure_local_environment_context,
)
from cortex.structure.lifecycle.setup import StructureSetup

__all__ = [
    "StructureSetup",
    "StructureHealthChecker",
    "LegacyCursorCleanupReport",
    "cleanup_legacy_cursor_artifacts",
    "LOCAL_ENV_CONTEXT_FILENAME",
    "LocalEnvironmentContextResult",
    "ensure_local_environment_context",
]
