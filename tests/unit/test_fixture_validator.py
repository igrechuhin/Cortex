"""
Unit tests for test fixture validation helpers.

Validates that validate_optimization_config_mock and related helpers
correctly detect complete vs incomplete optimization_config mocks.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

from tests.helpers.fixture_validator import (
    OPTIMIZATION_CONFIG_REQUIRED_FOR_PHASE4,
    FixtureValidationResult,
    validate_optimization_config_mock,
)

# =============================================================================
# validate_optimization_config_mock - success
# =============================================================================


def test_validate_optimization_config_mock_complete_magic_mock_passes() -> None:
    """Validation passes when mock has all required members as MagicMock with return_value."""
    mock = MagicMock()
    mock.get_token_budget.return_value = 10000
    mock.get_max_token_budget.return_value = 100000
    mock.get_reserve_for_response.return_value = 10000
    mock.get_priority_order.return_value = ["file1.md"]
    mock.get_mandatory_files.return_value = ["file1.md"]
    mock.is_optimization_enabled.return_value = True
    mock.is_summarization_enabled.return_value = True
    mock.get_summarization_target_reduction.return_value = 0.5
    mock.get_summarization_strategy.return_value = "extract_key_sections"

    result = validate_optimization_config_mock(mock)

    assert result.valid is True
    assert result.missing == []
    assert "present" in result.message


def _dummy_callable(*args: object, **kwargs: object) -> None:
    """Dummy callable for fixture validator tests."""
    return None


def test_validate_optimization_config_mock_callable_attributes_pass() -> None:
    """Validation passes when required members are callable (e.g. real methods)."""
    mock = MagicMock()
    for name in OPTIMIZATION_CONFIG_REQUIRED_FOR_PHASE4:
        setattr(mock, name, _dummy_callable)

    result = validate_optimization_config_mock(mock)

    assert result.valid is True
    assert result.missing == []


# =============================================================================
# validate_optimization_config_mock - failure
# =============================================================================


def test_validate_optimization_config_mock_missing_one_fails() -> None:
    """Validation fails when one required member is missing."""
    # SimpleNamespace allows dynamic attributes without type errors.
    mock = SimpleNamespace(
        get_token_budget=MagicMock(return_value=10000),
        get_max_token_budget=MagicMock(return_value=100000),
        get_reserve_for_response=MagicMock(return_value=10000),
        get_priority_order=MagicMock(return_value=[]),
        get_mandatory_files=MagicMock(return_value=[]),
        is_optimization_enabled=MagicMock(return_value=True),
        is_summarization_enabled=MagicMock(return_value=True),
        get_summarization_target_reduction=MagicMock(return_value=0.5),
        # omit get_summarization_strategy
    )

    result = validate_optimization_config_mock(mock)

    assert result.valid is False
    assert "get_summarization_strategy" in result.missing
    assert len(result.missing) == 1
    assert "missing" in result.message.lower() or "incomplete" in result.message.lower()


def test_validate_optimization_config_mock_missing_several_fails() -> None:
    """Validation fails with multiple missing members listed."""
    mock = SimpleNamespace(
        get_token_budget=MagicMock(return_value=10000),
        get_max_token_budget=MagicMock(return_value=100000),
    )

    result = validate_optimization_config_mock(mock)

    assert result.valid is False
    assert len(result.missing) == len(OPTIMIZATION_CONFIG_REQUIRED_FOR_PHASE4) - 2
    assert "get_reserve_for_response" in result.missing
    assert "get_summarization_strategy" in result.missing


def test_validate_optimization_config_mock_empty_mock_fails() -> None:
    """Validation fails for object with no required attributes."""

    class Plain:
        pass

    result = validate_optimization_config_mock(Plain())

    assert result.valid is False
    assert len(result.missing) == len(OPTIMIZATION_CONFIG_REQUIRED_FOR_PHASE4)


# =============================================================================
# FixtureValidationResult
# =============================================================================


def test_fixture_validation_result_model() -> None:
    """FixtureValidationResult is a valid Pydantic model with expected fields."""
    r = FixtureValidationResult(valid=True, missing=[], message="OK")
    assert r.valid is True
    assert r.missing == []
    assert r.message == "OK"

    r2 = FixtureValidationResult(
        valid=False, missing=["a", "b"], message="Missing a, b"
    )
    assert r2.valid is False
    assert r2.missing == ["a", "b"]
    assert r2.message == "Missing a, b"


# =============================================================================
# OPTIMIZATION_CONFIG_REQUIRED_FOR_PHASE4
# =============================================================================


def test_optimization_config_required_phase4_non_empty() -> None:
    """Required Phase 4 list is non-empty and contains expected methods."""
    assert len(OPTIMIZATION_CONFIG_REQUIRED_FOR_PHASE4) >= 9
    assert "is_optimization_enabled" in OPTIMIZATION_CONFIG_REQUIRED_FOR_PHASE4
    assert "is_summarization_enabled" in OPTIMIZATION_CONFIG_REQUIRED_FOR_PHASE4
    assert "get_summarization_strategy" in OPTIMIZATION_CONFIG_REQUIRED_FOR_PHASE4
    assert "get_token_budget" in OPTIMIZATION_CONFIG_REQUIRED_FOR_PHASE4
