# Copyright (c) 2025 Cortex and contributors. All rights reserved.
# SPDX-License-Identifier: MIT

"""Setup prompts that are always available regardless of project configuration.

setup_synapse is registered on the main MCP server when this module is
imported so it is available even when the project is fully configured.
"""

from cortex.core.icon_helpers import create_emoji_icon
from cortex.server import mcp

_SETUP_SYNAPSE_ICON = "🔗"

_SETUP_SYNAPSE_PROMPT_TEMPLATE = """Please setup Synapse in my project.

I want to use Synapse from: {synapse_repo_url}

Synapse is a shared repository that contains both rules and prompts for
cross-project sharing.

I need you to:
1. Add the Synapse repository as a Git submodule
2. Clone it to .cortex/synapse/
3. Create the rules index
4. Validate the structure (should have rules/ and prompts/ subdirectories)
5. Load the rules and prompts manifests

Commands to run:
git submodule add {synapse_repo_url} .cortex/synapse/
git submodule update --init --recursive

Expected structure:
.cortex/synapse/
├── LICENSE
├── rules/
│   ├── rules-manifest.json
│   ├── general/
│   ├── python/
│   └── ...
└── prompts/
    ├── prompts-manifest.json
    ├── general/
    ├── python/
    └── ...

Expected output format:
{{
  "status": "success",
  "message": "Synapse setup successfully",
  "synapse_path": ".cortex/synapse/",
  "rules_count": <count>,
  "prompts_count": <count>,
  "submodule_url": "{synapse_repo_url}",
  "commit": "<commit_hash>"
}}"""


@mcp.prompt(icons=[create_emoji_icon(_SETUP_SYNAPSE_ICON)])
def setup_synapse(
    synapse_repo_url: str = "https://github.com/igrechuhin/Synapse.git",
) -> str:
    """Setup Synapse via Git submodule (always available).

    Args:
        synapse_repo_url: URL of Synapse repository (default provided)
    """
    return _SETUP_SYNAPSE_PROMPT_TEMPLATE.format(synapse_repo_url=synapse_repo_url)
