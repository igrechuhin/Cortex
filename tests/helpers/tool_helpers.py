"""Helper utilities for testing MCP tools.

FastMCP 2.0 decorates functions with @mcp.tool() which returns FunctionTool objects.
These helpers extract the underlying functions for direct testing.
"""

import json
from collections.abc import Awaitable, Callable, Sequence
from typing import TypeVar, cast

from pydantic import BaseModel

T = TypeVar("T")
DictItem = dict[str, str | int | float | bool | None | list[str]]

# Type alias for test result dictionaries.
# Uses object as value type to allow any nested JSON structure.
# Helper functions (get_str, get_list, etc.) provide type-safe access.
TestResultDict = dict[str, object]


def get_tool_fn(tool: object) -> Callable[..., Awaitable[object]]:
    """Extract the underlying function from a FunctionTool.

    FastMCP 2.0 decorates functions with @mcp.tool() which returns FunctionTool.
    This helper extracts the underlying function for direct testing.

    Args:
        tool: A FunctionTool object or regular callable

    Returns:
        The underlying async function

    Example:
        >>> from cortex.tools.file_operations import manage_file
        >>> manage_file_fn = get_tool_fn(manage_file)
        >>> result = await manage_file_fn(operation="read", file_name="test.md")
    """
    if hasattr(tool, "fn"):
        return tool.fn  # type: ignore[return-value]
    return tool  # type: ignore[return-value]


def to_dict(result: object) -> TestResultDict:
    """Convert a tool result to a dictionary for test assertions.

    Handles both Pydantic models (new style) and JSON strings (legacy).
    This helper allows tests to work with both return types during migration.

    Note: Returns TestResultDict for flexible test assertions.
    In production code, prefer using Pydantic models directly.

    Args:
        result: Tool result - either a Pydantic model or JSON string

    Returns:
        Dictionary representation of the result

    Example:
        >>> result = await manage_file(operation="read", file_name="test.md")
        >>> data = to_dict(result)
        >>> assert data["status"] == "success"
    """
    if isinstance(result, BaseModel):
        return cast(TestResultDict, result.model_dump())
    if isinstance(result, str):
        parsed: object = json.loads(result)
        if isinstance(parsed, dict):
            # Cast is safe here because isinstance verified it's a dict
            # json.loads() returns dict[str, object] for JSON objects
            return cast(TestResultDict, parsed)
        raise ValueError(f"Expected dict from JSON, got {type(parsed)}")
    if isinstance(result, dict):
        # Cast is safe here because isinstance verified it's a dict
        return cast(TestResultDict, result)
    raise ValueError(f"Cannot convert {type(result)} to dict")


def get_str(result_dict: TestResultDict, key: str) -> str:
    """Get a string value from a test result dictionary.

    Args:
        result_dict: Dictionary from to_dict()
        key: Key to retrieve

    Returns:
        The string value

    Raises:
        AssertionError: If value is not a string
    """
    value = result_dict.get(key)
    assert isinstance(value, str), f"Expected str for '{key}', got {type(value)}"
    return value


def get_int(result_dict: TestResultDict, key: str) -> int:
    """Get an integer value from a test result dictionary.

    Args:
        result_dict: Dictionary from to_dict()
        key: Key to retrieve

    Returns:
        The integer value

    Raises:
        AssertionError: If value is not an integer
    """
    value = result_dict.get(key)
    assert isinstance(value, int), f"Expected int for '{key}', got {type(value)}"
    return value


def get_bool(result_dict: TestResultDict, key: str) -> bool:
    """Get a boolean value from a test result dictionary.

    Args:
        result_dict: Dictionary from to_dict()
        key: Key to retrieve

    Returns:
        The boolean value

    Raises:
        AssertionError: If value is not a boolean
    """
    value = result_dict.get(key)
    assert isinstance(value, bool), f"Expected bool for '{key}', got {type(value)}"
    return value


def get_list(result_dict: TestResultDict, key: str) -> list[object]:
    """Get a list value from a test result dictionary.

    Args:
        result_dict: Dictionary from to_dict()
        key: Key to retrieve

    Returns:
        The list value

    Raises:
        AssertionError: If value is not a list
    """
    value: object = result_dict.get(key)
    assert isinstance(value, list), f"Expected list for '{key}', got {type(value)}"
    # Use cast after isinstance check to help pyright understand the type
    return cast(list[object], value)


def get_str_list(result_dict: TestResultDict, key: str) -> list[str]:
    """Get a list of strings from a test result dictionary.

    Args:
        result_dict: Dictionary from to_dict()
        key: Key to retrieve

    Returns:
        The list of strings

    Raises:
        AssertionError: If value is not a list of strings
    """
    value: object = result_dict.get(key)
    assert isinstance(value, list), f"Expected list for '{key}', got {type(value)}"
    # Cast to list[object] for type-safe iteration after isinstance check
    value_list = cast(list[object], value)
    # Verify all items are strings
    for i, item in enumerate(value_list):
        assert isinstance(
            item, str
        ), f"Expected str at index {i} for '{key}', got {type(item)}"
    return cast(list[str], value_list)


