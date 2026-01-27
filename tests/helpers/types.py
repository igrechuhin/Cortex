"""Type definitions for test helpers.

This module provides type aliases for common test patterns to avoid
using dict[str, object] throughout test files.

Note: dict[str, object] is acceptable in tests when:
1. Testing JSON parsing boundaries (simulating raw JSON data)
2. Testing backward compatibility with legacy dict-based APIs
3. Testing error handling for malformed input

For new test code, prefer using Pydantic models directly.
"""

from typing import cast
from unittest.mock import AsyncMock, MagicMock

from cortex.core.models import JsonValue, ModelDict

# Type alias for mock managers dictionary used in tests.
# Tests populate this with MagicMock or AsyncMock instances.
# Note: We use MagicMock | AsyncMock | object because mock managers don't implement
# the full protocol and type checkers would otherwise complain about incompatible types.
MockManagersDict = dict[str, MagicMock | AsyncMock]

# Type alias for test managers dictionary.
# This is a permissive type for tests that need to pass mock managers
# to functions expecting ManagersDict. Using object is acceptable in tests
# because we're testing behavior, not type safety.
TestManagersDict = dict[str, MagicMock | AsyncMock]

# Type alias for raw JSON data in tests.
# Used when testing JSON parsing boundaries where data comes from json.load().
# This is acceptable because JSON can contain arbitrary nested structures.
RawJSONDict = ModelDict

# Type alias for raw JSON list data in tests.
RawJSONList = list[JsonValue]


def assert_is_list(
    value: JsonValue, error_msg: str = "Expected list"
) -> list[JsonValue]:
    """Assert that a JsonValue is a list and return it typed as list.

    Args:
        value: JsonValue to check
        error_msg: Error message if assertion fails

    Returns:
        The value typed as list[JsonValue]

    Raises:
        AssertionError: If value is not a list
    """
    assert isinstance(value, list), error_msg
    return cast(list[JsonValue], value)


def assert_is_dict(value: JsonValue, error_msg: str = "Expected dict") -> ModelDict:
    """Assert that a JsonValue is a dict and return it typed as ModelDict.

    Args:
        value: JsonValue to check
        error_msg: Error message if assertion fails

    Returns:
        The value typed as ModelDict

    Raises:
        AssertionError: If value is not a dict
    """
    assert isinstance(value, dict), error_msg
    return cast(ModelDict, value)


def get_list(value: JsonValue, key: str) -> list[JsonValue]:
    """Get a list value from a ModelDict with type narrowing.

    Args:
        value: ModelDict containing the value
        key: Key to look up

    Returns:
        The value as list[JsonValue]

    Raises:
        AssertionError: If value is not a dict or key doesn't contain a list
    """
    assert isinstance(value, dict), f"Expected dict, got {type(value)}"
    item = value[key]
    return assert_is_list(item, f"Expected {key} to be a list")


def get_dict(value: JsonValue, key: str) -> ModelDict:
    """Get a dict value from a ModelDict with type narrowing.

    Args:
        value: ModelDict containing the value
        key: Key to look up

    Returns:
        The value as ModelDict

    Raises:
        AssertionError: If value is not a dict or key doesn't contain a dict
    """
    assert isinstance(value, dict), f"Expected dict, got {type(value)}"
    item = value[key]
    return assert_is_dict(item, f"Expected {key} to be a dict")
