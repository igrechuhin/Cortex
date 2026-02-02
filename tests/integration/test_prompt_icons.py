# Copyright (c) 2025 Cortex and contributors. All rights reserved.
# SPDX-License-Identifier: MIT

"""Integration tests that the server returns prompts with icons.

Verifies that when prompts are registered (setup and/or Synapse), list_prompts
includes at least one prompt with non-empty icons. Display of icons in the UI
depends on the MCP client (e.g. Cursor may not render them yet).
"""

import pytest

# Import main so that setup.prompts and tools (synapse_prompts) are loaded
# and prompts are registered with icons.
import cortex.main

_ = cortex.main  # Side-effect import for prompt registration
from cortex.server import mcp


@pytest.mark.asyncio
async def test_list_prompts_includes_at_least_one_prompt_with_icons() -> None:
    """Server list_prompts returns at least one prompt that has icons.

    Cortex registers setup and Synapse prompts with emoji icons. This test
    ensures the server sends them in the prompts list. If this passes but
    the user does not see icons in the client, the client is not rendering
    prompt icons (e.g. Cursor IDE).
    """
    # Prompts are registered at import time (main.py imports setup.prompts and tools)
    result = await mcp.list_prompts()
    assert result, "Expected at least one registered prompt"
    prompts_with_icons = [p for p in result if getattr(p, "icons", None)]
    assert prompts_with_icons, (
        "Expected at least one prompt to have icons; "
        "check that setup.prompts and/or synapse_prompts register with icons"
    )
    for p in prompts_with_icons[:3]:
        icons = getattr(p, "icons", [])
        assert icons, f"Prompt {getattr(p, 'name', p)} had empty icons list"
        first = icons[0]
        assert getattr(first, "src", None), "Icon should have src (data URI or URL)"
