"""Tests for rules section filtering by task type."""

from cortex.core.models import TaskType
from cortex.core.rules_filter import filter_rules

_RULES = """## Universal
<!-- task_types: ALL -->
Always keep this.

## Python
<!-- task_types: CORE_LOGIC, SCHEMA -->
Python-only rule.

## MCP
<!-- task_types: MCP_TOOL -->
MCP-only rule.
"""


def test_filter_rules_keeps_universal_and_matching_sections() -> None:
    # Arrange / Act
    filtered = filter_rules(_RULES, [TaskType.CORE_LOGIC])

    # Assert
    assert "Always keep this." in filtered
    assert "Python-only rule." in filtered
    assert "MCP-only rule." not in filtered


def test_filter_rules_keeps_all_when_all_requested() -> None:
    # Arrange / Act
    filtered = filter_rules(_RULES, [TaskType.ALL])

    # Assert
    assert "Always keep this." in filtered
    assert "Python-only rule." in filtered
    assert "MCP-only rule." in filtered
