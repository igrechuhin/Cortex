"""
Dynamic Prompts Registration

This module loads prompts from two locations and registers them as MCP prompts:
1. .cortex/synapse/prompts/ - Shared prompts from Synapse (language-agnostic)
2. .cortex/prompts/ - Project-specific prompts (e.g., Cortex MCP tools)

Prompts are loaded synchronously at import time to enable decorator registration.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

from cortex.core.models import ModelDict
from cortex.server import mcp
from cortex.tools.synapse.prompts_agents import (
    get_claude_agents_target,
    get_cursor_agents_source,
    get_cursor_agents_target,
    inject_tools_into_frontmatter,
    sync_cursor_agents,
)
from cortex.tools.synapse.prompts_content import (
    CLAUDE_CODE_TOOLS_FIELD,
    DEFAULT_PROMPT_ICON,
    SYNAPSE_PROMPT_ICONS,
)
from cortex.tools.synapse.prompts_paths import (
    get_prompts_paths,
    get_synapse_prompts_path,
    load_prompt_content,
    load_prompts_manifest,
)
from cortex.tools.synapse.prompts_registration import (
    create_prompt_function as _create_prompt_function_impl,
)
from cortex.tools.synapse.prompts_registration import (
    log_registration_summary as _log_registration_summary_impl,
)
from cortex.tools.synapse.prompts_registration import (
    process_prompt_info as _process_prompt_info_impl,
)
from cortex.tools.synapse.prompts_registration import (
    register_prompts_from_path as _register_prompts_from_path_impl,
)
from cortex.tools.synapse.prompts_registration import (
    register_synapse_prompts_for_facade,
)

# Explicitly reference mcp to satisfy type checker (module imported for registration side effects)
_ = mcp

__all__ = [
    "CLAUDE_CODE_TOOLS_FIELD",
    "DEFAULT_PROMPT_ICON",
    "SYNAPSE_PROMPT_ICONS",
    "create_prompt_function",
    "get_claude_agents_target",
    "get_cursor_agents_source",
    "get_cursor_agents_target",
    "get_prompts_paths",
    "get_synapse_prompts_path",
    "inject_tools_into_frontmatter",
    "load_prompt_content",
    "load_prompts_manifest",
    "log_registration_summary",
    "process_prompt_info",
    "register_prompts_from_path",
    "register_synapse_prompts",
    "sync_cursor_agents",
]


def _facade() -> ModuleType:
    return sys.modules[__name__]


def create_prompt_function(
    name: str,
    content: str,
    description: str,
    icon_emoji: str | None = None,
) -> None:
    """Create and register a prompt function dynamically."""
    _create_prompt_function_impl(_facade(), name, content, description, icon_emoji)


def process_prompt_info(
    prompt_info: ModelDict, prompts_path: Path, category_name: str
) -> int:
    """Process a single prompt info and register it."""
    return _process_prompt_info_impl(
        _facade(), prompt_info, prompts_path, category_name
    )


def log_registration_summary(registered_count: int) -> None:
    """Log registration summary and verify functions exist."""
    _log_registration_summary_impl(_facade(), registered_count)


def register_prompts_from_path(prompts_path: Path) -> int:
    """Load and register prompts from a single path."""
    return _register_prompts_from_path_impl(_facade(), prompts_path)


def register_synapse_prompts() -> None:
    """Load and register all prompts from Synapse and project-specific directories."""
    register_synapse_prompts_for_facade(_facade())


# Register prompts and sync cursor agents at import time
register_synapse_prompts()
sync_cursor_agents()
