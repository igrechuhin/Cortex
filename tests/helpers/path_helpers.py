"""Path resolution helpers for tests using Cortex path resolver.

This module provides utilities for creating test directories and resolving
paths using the centralized path resolver, avoiding hardcoded paths in tests.
"""

from pathlib import Path

from cortex.core.path_resolver import CortexResourceType, get_cortex_path


def get_test_memory_bank_dir(project_root: Path) -> Path:
    """Get the memory-bank directory path for a test project root.

    Args:
        project_root: Temporary project root directory for testing

    Returns:
        Path to the memory-bank directory (.cortex/memory-bank)

    Examples:
        >>> root = Path("/tmp/test")
        >>> mb_dir = get_test_memory_bank_dir(root)
        >>> str(mb_dir)
        '/tmp/test/.cortex/memory-bank'
    """
    return get_cortex_path(project_root, CortexResourceType.MEMORY_BANK)


def ensure_test_cortex_structure(project_root: Path) -> Path:
    """Ensure .cortex directory structure exists for testing.

    Creates the .cortex directory and memory-bank subdirectory if they don't exist.

    Args:
        project_root: Temporary project root directory for testing

    Returns:
        Path to the memory-bank directory

    Examples:
        >>> root = Path("/tmp/test")
        >>> mb_dir = ensure_test_cortex_structure(root)
        >>> mb_dir.exists()
        True
    """
    memory_bank_dir = get_test_memory_bank_dir(project_root)
    memory_bank_dir.mkdir(parents=True, exist_ok=True)
    return memory_bank_dir


def get_test_cortex_path(project_root: Path, resource_type: CortexResourceType) -> Path:
    """Get a Cortex resource path for testing.

    Wrapper around get_cortex_path for test usage.

    Args:
        project_root: Temporary project root directory for testing
        resource_type: Type of Cortex resource

    Returns:
        Path to the resource

    Examples:
        >>> root = Path("/tmp/test")
        >>> plans_dir = get_test_cortex_path(root, CortexResourceType.PLANS)
        >>> str(plans_dir)
        '/tmp/test/.cortex/plans'
    """
    return get_cortex_path(project_root, resource_type)
