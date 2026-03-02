"""Unit tests for configuration_helpers."""

from cortex.tools.config import ConfigAction, parse_config_action


def test_parse_config_action_returns_none_for_none() -> None:
    """parse_config_action(None) returns None."""
    assert parse_config_action(None) is None


def test_parse_config_action_returns_enum_for_valid_values() -> None:
    """parse_config_action returns ConfigAction for valid strings."""
    assert parse_config_action("view") is ConfigAction.VIEW
    assert parse_config_action("update") is ConfigAction.UPDATE
    assert parse_config_action("reset") is ConfigAction.RESET


def test_parse_config_action_returns_none_for_invalid_value() -> None:
    """parse_config_action returns None for invalid string (ValueError branch)."""
    assert parse_config_action("unknown") is None
    assert parse_config_action("") is None
