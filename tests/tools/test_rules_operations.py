"""
Comprehensive tests for Rules Operations Tools

This test suite provides comprehensive coverage for:
- rules() consolidated tool
- check_rules_enabled()
- handle_index_operation()
- validate_get_relevant_params()
- resolve_config_defaults()
- extract_all_rules()
- calculate_total_tokens()
- handle_get_relevant_operation()
- build_get_relevant_response()
- dispatch_operation()
- All error paths and edge cases
"""

import json
from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cortex.core.models import ModelDict
from cortex.managers.types import ManagersDict
from cortex.optimization.models import RulesManagerStatusModel
from cortex.tools.rules_operations import (
    build_get_relevant_response,
    calculate_total_tokens,
    check_rules_enabled,
    dispatch_operation,
    extract_all_rules,
    handle_get_relevant_operation,
    handle_index_operation,
    resolve_config_defaults,
    rules,
    validate_get_relevant_params,
)
from tests.helpers.managers import make_test_managers


def _get_manager_helper(mgrs: ManagersDict, key: str, _: object) -> object:
    """Helper function to get manager by field name."""
    return getattr(mgrs, key)


@pytest.fixture(autouse=True)
def _patch_get_manager() -> object:  # pyright: ignore[reportUnusedFunction]
    """Patch strict get_manager() to allow MagicMocks in tool tests."""
    with patch(
        "cortex.tools.rules_operations.get_manager", side_effect=_get_manager_helper
    ):
        yield


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_project_root(tmp_path: Path) -> Path:
    """Create mock project root."""
    return tmp_path


@pytest.fixture
def mock_optimization_config_enabled() -> MagicMock:
    """Create mock optimization config with rules enabled."""
    config = MagicMock()
    config.is_rules_enabled.return_value = True
    config.get_rules_max_tokens.return_value = 5000
    config.get_rules_min_relevance.return_value = 0.6
    return config


@pytest.fixture
def mock_optimization_config_disabled() -> MagicMock:
    """Create mock optimization config with rules disabled."""
    config = MagicMock()
    config.is_rules_enabled.return_value = False
    return config


@pytest.fixture
def mock_rules_manager() -> MagicMock:
    """Create mock rules manager."""
    manager = MagicMock()
    manager.index_rules = AsyncMock(
        return_value={
            "indexed": 42,
            "total_tokens": 15234,
            "cache_hit": False,
            "index_time_seconds": 2.5,
            "rules_folder": ".cursor/rules",
            "rules_by_category": {"generic": 15, "language_specific": 20, "local": 7},
        }
    )
    manager.get_relevant_rules = AsyncMock(
        return_value={
            "generic_rules": [
                {
                    "file": "error-handling.mdc",
                    "category": "generic",
                    "relevance_score": 0.78,
                    "tokens": 620,
                    "title": "Error Handling Patterns",
                    "content": "Always validate inputs...",
                    "metadata": {"tags": ["errors", "validation"]},
                }
            ],
            "language_rules": [
                {
                    "file": "python-async.mdc",
                    "category": "language_specific",
                    "relevance_score": 0.92,
                    "tokens": 850,
                    "title": "Python Async Best Practices",
                    "content": "Use asyncio.timeout()...",
                    "metadata": {
                        "language": "python",
                        "tags": ["async", "concurrency"],
                    },
                }
            ],
            "local_rules": [],
            "total_tokens": 1470,
            "context": {"filtered_count": 5, "truncated_count": 2},
            "source": "indexed",
        }
    )
    manager.get_status.return_value = RulesManagerStatusModel(
        enabled=True,
        rules_folder=".cursor/rules",
        indexed_files=42,
        last_indexed="2026-01-04T10:30:00Z",
        total_tokens=15234,
    )
    return manager


@pytest.fixture
def mock_managers_enabled(
    mock_optimization_config_enabled: MagicMock, mock_rules_manager: MagicMock
) -> ManagersDict:
    """Create typed mock managers container with rules enabled."""
    return make_test_managers(
        optimization_config=mock_optimization_config_enabled,
        rules_manager=mock_rules_manager,
    )


