# Copyright (c) 2025 Cortex and contributors. All rights reserved.
# SPDX-License-Identifier: MIT

"""Setup-related prompts and optional mounting logic.

Setup prompts (initialize, migrate, populate_tiktoken_cache) are registered
on the main MCP server when this package's prompts module is imported
(e.g. from main.py). The current MCP SDK does not provide server mount(),
so setup is implemented as a separate module that registers on the main server.

setup_synapse is always available via prompts_always module.
"""

from cortex.tools.config import (
    ProjectConfigStatus,
    get_project_config_status,
)


def should_mount_setup(config: ProjectConfigStatus | None = None) -> bool:
    """Return True if project needs setup (initialization or migration).

    When True, setup prompts should be available. Used by main entry point
    to decide whether to import setup prompts (which register on the main
    server). Pass config to avoid re-reading; otherwise uses
    get_project_config_status().
    """
    status = config if config is not None else get_project_config_status()
    return (
        not status.memory_bank_initialized
        or not status.structure_configured
        or not status.cursor_integration_configured
        or status.migration_needed
        or not status.tiktoken_cache_available
    )


# Import prompts so they register on the main server when setup is needed.
# main.py imports cortex.setup.prompts after cortex.tools so that setup
# prompts are registered conditionally on the same mcp instance.
__all__ = ["get_project_config_status", "ProjectConfigStatus", "should_mount_setup"]
