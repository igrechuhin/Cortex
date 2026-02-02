"""
MCP Prompt Templates (non-setup).

Setup and migration prompts have been moved to cortex.setup.prompts.
They are registered on the main server when the project needs setup
(main.py imports cortex.setup.prompts when should_mount_setup() is True).

This module is kept for tools package structure; all prompt registration
for setup, initialization, and migration lives in cortex.setup.prompts.
"""