@pytest.fixture
def mock_managers_disabled(
    mock_optimization_config_disabled: MagicMock, mock_rules_manager: MagicMock
) -> ManagersDict:
    """Create typed mock managers container with rules disabled."""
    return make_test_managers(
        optimization_config=mock_optimization_config_disabled,
        rules_manager=mock_rules_manager,
    )


# ============================================================================
# Test check_rules_enabled
# ============================================================================


@pytest.mark.asyncio
async def test_check_rules_enabled_when_enabled(
    mock_optimization_config_enabled: MagicMock,
) -> None:
    """Test check_rules_enabled returns None when rules enabled."""
    # Act
    result = await check_rules_enabled(mock_optimization_config_enabled)

    # Assert
    assert result is None
    mock_optimization_config_enabled.is_rules_enabled.assert_called_once()


@pytest.mark.asyncio
async def test_check_rules_enabled_when_disabled(
    mock_optimization_config_disabled: MagicMock,
) -> None:
    """Test check_rules_enabled returns error message when rules disabled."""
    # Act
    result = await check_rules_enabled(mock_optimization_config_disabled)

    # Assert
    assert result is not None
    result_dict = json.loads(result)
    assert result_dict["status"] == "disabled"
    assert "disabled" in result_dict["message"].lower()
    mock_optimization_config_disabled.is_rules_enabled.assert_called_once()


# ============================================================================
# Test handle_index_operation
# ============================================================================


@pytest.mark.asyncio
async def test_handle_index_operation_success(mock_rules_manager: MagicMock) -> None:
    """Test handle_index_operation with successful indexing."""
    # Act
    result = await handle_index_operation(mock_rules_manager, force=False)

    # Assert
    result_dict = json.loads(result)
    assert result_dict["status"] == "success"
    assert result_dict["operation"] == "index"
    assert result_dict["result"]["indexed"] == 42
    assert result_dict["result"]["total_tokens"] == 15234
    mock_rules_manager.index_rules.assert_called_once_with(force=False)


@pytest.mark.asyncio
async def test_handle_index_operation_with_force(mock_rules_manager: MagicMock) -> None:
    """Test handle_index_operation with force=True."""
    # Act
    result = await handle_index_operation(mock_rules_manager, force=True)

    # Assert
    result_dict = json.loads(result)
    assert result_dict["status"] == "success"
    assert result_dict["operation"] == "index"
    mock_rules_manager.index_rules.assert_called_once_with(force=True)


# ============================================================================
# Test validate_get_relevant_params
# ============================================================================


@pytest.mark.asyncio
async def test_validate_get_relevant_params_valid() -> None:
    """Test validate_get_relevant_params with valid task description."""
    # Act
    result = await validate_get_relevant_params("Implementing async file operations")

    # Assert
    assert result is None


@pytest.mark.asyncio
async def test_validate_get_relevant_params_none() -> None:
    """Test validate_get_relevant_params with None task description."""
    # Act
    result = await validate_get_relevant_params(None)

    # Assert
    assert result is not None
    result_dict = json.loads(result)
    assert result_dict["status"] == "error"
    assert "required" in result_dict["error"].lower()


@pytest.mark.asyncio
async def test_validate_get_relevant_params_empty() -> None:
    """Test validate_get_relevant_params with empty task description."""
    # Act
    result = await validate_get_relevant_params("")

    # Assert
    assert result is not None
    result_dict = json.loads(result)
    assert result_dict["status"] == "error"


# ============================================================================
# Test resolve_config_defaults
# ============================================================================


def test_resolve_config_defaults_both_provided(
    mock_optimization_config_enabled: MagicMock,
) -> None:
    """Test resolve_config_defaults when both params provided."""
    # Act
    max_tokens, min_score = resolve_config_defaults(
        mock_optimization_config_enabled, 3000, 0.8
    )

    # Assert
    assert max_tokens == 3000
    assert min_score == 0.8
    mock_optimization_config_enabled.get_rules_max_tokens.assert_not_called()
    mock_optimization_config_enabled.get_rules_min_relevance.assert_not_called()


def test_resolve_config_defaults_both_none(
    mock_optimization_config_enabled: MagicMock,
) -> None:
    """Test resolve_config_defaults when both params are None."""
    # Act
    max_tokens, min_score = resolve_config_defaults(
        mock_optimization_config_enabled, None, None
    )

    # Assert
    assert max_tokens == 5000  # Default from config
    assert min_score == 0.6  # Default from config
    mock_optimization_config_enabled.get_rules_max_tokens.assert_called_once()
    mock_optimization_config_enabled.get_rules_min_relevance.assert_called_once()


