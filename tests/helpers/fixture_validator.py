"""
Test fixture validation helpers.

Validates that mock fixtures expose the methods/attributes required by
implementation code, to catch incomplete mock configurations early and
prevent test failures from fixture drift.

See tests/FIXTURE_REQUIREMENTS.md and tests/FIXTURE_MAINTENANCE.md.
"""

from __future__ import annotations

from pydantic import BaseModel


class FixtureValidationResult(BaseModel):
    """Result of validating a mock fixture against required interface."""

    valid: bool
    """True if all required members are present and usable."""
    missing: list[str]
    """Names of required members that are missing or not callable/have no return_value."""
    message: str
    """Human-readable summary."""


# Methods required on optimization_config mock for Phase 4 tools
# (load_context, load_progressive_context, summarize_content, get_relevance_scores).
# Keep in sync with: phase4_context_operations, phase4_progressive_operations,
# phase4_summarization_operations, phase4_optimization_handlers.
OPTIMIZATION_CONFIG_REQUIRED_FOR_PHASE4: tuple[str, ...] = (
    "get_token_budget",
    "get_max_token_budget",
    "get_reserve_for_response",
    "get_priority_order",
    "get_mandatory_files",
    "is_optimization_enabled",
    "is_summarization_enabled",
    "get_summarization_target_reduction",
    "get_summarization_strategy",
)


def validate_optimization_config_mock(mock: object) -> FixtureValidationResult:
    """Validate that an optimization_config mock has all members required by Phase 4 tools.

    A member is considered present if the mock has the attribute and either:
    - it is callable (method), or
    - it has a 'return_value' attribute (MagicMock-style).

    Args:
        mock: The optimization_config mock (e.g. MagicMock() with .return_value set).

    Returns:
        FixtureValidationResult with valid=True if all required members are present,
        otherwise valid=False and missing list / message set.
    """
    missing: list[str] = []
    for name in OPTIMIZATION_CONFIG_REQUIRED_FOR_PHASE4:
        if not _mock_has_usable_member(mock, name):
            missing.append(name)
    valid = len(missing) == 0
    if valid:
        message = "All required optimization_config members are present."
    else:
        message = (
            f"optimization_config mock is missing or incomplete: {', '.join(missing)}. "
            "Update the mock fixture (e.g. mock_managers in test_phase4_optimization.py) "
            "and see tests/FIXTURE_MAINTENANCE.md."
        )
    return FixtureValidationResult(valid=valid, missing=missing, message=message)


def _mock_has_usable_member(mock: object, name: str) -> bool:
    """Return True if mock has a usable attribute for name (callable or has return_value)."""
    if not hasattr(mock, name):
        return False
    attr = getattr(mock, name)
    if callable(attr):
        return True
    if hasattr(attr, "return_value"):
        return True
    return False
