"""Tool invocation and response helpers for testing MCP tools.

Extract underlying functions from FastMCP FunctionTool, convert results to dicts,
and provide type-safe accessors for test result dictionaries.
"""

import json
from collections.abc import Awaitable, Callable
from typing import cast

from pydantic import BaseModel

DictItem = dict[str, str | int | float | bool | None | list[str]]
TestResultDict = dict[str, object]


def get_tool_fn(tool: object) -> Callable[..., Awaitable[object]]:
    """Extract the underlying function from a FunctionTool.

    FastMCP 2.0 decorates functions with @mcp.tool() which returns FunctionTool.
    This helper extracts the underlying function for direct testing.

    Args:
        tool: A FunctionTool object or regular callable

    Returns:
        The underlying async function
    """
    if hasattr(tool, "fn"):
        return tool.fn  # type: ignore[return-value]
    return tool  # type: ignore[return-value]


def to_dict(result: object) -> TestResultDict:
    """Convert a tool result to a dictionary for test assertions.

    Handles both Pydantic models (new style) and JSON strings (legacy).

    Args:
        result: Tool result - either a Pydantic model or JSON string

    Returns:
        Dictionary representation of the result
    """
    if isinstance(result, BaseModel):
        return cast(TestResultDict, result.model_dump())
    if isinstance(result, str):
        parsed: object = json.loads(result)
        if isinstance(parsed, dict):
            return cast(TestResultDict, parsed)
        raise ValueError(f"Expected dict from JSON, got {type(parsed)}")
    if isinstance(result, dict):
        return cast(TestResultDict, result)
    raise ValueError(f"Cannot convert {type(result)} to dict")


def get_str(result_dict: TestResultDict, key: str) -> str:
    """Get a string value from a test result dictionary."""
    value = result_dict.get(key)
    assert isinstance(value, str), f"Expected str for '{key}', got {type(value)}"
    return value


def get_int(result_dict: TestResultDict, key: str) -> int:
    """Get an integer value from a test result dictionary."""
    value = result_dict.get(key)
    assert isinstance(value, int), f"Expected int for '{key}', got {type(value)}"
    return value


def get_bool(result_dict: TestResultDict, key: str) -> bool:
    """Get a boolean value from a test result dictionary."""
    value = result_dict.get(key)
    assert isinstance(value, bool), f"Expected bool for '{key}', got {type(value)}"
    return value


def get_list(result_dict: TestResultDict, key: str) -> list[object]:
    """Get a list value from a test result dictionary."""
    value: object = result_dict.get(key)
    assert isinstance(value, list), f"Expected list for '{key}', got {type(value)}"
    return cast(list[object], value)


def get_str_list(result_dict: TestResultDict, key: str) -> list[str]:
    """Get a list of strings from a test result dictionary."""
    value: object = result_dict.get(key)
    assert isinstance(value, list), f"Expected list for '{key}', got {type(value)}"
    value_list = cast(list[object], value)
    for i, item in enumerate(value_list):
        assert isinstance(
            item, str
        ), f"Expected str at index {i} for '{key}', got {type(item)}"
    return cast(list[str], value_list)


def get_dict_list(result_dict: TestResultDict, key: str) -> list[DictItem]:
    """Get a list of dictionaries from a test result dictionary."""
    value: object = result_dict.get(key)
    assert isinstance(value, list), f"Expected list for '{key}', got {type(value)}"
    value_list = cast(list[object], value)
    for i, item in enumerate(value_list):
        assert isinstance(
            item, dict
        ), f"Expected dict at index {i} for '{key}', got {type(item)}"
    return cast(list[DictItem], value_list)


def get_dict(result_dict: TestResultDict, key: str) -> dict[str, object]:
    """Get a nested dict value from a test result dictionary."""
    value: object = result_dict.get(key)
    assert isinstance(value, dict), f"Expected dict for '{key}', got {type(value)}"
    return cast(dict[str, object], value)


def get_nested_int(result_dict: TestResultDict, *keys: str) -> int:
    """Get a nested integer value using path of keys."""
    current: dict[str, object] = result_dict
    for key in keys[:-1]:
        assert isinstance(
            current, dict
        ), f"Expected dict at '{key}', got {type(current)}"
        next_val = current.get(key)
        assert isinstance(
            next_val, dict
        ), f"Expected dict for '{key}', got {type(next_val)}"
        current = cast(dict[str, object], next_val)
    final = current.get(keys[-1])
    assert isinstance(final, int), f"Expected int for '{keys[-1]}', got {type(final)}"
    return final


def get_nested_str(result_dict: TestResultDict, *keys: str) -> str:
    """Get a nested string value using path of keys."""
    current: dict[str, object] = result_dict
    for key in keys[:-1]:
        assert isinstance(
            current, dict
        ), f"Expected dict at '{key}', got {type(current)}"
        next_val = current.get(key)
        assert isinstance(
            next_val, dict
        ), f"Expected dict for '{key}', got {type(next_val)}"
        current = cast(dict[str, object], next_val)
    final = current.get(keys[-1])
    assert isinstance(final, str), f"Expected str for '{keys[-1]}', got {type(final)}"
    return final
