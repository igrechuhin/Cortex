"""
Integration tests for test fixture completeness.

Verifies that validated fixtures (e.g. optimization_config in Phase 4 mock_managers)
are complete against the required interface so fixture drift is caught in CI.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

from tests.helpers.fixture_validator import (
    OPTIMIZATION_CONFIG_REQUIRED_FOR_PHASE4,
    validate_mock_manager_fixture,
    validate_optimization_config_mock,
)


def _make_complete_optimization_config_mock() -> MagicMock:
    """Build optimization_config mock with all Phase 4 required members (mirrors fixture)."""
    mock = MagicMock()
    mock.get_token_budget.return_value = 10000
    mock.get_max_token_budget.return_value = 100000
    mock.get_reserve_for_response.return_value = 10000
    mock.get_priority_order.return_value = ["file1.md", "file2.md"]
    mock.get_mandatory_files.return_value = ["file1.md"]
    mock.is_summarization_enabled.return_value = True
    mock.is_optimization_enabled.return_value = True
    mock.get_summarization_target_reduction.return_value = 0.5
    mock.get_summarization_strategy.return_value = "extract_key_sections"
    return mock


def test_optimization_config_fixture_completeness_passes() -> None:
    """A mock with all OPTIMIZATION_CONFIG_REQUIRED_FOR_PHASE4 members passes validation."""
    mock = _make_complete_optimization_config_mock()

    result = validate_optimization_config_mock(mock)

    assert result.valid is True
    assert result.missing == []


def test_optimization_config_fixture_completeness_reports_missing() -> None:
    """Validation fails with actionable message when a required member is missing."""
    mock = _make_complete_optimization_config_mock()
    del mock.get_summarization_strategy

    result = validate_optimization_config_mock(mock)

    assert result.valid is False
    assert "get_summarization_strategy" in result.missing
    assert (
        "FIXTURE_MAINTENANCE" in result.message
        or "incomplete" in result.message.lower()
    )


def test_fixture_completeness_via_generic_validator() -> None:
    """Generic validate_mock_manager_fixture with Phase 4 list matches optimization_config validation."""
    mock = _make_complete_optimization_config_mock()

    result = validate_mock_manager_fixture(
        mock,
        OPTIMIZATION_CONFIG_REQUIRED_FOR_PHASE4,
        mock_name="optimization_config",
    )

    assert result.valid is True
    assert result.missing == []


def test_fixture_completeness_missing_multiple_reported() -> None:
    """All missing members are reported when multiple are absent."""
    # Use SimpleNamespace so only set attributes exist; MagicMock would auto-create the rest.
    mock = SimpleNamespace(
        get_token_budget=MagicMock(return_value=10000),
        get_max_token_budget=MagicMock(return_value=100000),
    )
    # Omit the rest

    result = validate_optimization_config_mock(mock)

    assert result.valid is False
    assert len(result.missing) == len(OPTIMIZATION_CONFIG_REQUIRED_FOR_PHASE4) - 2
    assert "get_reserve_for_response" in result.missing
    assert "get_summarization_strategy" in result.missing