def test_resolve_config_defaults_max_tokens_provided(
    mock_optimization_config_enabled: MagicMock,
) -> None:
    """Test resolve_config_defaults when only max_tokens provided."""
    # Act
    max_tokens, min_score = resolve_config_defaults(
        mock_optimization_config_enabled, 3000, None
    )

    # Assert
    assert max_tokens == 3000
    assert min_score == 0.6  # Default from config
    mock_optimization_config_enabled.get_rules_max_tokens.assert_not_called()
    mock_optimization_config_enabled.get_rules_min_relevance.assert_called_once()


def test_resolve_config_defaults_min_score_provided(
    mock_optimization_config_enabled: MagicMock,
) -> None:
    """Test resolve_config_defaults when only min_relevance_score provided."""
    # Act
    max_tokens, min_score = resolve_config_defaults(
        mock_optimization_config_enabled, None, 0.8
    )

    # Assert
    assert max_tokens == 5000  # Default from config
    assert min_score == 0.8
    mock_optimization_config_enabled.get_rules_max_tokens.assert_called_once()
    mock_optimization_config_enabled.get_rules_min_relevance.assert_not_called()


# ============================================================================
# Test extract_all_rules
# ============================================================================


def test_extract_all_rules_all_categories() -> None:
    """Test extract_all_rules with all three categories."""
    # Arrange
    rules_dict = {
        "generic_rules": [{"id": 1}, {"id": 2}],
        "language_rules": [{"id": 3}, {"id": 4}],
        "local_rules": [{"id": 5}],
    }

    # Act
    result = extract_all_rules(cast(ModelDict, rules_dict))

    # Assert
    assert len(result) == 5
    assert {"id": 1} in result
    assert {"id": 5} in result


def test_extract_all_rules_some_categories() -> None:
    """Test extract_all_rules with only some categories."""
    # Arrange
    rules_dict = {
        "generic_rules": [{"id": 1}, {"id": 2}],
        "language_rules": [],
    }

    # Act
    result = extract_all_rules(cast(ModelDict, rules_dict))

    # Assert
    assert len(result) == 2
    assert {"id": 1} in result


def test_extract_all_rules_empty() -> None:
    """Test extract_all_rules with empty dictionary."""
    # Arrange
    rules_dict: ModelDict = {}

    # Act
    result = extract_all_rules(rules_dict)

    # Assert
    assert len(result) == 0


def test_extract_all_rules_non_list_values() -> None:
    """Test extract_all_rules with non-list values."""
    # Arrange
    rules_dict = {
        "generic_rules": "not a list",
        "language_rules": [{"id": 1}],
        "local_rules": None,
    }

    # Act
    result = extract_all_rules(cast(ModelDict, rules_dict))

    # Assert
    assert len(result) == 1
    assert {"id": 1} in result


# ============================================================================
# Test calculate_total_tokens
# ============================================================================


def test_calculate_total_tokens_from_dict() -> None:
    """Test calculate_total_tokens using total_tokens from dict."""
    # Arrange
    rules_dict: ModelDict = {"total_tokens": 1500}
    all_rules: list[ModelDict] = []

    # Act
    result = calculate_total_tokens(rules_dict, all_rules)

    # Assert
    assert result == 1500


def test_calculate_total_tokens_from_rules() -> None:
    """Test calculate_total_tokens by summing rules."""
    # Arrange
    rules_dict: ModelDict = {
        "total_tokens": None
    }  # Non-int/float value triggers rule summing
    all_rules: list[ModelDict] = [
        {"tokens": 500},
        {"tokens": 700},
        {"tokens": 300},
    ]

    # Act
    result = calculate_total_tokens(rules_dict, all_rules)

    # Assert
    assert result == 1500


def test_calculate_total_tokens_mixed_types() -> None:
    """Test calculate_total_tokens with mixed token types."""
    # Arrange
    rules_dict: ModelDict = {
        "total_tokens": "invalid"
    }  # Non-int/float value triggers rule summing
    all_rules: list[ModelDict] = [
        {"tokens": 500},
        {"tokens": 700.5},  # Float
        {"tokens": "invalid"},  # Invalid type
        {"name": "no_tokens"},  # Missing tokens key
    ]

    # Act
    result = calculate_total_tokens(rules_dict, all_rules)

    # Assert
    assert result == 1200  # 500 + 700 (rounded from 700.5)


