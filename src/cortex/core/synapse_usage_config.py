"""Synapse usage configuration loader.

When usage_writable is true in Synapse config, usage data is written to
Synapse .cache. When false or absent, Cortex operates as a static snapshot:
no statistics writes for tools, prompts, or resources.
"""

import json
from pathlib import Path
from typing import cast

from cortex.core.path_resolver import CortexResourceType, get_cortex_path


def load_synapse_usage_config(project_root: Path) -> dict[str, object]:
    """Load Synapse usage config from .cortex/synapse/config.json.

    Returns dict with usage_writable key (bool). Usage persistence is opt-in:
    when config file is missing, defaults to {"usage_writable": False}. On
    parse error or invalid content, returns False.
    """
    config_path = (
        get_cortex_path(project_root, CortexResourceType.SYNAPSE) / "config.json"
    )
    if not config_path.is_file():
        return {"usage_writable": False}
    try:
        with open(config_path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"usage_writable": False}
        data_dict = cast(dict[str, object], data)
        writable = data_dict.get("usage_writable")
        return {"usage_writable": writable is True}
    except (OSError, json.JSONDecodeError):
        return {"usage_writable": False}


def is_usage_writable(project_root: Path) -> bool:
    """Return True if Synapse config has usage_writable: true.

    When false or config missing, Cortex operates as static snapshot
    (no usage writes).
    """
    config = load_synapse_usage_config(project_root)
    return config.get("usage_writable", False) is True


def get_usage_storage_root(project_root: Path) -> Path:
    """Return cache root for usage storage when usage_writable is true.

    Returns project_root/.cortex/synapse/.cache when usage_writable and
    Synapse exists; otherwise project_root/.cortex/.cache. Callers should
    only persist when is_usage_writable() is true.
    """
    cortex_dir = get_cortex_path(project_root, CortexResourceType.CORTEX_DIR)
    synapse_dir = cortex_dir / "synapse"
    if is_usage_writable(project_root) and synapse_dir.is_dir():
        return synapse_dir / ".cache"
    return cortex_dir / ".cache"
