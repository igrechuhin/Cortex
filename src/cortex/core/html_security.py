"""HTML escaping helpers for security-sensitive output.

Extracted from ``security.py`` as part of Phase 81
(oversized module reduction wave 1).
"""

from __future__ import annotations

import html
from typing import cast

from cortex.core.models import JsonDict, JsonList, JsonValue, ModelDict


class HTMLEscaper:
    """Escape HTML content to prevent XSS attacks in exported content.

    Provides HTML escaping for content that may be rendered in web contexts,
    preventing cross-site scripting (XSS) vulnerabilities.
    """

    @staticmethod
    def escape(content: str) -> str:
        """Escape HTML special characters in content.

        Escapes: < > & " '

        Args:
            content: The content to escape

        Returns:
            HTML-escaped content safe for web display
        """
        # Use standard library html.escape for reliable escaping
        # quote=True escapes both " and '
        return html.escape(content, quote=True)

    @staticmethod
    def escape_dict(data: JsonDict | ModelDict) -> ModelDict:
        """Recursively escape all string values in a dictionary.

        Args:
            data: JsonDict or dict with potentially unsafe string values

        Returns:
            New dict with all string values HTML-escaped
        """
        data_dict = data.to_dict() if isinstance(data, JsonDict) else data
        return HTMLEscaper._escape_dict_recursive(dict(data_dict))

    @staticmethod
    def _escape_dict_recursive(data: ModelDict) -> ModelDict:
        """Recursively escape string values in a dictionary."""
        result_dict: ModelDict = {}
        for key, value in data.items():
            if isinstance(value, str):
                result_dict[key] = HTMLEscaper.escape(value)
            elif isinstance(value, dict):
                escaped = HTMLEscaper._escape_dict_recursive(cast(ModelDict, value))
                result_dict[key] = escaped
            elif isinstance(value, list):
                nested_list = JsonList.from_list(value)
                escaped = HTMLEscaper._escape_list_recursive(nested_list)
                result_dict[key] = escaped.to_list()
            else:
                # int, float, bool, None - pass through unchanged
                result_dict[key] = value
        return result_dict

    @staticmethod
    def _escape_list_recursive(data: JsonList) -> JsonList:
        """Recursively escape string values in a list."""
        result_list: list[JsonValue] = []
        data_list = data.to_list()
        for item in data_list:
            if isinstance(item, str):
                result_list.append(HTMLEscaper.escape(item))
            elif isinstance(item, dict):
                escaped = HTMLEscaper._escape_dict_recursive(cast(ModelDict, item))
                result_list.append(escaped)
            elif isinstance(item, list):
                nested_list = JsonList.from_list(item)
                escaped = HTMLEscaper._escape_list_recursive(nested_list)
                result_list.append(escaped.to_list())
            else:
                result_list.append(item)
        return JsonList.from_list(result_list)
