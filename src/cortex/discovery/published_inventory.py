"""Canonical published MCP surface for documentation and CI drift checks.

**Tools:** :data:`~cortex.tools.structure.categories.TOOL_CATEGORIES` is the
single source of truth for MCP ``tools/list`` names (enforced by
``tests/tools/test_tool_categories_governance.py``).

**Static resources:** :data:`PUBLISHED_STATIC_RESOURCE_URIS` must stay aligned
with ``@mcp.resource(uri=...)`` registrations under ``src/cortex/tools/``.

**Prompts:** Setup prompts are registered in ``cortex.setup.prompts`` and
``cortex.setup.prompts_always``; at most one conditional block from
``prompts.py`` is active per process, so clients never see all four at once.
The ``max_exposed`` field is the count if every registration were mounted.
"""

from __future__ import annotations

import json
from typing import Final

from cortex.tools.structure.categories import TOOL_CATEGORIES

# Keep in sync with @mcp.resource(uri="cortex://...") under src/cortex/tools/.
PUBLISHED_STATIC_RESOURCE_URIS: Final[tuple[str, ...]] = (
    "cortex://health/connection",
    "cortex://structure",
    "cortex://context",
    "cortex://rules",
    "cortex://validation",
    "cortex://analysis",
)

SETUP_PROMPT_ALWAYS: Final[tuple[str, ...]] = ("setup_synapse",)
SETUP_PROMPTS_CONDITIONAL: Final[tuple[str, ...]] = (
    "initialize",
    "migrate",
    "populate_tiktoken_cache",
)


def published_tool_names() -> list[str]:
    """Sorted MCP tool names from :data:`TOOL_CATEGORIES`."""
    return sorted(entry.name for entry in TOOL_CATEGORIES)


def published_inventory_payload() -> dict[str, object]:
    """Serializable snapshot for ``docs/_generated/tool-inventory.json``."""
    max_prompts = len(SETUP_PROMPT_ALWAYS) + len(SETUP_PROMPTS_CONDITIONAL)
    return {
        "schema_version": 1,
        "tools_count": len(TOOL_CATEGORIES),
        "tool_names": published_tool_names(),
        "static_resources": list(PUBLISHED_STATIC_RESOURCE_URIS),
        "resources_count": len(PUBLISHED_STATIC_RESOURCE_URIS),
        "prompts": {
            "always": list(SETUP_PROMPT_ALWAYS),
            "conditional": list(SETUP_PROMPTS_CONDITIONAL),
            "max_exposed": max_prompts,
        },
    }


def published_inventory_json() -> str:
    """Pretty JSON (trailing newline) for generated docs and tests."""
    return json.dumps(published_inventory_payload(), indent=2, sort_keys=True) + "\n"
