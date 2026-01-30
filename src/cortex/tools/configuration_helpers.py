"""Helper types and functions for configuration operations."""

from enum import Enum


class ConfigAction(str, Enum):
    """Fixed set of configure() actions. Use instead of raw strings."""

    VIEW = "view"
    UPDATE = "update"
    RESET = "reset"


def parse_config_action(value: str | None) -> ConfigAction | None:
    """Parse string to ConfigAction. Returns None if invalid or missing."""
    if value is None:
        return None
    try:
        return ConfigAction(value)
    except ValueError:
        return None
