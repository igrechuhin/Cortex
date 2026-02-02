# Copyright (c) 2025 Cortex and contributors. All rights reserved.
# SPDX-License-Identifier: MIT

"""Setup MCP server composition (no-op when mount not available).

This module reserves the setup server abstraction. The current MCP SDK
(mcp>=1.26.0) does not provide FastMCP.mount(), so setup prompts are
registered on the main server via cortex.setup.prompts when the module
is imported. If a future SDK adds mount(), this module can expose a
separate FastMCP instance for setup and mounting logic.
"""
