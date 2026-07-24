# Copyright (c) 2025 Cortex and contributors. All rights reserved.
# SPDX-License-Identifier: MIT

"""Unit tests for cortex.setup module."""

from unittest.mock import patch

from cortex.setup import should_mount_setup
from cortex.tools.config import ProjectConfigStatus


def test_should_mount_setup_returns_true_when_memory_bank_not_initialized() -> None:
    """When memory bank is not initialized, should_mount_setup returns True."""
    config = ProjectConfigStatus(
        memory_bank_initialized=False,
        structure_configured=True,
        migration_needed=False,
        tiktoken_cache_available=True,
        codegraph_configured=True,
    )
    assert should_mount_setup(config) is True


def test_should_mount_setup_returns_true_when_structure_not_configured() -> None:
    """When structure is not configured, should_mount_setup returns True."""
    config = ProjectConfigStatus(
        memory_bank_initialized=True,
        structure_configured=False,
        migration_needed=False,
        tiktoken_cache_available=True,
        codegraph_configured=True,
    )
    assert should_mount_setup(config) is True


def test_should_mount_setup_returns_true_when_migration_needed() -> None:
    """When migration is needed, should_mount_setup returns True."""
    config = ProjectConfigStatus(
        memory_bank_initialized=True,
        structure_configured=True,
        migration_needed=True,
        tiktoken_cache_available=True,
        codegraph_configured=True,
    )
    assert should_mount_setup(config) is True


def test_should_mount_setup_returns_false_when_fully_configured() -> None:
    """When project is fully configured, should_mount_setup returns False."""
    config = ProjectConfigStatus(
        memory_bank_initialized=True,
        structure_configured=True,
        migration_needed=False,
        tiktoken_cache_available=True,
        codegraph_configured=True,
    )
    assert should_mount_setup(config) is False


def test_should_mount_setup_calls_get_project_config_status_when_config_none() -> None:
    """When config is None, should_mount_setup calls get_project_config_status."""
    with patch(
        "cortex.setup.get_project_config_status",
        return_value=ProjectConfigStatus(
            memory_bank_initialized=True,
            structure_configured=True,
            migration_needed=False,
            tiktoken_cache_available=True,
            codegraph_configured=True,
        ),
    ) as mock_get:
        result = should_mount_setup(None)
        mock_get.assert_called_once()
        assert result is False