def test_calculate_total_tokens_zero() -> None:
    """Test calculate_total_tokens with no tokens."""
    # Arrange
    rules_dict: ModelDict = {}
    all_rules: list[ModelDict] = []

    # Act
    result = calculate_total_tokens(rules_dict, all_rules)

    # Assert
    assert result == 0


# ============================================================================
# Test handle_get_relevant_operation
# ============================================================================


@pytest.mark.asyncio
async def test_handle_get_relevant_operation_success(
    mock_rules_manager: MagicMock, mock_optimization_config_enabled: MagicMock
) -> None:
    """Test handle_get_relevant_operation with successful retrieval."""
    # Act
    result = await handle_get_relevant_operation(
        mock_rules_manager,
        mock_optimization_config_enabled,
        "Implementing async file operations",
        5000,
        0.7,
    )

    # Assert
    result_dict = json.loads(result)
    assert result_dict["status"] == "success"
    assert result_dict["operation"] == "get_relevant"
    assert result_dict["task_description"] == "Implementing async file operations"
    assert result_dict["max_tokens"] == 5000
    assert result_dict["min_relevance_score"] == 0.7
    assert result_dict["rules_count"] == 2  # generic + language rules
    assert result_dict["total_tokens"] == 1470
    mock_rules_manager.get_relevant_rules.assert_called_once()


@pytest.mark.asyncio
async def test_handle_get_relevant_operation_defaults(
    mock_rules_manager: MagicMock, mock_optimization_config_enabled: MagicMock
) -> None:
    """Test handle_get_relevant_operation with default parameters."""
    # Act
    result = await handle_get_relevant_operation(
        mock_rules_manager,
        mock_optimization_config_enabled,
        "Implementing async file operations",
        None,  # Use config default
        None,  # Use config default
    )

    # Assert
    result_dict = json.loads(result)
    assert result_dict["max_tokens"] == 5000  # From config
    assert result_dict["min_relevance_score"] == 0.6  # From config


# ============================================================================
# Test build_get_relevant_response
# ============================================================================


def test_build_get_relevant_response() -> None:
    """Test build_get_relevant_response constructs correct JSON."""
    # Arrange
    all_rules: list[ModelDict] = [
        {"file": "test1.mdc", "tokens": 500},
        {"file": "test2.mdc", "tokens": 700},
    ]
    status = RulesManagerStatusModel(
        enabled=True,
        rules_folder=".cursor/rules",
        indexed_files=42,
        last_indexed="2026-01-04T10:30:00Z",
        total_tokens=15234,
    )
    relevant_rules_dict: ModelDict = {
        "context": {"filtered_count": 5},
        "source": "indexed",
    }
    all_rules: list[ModelDict] = [
        {"id": 1, "tokens": 100},
        {"id": 2, "tokens": 200},
    ]

    # Act
    result = build_get_relevant_response(
        "Test task",
        5000,
        0.7,
        all_rules,
        1200,
        status,
        relevant_rules_dict,
    )

    # Assert
    result_dict = json.loads(result)
    assert result_dict["status"] == "success"
    assert result_dict["operation"] == "get_relevant"
    assert result_dict["task_description"] == "Test task"
    assert result_dict["max_tokens"] == 5000
    assert result_dict["min_relevance_score"] == 0.7
    assert result_dict["rules_count"] == 2
    assert result_dict["total_tokens"] == 1200
    assert result_dict["rules"] == all_rules
    assert result_dict["rules_manager_status"]["indexed_files"] == 42
    assert result_dict["rules_context"] == {"filtered_count": 5}
    assert result_dict["rules_source"] == "indexed"


# ============================================================================
# Test dispatch_operation
# ============================================================================


