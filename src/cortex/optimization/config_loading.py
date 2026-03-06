"""
Load, merge, and persist optimization configuration.

Uses config_defaults for the base default; tool_search is injected here
to avoid circular import with cortex.tools.structure.categories.
"""

import copy
import json
from pathlib import Path
from typing import cast

from cortex.core.async_file_utils import open_async_text_file
from cortex.core.models import ModelDict
from cortex.optimization.config_defaults import DEFAULT_OPTIMIZATION_CONFIG


def get_default_config_with_tool_search() -> ModelDict:
    """Build default config dict with tool_search injected (avoids circular import)."""
    default_config = cast(ModelDict, copy.deepcopy(DEFAULT_OPTIMIZATION_CONFIG))
    from cortex.tools.structure.categories import build_category_config

    default_config["tool_search"] = build_category_config().model_dump()
    return default_config


def load_config(config_path: Path) -> ModelDict:
    """
    Load configuration from file or return default with tool_search.

    Uses synchronous I/O for use during OptimizationConfig.__init__.
    """
    default_config = get_default_config_with_tool_search()
    if not config_path.exists():
        return default_config
    try:
        with open(config_path) as f:
            user_config_raw = cast(object, json.load(f))
    except (OSError, json.JSONDecodeError) as e:
        from cortex.core.logging_config import logger

        logger.warning("Failed to load optimization config: %s", e)
        return default_config
    if not isinstance(user_config_raw, dict):
        return default_config
    return merge_configs(default_config, cast(ModelDict, user_config_raw))


def merge_configs(default: ModelDict, user: ModelDict) -> ModelDict:
    """Recursively merge user config dict with defaults."""
    result = default.copy()
    for key, value in user.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_configs(
                cast(ModelDict, result[key]),
                cast(ModelDict, value),
            )
        else:
            result[key] = value
    return result


async def save_config_async(config_path: Path, config: ModelDict) -> bool:
    """Save configuration dict to file. Returns True if saved successfully."""
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        async with open_async_text_file(config_path, "w", "utf-8") as f:
            _ = await f.write(json.dumps(config, indent=2))
        return True
    except OSError as e:
        from cortex.core.logging_config import logger

        logger.error("Failed to save optimization config: %s", e)
        return False
