"""Usage tracking configuration loading (Phase 81 split from usage_tracker)."""

import json
from pathlib import Path
from typing import cast

from cortex.core.path_resolver import CortexResourceType, get_cortex_path


def _default_config() -> dict[str, bool | int | float | list[str]]:
    """Return default usage tracking configuration."""
    return {
        "enabled": True,
        "anonymize_params": True,
        "retention_days": 90,
        "aggregation_enabled": True,
        "opt_out_tools": [],
        "min_duration_ms": 0.0,
        "result_summary_enabled_tools": [],
    }


def _apply_config_overrides(
    config: dict[str, bool | int | float | list[str]],
    data: dict[str, object],
) -> None:
    """Merge persisted usage_tracking.json values into the default config."""
    for key in ("enabled", "anonymize_params", "aggregation_enabled"):
        val = data.get(key)
        if isinstance(val, bool):
            config[key] = val
    retention = data.get("retention_days")
    if isinstance(retention, int):
        config["retention_days"] = retention
    opt_out_raw = data.get("opt_out_tools")
    if isinstance(opt_out_raw, list):
        raw_list = cast(list[object], opt_out_raw)
        config["opt_out_tools"] = [s for s in raw_list if isinstance(s, str)]
    min_dur = data.get("min_duration_ms")
    if isinstance(min_dur, (int, float)):
        config["min_duration_ms"] = float(min_dur)
    summary_raw = data.get("result_summary_enabled_tools")
    if isinstance(summary_raw, list):
        raw_list = cast(list[object], summary_raw)
        config["result_summary_enabled_tools"] = [
            s for s in raw_list if isinstance(s, str)
        ]


def load_usage_tracker_config(
    project_root: Path,
) -> dict[str, bool | int | float | list[str]]:
    """Load usage tracking config from .cortex/config/usage_tracking.json."""
    config_dir = get_cortex_path(project_root, CortexResourceType.CONFIG)
    config_path = config_dir / "usage_tracking.json"
    if not config_path.is_file():
        return _default_config()
    try:
        with open(config_path, encoding="utf-8") as f:
            data = json.load(f)
        config = _default_config()
        if isinstance(data, dict):
            _apply_config_overrides(config, cast(dict[str, object], data))
        return config
    except (OSError, json.JSONDecodeError):
        return _default_config()


def get_tool_optimization_config(
    project_root: Path,
) -> dict[str, int]:
    """Load tool optimization threshold from .cortex/config/usage_tracking.json.

    Returns dict with keys days, min_usage_count, min_usage_threshold.
    Used as single source of truth for "tools below usage threshold" so the
    list can be tuned without code changes. Missing keys use defaults.
    """
    defaults: dict[str, int] = {
        "days": 30,
        "min_usage_count": 0,
        "min_usage_threshold": 5,
    }
    config_dir = get_cortex_path(project_root, CortexResourceType.CONFIG)
    config_path = config_dir / "usage_tracking.json"
    if not config_path.is_file():
        return defaults.copy()
    try:
        with open(config_path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return defaults.copy()
        data_dict = cast(dict[str, object], data)
        section = data_dict.get("tool_optimization")
        if not isinstance(section, dict):
            return defaults.copy()
        section_dict = cast(dict[str, object], section)
        out = defaults.copy()
        for key in ("days", "min_usage_count", "min_usage_threshold"):
            val = section_dict.get(key)
            if isinstance(val, int):
                out[key] = val
        return out
    except (OSError, json.JSONDecodeError):
        return defaults.copy()
