"""Regression tests for load_context effective budget calculation."""

from pathlib import Path

from cortex.optimization.config import OptimizationConfig
from cortex.tools.context.load_operations import calculate_effective_budget


def _config(tmp_path: Path) -> OptimizationConfig:
    return OptimizationConfig(tmp_path)


def test_budget_equal_to_reserve_still_loads_files(tmp_path: Path) -> None:
    # Arrange: a request exactly equal to the response reserve (10000).
    config = _config(tmp_path)
    reserve = config.get_reserve_for_response()

    # Act
    effective = calculate_effective_budget(reserve, config)

    # Assert: reserve capped at half the budget, so context is not annihilated.
    assert effective == reserve // 2
    assert effective > 0


def test_budget_below_reserve_never_returns_zero(tmp_path: Path) -> None:
    # Arrange
    config = _config(tmp_path)

    # Act / Assert: no positive request may resolve to an empty budget.
    for requested in (2, 100, 5000, 9999, 10000):
        assert calculate_effective_budget(requested, config) > 0


def test_budget_well_above_reserve_subtracts_full_reserve(tmp_path: Path) -> None:
    # Arrange
    config = _config(tmp_path)
    reserve = config.get_reserve_for_response()

    # Act
    effective = calculate_effective_budget(100000, config)

    # Assert: the cap only binds near the reserve, normal budgets are unchanged.
    assert effective == config.get_max_token_budget() - reserve


def test_unspecified_budget_fits_the_memory_bank(tmp_path: Path) -> None:
    # Arrange: None and 0 both fall through to the configured default.
    config = _config(tmp_path)

    # Act
    default_effective = calculate_effective_budget(None, config)

    # Assert: headroom over the ~12.5k-token memory bank without over-allocating.
    assert calculate_effective_budget(0, config) == default_effective
    assert 13000 <= default_effective <= 40000