@pytest.mark.asyncio
async def test_dispatch_operation_index(
    mock_rules_manager: MagicMock, mock_optimization_config_enabled: MagicMock
) -> None:
    """Test dispatch_operation with index operation."""
    # Act
    result = await dispatch_operation(
        "index",
        mock_rules_manager,
        mock_optimization_config_enabled,
        False,
        None,
        None,
        None,
    )

    # Assert
    result_dict = json.loads(result)
    assert result_dict["status"] == "success"
    assert result_dict["operation"] == "index"
    mock_rules_manager.index_rules.assert_called_once_with(force=False)


@pytest.mark.asyncio
async def test_dispatch_operation_get_relevant(
    mock_rules_manager: MagicMock, mock_optimization_config_enabled: MagicMock
) -> None:
    """Test dispatch_operation with get_relevant operation."""
    # Act
    result = await dispatch_operation(
        "get_relevant",
        mock_rules_manager,
        mock_optimization_config_enabled,
        False,
        "Test task",
        5000,
        0.7,
    )

    # Assert
    result_dict = json.loads(result)
    assert result_dict["status"] == "success"
    assert result_dict["operation"] == "get_relevant"
    mock_rules_manager.get_relevant_rules.assert_called_once()


@pytest.mark.asyncio
async def test_dispatch_operation_get_relevant_missing_task(
    mock_rules_manager: MagicMock, mock_optimization_config_enabled: MagicMock
) -> None:
    """Test dispatch_operation get_relevant without task_description."""
    # Act
    result = await dispatch_operation(
        "get_relevant",
        mock_rules_manager,
        mock_optimization_config_enabled,
        False,
        None,  # Missing task_description
        5000,
        0.7,
    )

    # Assert
    result_dict = json.loads(result)
    assert result_dict["status"] == "error"
    assert "required" in result_dict["error"].lower()
    mock_rules_manager.get_relevant_rules.assert_not_called()


@pytest.mark.asyncio
async def test_dispatch_operation_invalid(
    mock_rules_manager: MagicMock, mock_optimization_config_enabled: MagicMock
) -> None:
    """Test dispatch_operation with invalid operation."""
    # Act
    result = await dispatch_operation(
        "invalid_operation",  # type: ignore[arg-type]
        mock_rules_manager,
        mock_optimization_config_enabled,
        False,
        None,
        None,
        None,
    )

    # Assert
    result_dict = json.loads(result)
    assert result_dict["status"] == "error"
    assert "invalid" in result_dict["error"].lower()
    assert "valid_operations" in result_dict


# ============================================================================
# Test rules() main tool function
# ============================================================================


@pytest.mark.asyncio
async def test_rules_index_operation_success(
    mock_managers_enabled: dict[str, Any], mock_project_root: Path
) -> None:
    """Test rules() with index operation."""
    # Arrange
    with (
        patch(
            "cortex.tools.rules_operations.get_project_root",
            return_value=mock_project_root,
        ),
        patch(
            "cortex.tools.rules_operations.get_managers",
            AsyncMock(return_value=mock_managers_enabled),
        ),
    ):
        # Act
        result = await rules(
            operation="index", project_root=str(mock_project_root), force=False
        )

        # Assert
        result_dict = json.loads(result)
        assert result_dict["status"] == "success"
        assert result_dict["operation"] == "index"
        assert result_dict["result"]["indexed"] == 42


@pytest.mark.asyncio
async def test_rules_index_operation_force(
    mock_managers_enabled: dict[str, Any], mock_project_root: Path
) -> None:
    """Test rules() with index operation and force=True."""
    # Arrange
    with (
        patch(
            "cortex.tools.rules_operations.get_project_root",
            return_value=mock_project_root,
        ),
        patch(
            "cortex.tools.rules_operations.get_managers",
            AsyncMock(return_value=mock_managers_enabled),
        ),
    ):
        # Act
        result = await rules(
            operation="index", project_root=str(mock_project_root), force=True
        )

        # Assert
        result_dict = json.loads(result)
        assert result_dict["status"] == "success"
        managers = cast(ManagersDict, mock_managers_enabled)
        assert managers.rules_manager is not None
        if hasattr(managers.rules_manager, "index_rules"):
            managers.rules_manager.index_rules.assert_called_with(force=True)  # type: ignore


