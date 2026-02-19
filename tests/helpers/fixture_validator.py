"""
Test fixture validation helpers.

Validates that mock fixtures expose the methods/attributes required by
implementation code, to catch incomplete mock configurations early and
prevent test failures from fixture drift.

See tests/FIXTURE_REQUIREMENTS.md and tests/FIXTURE_MAINTENANCE.md.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from pydantic import BaseModel


class FixtureValidationResult(BaseModel):
    """Result of validating a mock fixture against required interface."""

    valid: bool
    """True if all required members are present and usable."""
    missing: list[str]
    """Names of required members that are missing or not callable/have no return_value."""
    message: str
    """Human-readable summary."""


# Protocol defining the optimization_config interface required by Phase 4 tools.
# Used for structural subtyping and documentation; validation uses
# OPTIMIZATION_CONFIG_REQUIRED_FOR_PHASE4.
class OptimizationConfigProtocol(Protocol):
    """Protocol for optimization config used by Phase 4 (load_context, summarize_content, etc.)."""

    def get_token_budget(self) -> int: ...
    def get_max_token_budget(self) -> int: ...
    def get_reserve_for_response(self) -> int: ...
    def get_priority_order(self) -> list[str]: ...
    def get_mandatory_files(self) -> list[str]: ...
    def is_optimization_enabled(self) -> bool: ...
    def is_summarization_enabled(self) -> bool: ...
    def get_summarization_target_reduction(self) -> float: ...
    def get_summarization_strategy(self) -> str: ...


# Methods required on optimization_config mock for Phase 4 tools
# (load_context, load_progressive_context, summarize_content, get_relevance_scores).
# Keep in sync with OptimizationConfigProtocol and implementation:
# phase4_context_operations, phase4_progressive_operations,
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


def validate_mock_manager_fixture(
    mock: object,
    required_member_names: Iterable[str],
    mock_name: str = "mock",
) -> FixtureValidationResult:
    """Validate that a mock has all required members (callable or with return_value).

    A member is considered present if the mock has the attribute and either:
    - it is callable (method), or
    - it has a 'return_value' attribute (MagicMock-style). Supports both
      MagicMock and AsyncMock.

    Args:
        mock: The manager mock to validate.
        required_member_names: Names of required methods/attributes.
        mock_name: Label for error messages (e.g. "optimization_config").

    Returns:
        FixtureValidationResult with valid=True if all required members are present,
        otherwise valid=False and missing list / message set.
    """
    required = list(required_member_names)
    missing: list[str] = []
    for name in required:
        if not _mock_has_usable_member(mock, name):
            missing.append(name)
    valid = len(missing) == 0
    if valid:
        message = f"All required {mock_name} members are present."
    else:
        message = (
            f"{mock_name} mock is missing or incomplete: {', '.join(missing)}. "
            "Update the mock fixture and see tests/FIXTURE_MAINTENANCE.md."
        )
    return FixtureValidationResult(valid=valid, missing=missing, message=message)


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
    result = validate_mock_manager_fixture(
        mock,
        OPTIMIZATION_CONFIG_REQUIRED_FOR_PHASE4,
        mock_name="optimization_config",
    )
    if not result.valid:
        result = FixtureValidationResult(
            valid=result.valid,
            missing=result.missing,
            message=(
                result.message
                + " Update the mock fixture (e.g. mock_managers in test_phase4_optimization.py)."
            ),
        )
    return result


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
