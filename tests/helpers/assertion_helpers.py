"""Custom assertion helpers for test result dictionaries."""

from collections.abc import Sequence

from tests.helpers.tool_call_helpers import TestResultDict


def assert_error_contains(result_dict: TestResultDict, substring: str) -> None:
    """Assert that the 'error' field in result contains the given substring."""
    error_value = result_dict.get("error")
    assert isinstance(
        error_value, str
    ), f"Expected str for 'error', got {type(error_value)}"
    assert substring in error_value, f"Expected '{substring}' in error: {error_value}"


def assert_message_contains(result_dict: TestResultDict, substring: str) -> None:
    """Assert that the 'message' field in result contains the given substring."""
    message_value = result_dict.get("message")
    assert isinstance(
        message_value, str
    ), f"Expected str for 'message', got {type(message_value)}"
    assert (
        substring in message_value
    ), f"Expected '{substring}' in message: {message_value}"


def str_contains(result_dict: TestResultDict, key: str, substring: str) -> bool:
    """Check if string value at key contains substring."""
    value = result_dict.get(key)
    if not isinstance(value, str):
        return False
    return substring in value


def str_in_value(result_dict: TestResultDict, key: str, substring: str) -> bool:
    """Alias for str_contains for backward compatibility with 'in' pattern."""
    return str_contains(result_dict, key, substring)


def in_str_list(items: Sequence[str], value: str) -> bool:
    """Check if value is in list of strings."""
    return value in items


def assert_in_str(value: str, container: str) -> None:
    """Assert string contains substring."""
    assert value in container, f"Expected '{value}' in '{container}'"


def assert_in_list(value: str, items: Sequence[object]) -> None:
    """Assert value is in list."""
    assert value in items, f"Expected '{value}' in list"