@pytest.mark.asyncio
async def test_rules_get_relevant_operation_success(
    mock_managers_enabled: dict[str, Any], mock_project_root: Path
) -> None:
    """Test rules() with get_relevant operation."""
    # Arrange
    with (
        patch(
            "cortex.tools.rules_operations.get_project_root",
            return_value=mock_project_root,
        ),
        patch(
            "cortex.tools.rules_operations.get_managers",
            AsyncMock(return_value=mock_managers_enabled),
        ),
    ):
        # Act
        result = await rules(
            operation="get_relevant",
            project_root=str(mock_project_root),
            task_description="Implementing async file operations",
            max_tokens=5000,
            min_relevance_score=0.7,
        )

        # Assert
        result_dict = json.loads(result)
        assert result_dict["status"] == "success"
        assert result_dict["operation"] == "get_relevant"
        assert result_dict["rules_count"] == 2


@pytest.mark.asyncio
async def test_rules_get_relevant_defaults(
    mock_managers_enabled: dict[str, Any], mock_project_root: Path
) -> None:
    """Test rules() get_relevant with default max_tokens/min_score."""
    # Arrange
    with (
        patch(
            "cortex.tools.rules_operations.get_project_root",
            return_value=mock_project_root,
        ),
        patch(
            "cortex.tools.rules_operations.get_managers",
            AsyncMock(return_value=mock_managers_enabled),
        ),
    ):
        # Act
        result = await rules(
            operation="get_relevant",
            project_root=str(mock_project_root),
            task_description="Test task",
        )

        # Assert
        result_dict = json.loads(result)
        assert result_dict["max_tokens"] == 5000  # From config
        assert result_dict["min_relevance_score"] == 0.6  # From config


@pytest.mark.asyncio
async def test_rules_disabled(
    mock_managers_disabled: dict[str, Any], mock_project_root: Path
) -> None:
    """Test rules() when rules are disabled."""
    # Arrange
    with (
        patch(
            "cortex.tools.rules_operations.get_project_root",
            return_value=mock_project_root,
        ),
        patch(
            "cortex.tools.rules_operations.get_managers",
            AsyncMock(return_value=mock_managers_disabled),
        ),
    ):
        # Act
        result = await rules(operation="index", project_root=str(mock_project_root))

        # Assert
        result_dict = json.loads(result)
        assert result_dict["status"] == "disabled"
        assert "disabled" in result_dict["message"].lower()


@pytest.mark.asyncio
async def test_rules_get_relevant_missing_task(
    mock_managers_enabled: dict[str, Any], mock_project_root: Path
) -> None:
    """Test rules() get_relevant without task_description."""
    # Arrange
    with (
        patch(
            "cortex.tools.rules_operations.get_project_root",
            return_value=mock_project_root,
        ),
        patch(
            "cortex.tools.rules_operations.get_managers",
            AsyncMock(return_value=mock_managers_enabled),
        ),
    ):
        # Act
        result = await rules(
            operation="get_relevant", project_root=str(mock_project_root)
        )

        # Assert
        result_dict = json.loads(result)
        assert result_dict["status"] == "error"
        assert "required" in result_dict["error"].lower()


@pytest.mark.asyncio
async def test_rules_exception_handling(mock_project_root: Path) -> None:
    """Test rules() exception handling."""
    # Arrange
    with (
        patch(
            "cortex.tools.rules_operations.get_project_root",
            return_value=mock_project_root,
        ),
        patch(
            "cortex.tools.rules_operations.get_managers",
            AsyncMock(side_effect=ValueError("Test error")),
        ),
    ):
        # Act
        result = await rules(operation="index", project_root=str(mock_project_root))

        # Assert
        result_dict = json.loads(result)
        assert result_dict["status"] == "error"
        assert result_dict["error"] == "Test error"
        assert result_dict["error_type"] == "ValueError"


@pytest.mark.asyncio
async def test_rules_default_project_root(
    mock_managers_enabled: dict[str, Any],
) -> None:
    """Test rules() with default project_root (None)."""
    # Arrange
    with (
        patch(
            "cortex.tools.rules_operations.get_project_root",
            return_value=Path.cwd(),
        ) as mock_get_root,
        patch(
            "cortex.tools.rules_operations.get_managers",
            AsyncMock(return_value=mock_managers_enabled),
        ),
    ):
        # Act
        result = await rules(operation="index")

        # Assert
        result_dict = json.loads(result)
        assert result_dict["status"] == "success"
        mock_get_root.assert_called_once_with(None)
