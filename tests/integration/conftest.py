"""Shared fixtures and helpers for integration tests."""

from pathlib import Path

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.managers.initialization import get_project_root


def repo_root() -> Path:
    """Return repository root (directory containing src/ and tests/)."""
    return get_project_root()


def synapse_path() -> Path:
    """Return path to Synapse directory."""
    return get_cortex_path(repo_root(), CortexResourceType.SYNAPSE)