def get_dict_list(result_dict: TestResultDict, key: str) -> list[DictItem]:
    """Get a list of dictionaries from a test result dictionary.

    Args:
        result_dict: Dictionary from to_dict()
        key: Key to retrieve

    Returns:
        The list of dictionaries

    Raises:
        AssertionError: If value is not a list of dicts
    """
    value: object = result_dict.get(key)
    assert isinstance(value, list), f"Expected list for '{key}', got {type(value)}"
    # Cast to list[object] for type-safe iteration after isinstance check
    value_list = cast(list[object], value)
    # Verify all items are dicts
    for i, item in enumerate(value_list):
        assert isinstance(
            item, dict
        ), f"Expected dict at index {i} for '{key}', got {type(item)}"
    return cast(list[DictItem], value_list)


def get_dict(result_dict: TestResultDict, key: str) -> dict[str, object]:
    """Get a nested dict value from a test result dictionary.

    Args:
        result_dict: Dictionary from to_dict()
        key: Key to retrieve

    Returns:
        The dict value

    Raises:
        AssertionError: If value is not a dict
    """
    value: object = result_dict.get(key)
    assert isinstance(value, dict), f"Expected dict for '{key}', got {type(value)}"
    # Use cast after isinstance check to help pyright understand the type
    return cast(dict[str, object], value)


def get_nested_int(result_dict: TestResultDict, *keys: str) -> int:
    """Get a nested integer value using path of keys.

    Args:
        result_dict: Dictionary from to_dict()
        *keys: Path of keys to traverse (e.g., "summary", "count")

    Returns:
        The integer value at the nested path

    Raises:
        AssertionError: If any intermediate value is not a dict or final
        value is not int

    Example:
        >>> get_nested_int(result, "summary", "markdown_links")
        # result["summary"]["markdown_links"]
    """
    current: dict[str, object] = result_dict
    for key in keys[:-1]:
        assert isinstance(
            current, dict
        ), f"Expected dict at '{key}', got {type(current)}"
        next_val = current.get(key)
        assert isinstance(
            next_val, dict
        ), f"Expected dict for '{key}', got {type(next_val)}"
        # Cast to satisfy pyright after isinstance check
        current = cast(dict[str, object], next_val)
    final = current.get(keys[-1])
    assert isinstance(final, int), f"Expected int for '{keys[-1]}', got {type(final)}"
    return final


def get_nested_str(result_dict: TestResultDict, *keys: str) -> str:
    """Get a nested string value using path of keys.

    Args:
        result_dict: Dictionary from to_dict()
        *keys: Path of keys to traverse

    Returns:
        The string value at the nested path
    """
    current: dict[str, object] = result_dict
    for key in keys[:-1]:
        assert isinstance(
            current, dict
        ), f"Expected dict at '{key}', got {type(current)}"
        next_val = current.get(key)
        assert isinstance(
            next_val, dict
        ), f"Expected dict for '{key}', got {type(next_val)}"
        # Cast to satisfy pyright after isinstance check
        current = cast(dict[str, object], next_val)
    final = current.get(keys[-1])
    assert isinstance(final, str), f"Expected str for '{keys[-1]}', got {type(final)}"
    return final


def assert_error_contains(result_dict: TestResultDict, substring: str) -> None:
    """Assert that the 'error' field in result contains the given substring.

    Args:
        result_dict: Dictionary from to_dict()
        substring: Substring expected in the error message

    Raises:
        AssertionError: If assertion fails
    """
    error_value = result_dict.get("error")
    assert isinstance(
        error_value, str
    ), f"Expected str for 'error', got {type(error_value)}"
    assert substring in error_value, f"Expected '{substring}' in error: {error_value}"


def assert_message_contains(result_dict: TestResultDict, substring: str) -> None:
    """Assert that the 'message' field in result contains the given substring.

    Args:
        result_dict: Dictionary from to_dict()
        substring: Substring expected in the message

    Raises:
        AssertionError: If assertion fails
    """
    message_value = result_dict.get("message")
    assert isinstance(
        message_value, str
    ), f"Expected str for 'message', got {type(message_value)}"
    assert (
        substring in message_value
    ), f"Expected '{substring}' in message: {message_value}"


def str_contains(result_dict: TestResultDict, key: str, substring: str) -> bool:
    """Check if string value at key contains substring.

    Type-safe way to check string containment for dict[str, object] values.

    Args:
        result_dict: Dictionary from to_dict()
        key: Key to check
        substring: Substring to look for

    Returns:
        True if value is a string containing substring
    """
    value = result_dict.get(key)
    if not isinstance(value, str):
        return False
    return substring in value


def str_in_value(result_dict: TestResultDict, key: str, substring: str) -> bool:
    """Alias for str_contains for backward compatibility with 'in' pattern."""
    return str_contains(result_dict, key, substring)


def in_str_list(items: Sequence[str], value: str) -> bool:
    """Check if value is in list of strings.

    Type-safe way to check list containment for test assertions.

    Args:
        items: List of strings
        value: String to look for

    Returns:
        True if value is in items
    """
    return value in items


def assert_in_str(value: str, container: str) -> None:
    """Assert string contains substring.

    Args:
        value: Substring to find
        container: String to search in

    Raises:
        AssertionError: If value not in container
    """
    assert value in container, f"Expected '{value}' in '{container}'"


def assert_in_list(value: str, items: Sequence[object]) -> None:
    """Assert value is in list.

    Args:
        value: Value to find
        items: List to search in

    Raises:
        AssertionError: If value not in items
    """
    assert value in items, f"Expected '{value}' in list"
