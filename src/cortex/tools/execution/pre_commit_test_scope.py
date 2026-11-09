"""Explicit selected-test scope for quality-gate requests and receipts."""

from cortex.core.models import ModelDict
from cortex.services.framework_adapters.test_selection import (
    validate_test_filter as validate_selection,
)


def validate_test_filter(value: object) -> str | None:
    """Accept an omitted filter or one nonempty, printable selection expression."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("test_filter must be a nonempty string")
    validate_selection(value)
    return value


def describe_test_scope(result: ModelDict, test_filter: str | None) -> None:
    """Keep a selected-test receipt distinct from a full-suite coverage verdict."""
    if test_filter is not None:
        result["test_filter"] = test_filter
        result["test_scope"] = "selected_tests"
        result["coverage_scope"] = "selected_tests_only"
        result["full_suite_validated"] = False
