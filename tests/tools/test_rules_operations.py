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
from cortex.managers.initialization import get_project_root
from cortex.managers.types import ManagersDict
from cortex.optimization.models import RulesManagerStatusModel
from cortex.tools.synapse.rules_operation_helpers import (
    RulesOperation,
    build_get_relevant_response,
    calculate_total_tokens,
    extract_all_rules,
    parse_rules_operation,
    resolve_config_defaults,
)
from cortex.tools.synapse.rules_operations import get_relevant_rules, rules
from cortex.tools.synapse.rules_operations_handlers import (
    check_rules_enabled,
    dispatch_operation,
    handle_get_relevant_operation,
    handle_index_operation,
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
    config.get_rules_folder.return_value = ".cortex/rules"
    config.get_rules_max_tokens.return_value = 5000
    config.get_rules_min_relevance.return_value = 0.6
    config.get_rule_priority.return_value = "local_overrides_shared"
    config.is_context_aware_loading.return_value = True
    return config


@pytest.fixture
def mock_optimization_config_disabled() -> MagicMock:
    """Create mock optimization config with rules disabled."""
    config = MagicMock()
    config.is_rules_enabled.return_value = False
    return config


@pytest.fixture
def mock_rules_manager(mock_project_root: Path) -> MagicMock:
    """Create mock rules manager."""
    manager = MagicMock()
    manager.project_root = mock_project_root
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
    manager.initialize = AsyncMock(return_value=None)
    # Mock indexer for status building
    mock_indexer = MagicMock()
    mock_indexer.get_status.return_value = RulesManagerStatusModel(
        enabled=True,
        rules_folder=None,
        indexed_files=42,
        last_indexed="2026-01-04T10:30:00Z",
        auto_reindex_enabled=True,
        reindex_interval_minutes=30.0,
        total_tokens=15234,
    )
    manager.indexer = mock_indexer
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
async def test_handle_index_operation_success(
    mock_rules_manager: MagicMock,
    mock_optimization_config_enabled: MagicMock,
    mock_project_root: Path,
) -> None:
    """Test handle_index_operation with successful indexing."""
    # Arrange: Create rules folder
    rules_folder = mock_project_root / ".cortex" / "rules"
    rules_folder.mkdir(parents=True, exist_ok=True)

    # Act
    result = await handle_index_operation(
        mock_rules_manager, mock_optimization_config_enabled, force=False
    )

    # Assert
    result_dict = json.loads(result)
    assert result_dict["status"] == "success"
    assert result_dict["operation"] == "index"
    assert result_dict["result"]["indexed"] == 42
    assert result_dict["result"]["total_tokens"] == 15234
    mock_rules_manager.index_rules.assert_called_once_with(force=False)


@pytest.mark.asyncio
async def test_handle_index_operation_with_force(
    mock_rules_manager: MagicMock,
    mock_optimization_config_enabled: MagicMock,
    mock_project_root: Path,
) -> None:
    """Test handle_index_operation with force=True."""
    # Arrange: Create rules folder
    rules_folder = mock_project_root / ".cortex" / "rules"
    rules_folder.mkdir(parents=True, exist_ok=True)

    # Act
    result = await handle_index_operation(
        mock_rules_manager, mock_optimization_config_enabled, force=True
    )

    # Assert
    result_dict = json.loads(result)
    assert result_dict["status"] == "success"
    assert result_dict["operation"] == "index"
    mock_rules_manager.index_rules.assert_called_once_with(force=True)


@pytest.mark.asyncio
async def test_handle_index_operation_missing_rules_folder(
    mock_rules_manager: MagicMock,
    mock_project_root: Path,
) -> None:
    """Test handle_index_operation fails loudly when rules folder not configured."""
    # Arrange: Config with no rules folder
    config = MagicMock()
    config.is_rules_enabled.return_value = True
    config.get_rules_folder.return_value = None

    # Act
    result = await handle_index_operation(mock_rules_manager, config, force=False)

    # Assert
    result_dict = json.loads(result)
    assert result_dict["status"] == "error"
    assert "Rules folder not configured" in result_dict["error"]
    assert "suggestion" in result_dict
    mock_rules_manager.index_rules.assert_not_called()


@pytest.mark.asyncio
async def test_handle_index_operation_rules_folder_not_found(
    mock_rules_manager: MagicMock,
    mock_optimization_config_enabled: MagicMock,
    mock_project_root: Path,
) -> None:
    """Test handle_index_operation fails loudly when rules folder doesn't exist."""
    # Arrange: Rules folder doesn't exist
    # (mock_project_root is empty)
    # Make index_rules return error for when it's called after folder check passes
    mock_rules_manager.index_rules.return_value = {
        "status": "error",
        "error": "Rules folder not found: .cortex/rules",
        "message": "Rules folder not found: .cortex/rules",
    }

    # Act
    result = await handle_index_operation(
        mock_rules_manager, mock_optimization_config_enabled, force=False
    )

    # Assert: Should return error (either from validation or from index_rules)
    result_dict = json.loads(result)
    assert result_dict["status"] == "error"
    assert (
        "Rules folder not found" in result_dict["error"]
        or "not found" in result_dict["error"].lower()
    )
    # index_rules may or may not be called depending on validation order


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


def test_parse_rules_operation_returns_none_for_none() -> None:
    """parse_rules_operation(None) returns None."""
    assert parse_rules_operation(None) is None


def test_parse_rules_operation_returns_enum_for_valid_values() -> None:
    """parse_rules_operation returns RulesOperation for valid strings."""
    assert parse_rules_operation("index") is RulesOperation.INDEX
    assert parse_rules_operation("get_relevant") is RulesOperation.GET_RELEVANT


def test_parse_rules_operation_returns_none_for_invalid_value() -> None:
    """parse_rules_operation returns None for invalid string."""
    assert parse_rules_operation("invalid") is None
    assert parse_rules_operation("") is None


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
async def test_handle_get_relevant_operation_missing_rules_folder(
    mock_rules_manager: MagicMock,
    mock_project_root: Path,
) -> None:
    """Test handle_get_relevant_operation fails loudly when rules folder not configured."""
    # Arrange: Config with no rules folder
    config = MagicMock()
    config.is_rules_enabled.return_value = True
    config.get_rules_folder.return_value = None
    config.get_rule_priority.return_value = "local_overrides_shared"
    config.is_context_aware_loading.return_value = True

    # Act
    result = await handle_get_relevant_operation(
        mock_rules_manager,
        config,
        task_description="Test task",
        max_tokens=None,
        min_relevance_score=None,
    )

    # Assert
    result_dict = json.loads(result)
    assert result_dict["status"] == "error"
    assert "Rules folder not configured" in result_dict["error"]
    assert "suggestion" in result_dict
    mock_rules_manager.get_relevant_rules.assert_not_called()


@pytest.mark.asyncio
async def test_handle_get_relevant_operation_rules_folder_not_found(
    mock_rules_manager: MagicMock,
    mock_optimization_config_enabled: MagicMock,
    mock_project_root: Path,
) -> None:
    """Test handle_get_relevant_operation fails loudly when rules folder doesn't exist."""
    # Arrange: Rules folder doesn't exist
    # (mock_project_root is empty)
    mock_optimization_config_enabled.get_rule_priority.return_value = (
        "local_overrides_shared"
    )
    mock_optimization_config_enabled.is_context_aware_loading.return_value = True

    # Act
    result = await handle_get_relevant_operation(
        mock_rules_manager,
        mock_optimization_config_enabled,
        task_description="Test task",
        max_tokens=None,
        min_relevance_score=None,
    )

    # Assert
    result_dict = json.loads(result)
    assert result_dict["status"] == "error"
    assert "not found" in result_dict["error"].lower()
    assert "suggestion" in result_dict
    mock_rules_manager.get_relevant_rules.assert_not_called()


@pytest.mark.asyncio
async def test_handle_get_relevant_operation_success(
    mock_rules_manager: MagicMock,
    mock_optimization_config_enabled: MagicMock,
    mock_project_root: Path,
) -> None:
    """Test handle_get_relevant_operation with successful retrieval."""
    # Arrange: Create rules folder
    rules_folder = mock_project_root / ".cortex" / "rules"
    rules_folder.mkdir(parents=True, exist_ok=True)
    mock_optimization_config_enabled.get_rule_priority.return_value = (
        "local_overrides_shared"
    )
    mock_optimization_config_enabled.is_context_aware_loading.return_value = True

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
    mock_rules_manager: MagicMock,
    mock_optimization_config_enabled: MagicMock,
    mock_project_root: Path,
) -> None:
    """Test handle_get_relevant_operation with default parameters."""
    # Arrange: Create rules folder
    rules_folder = mock_project_root / ".cortex" / "rules"
    rules_folder.mkdir(parents=True, exist_ok=True)
    mock_optimization_config_enabled.get_rule_priority.return_value = (
        "local_overrides_shared"
    )
    mock_optimization_config_enabled.is_context_aware_loading.return_value = True

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


@pytest.mark.asyncio
async def test_handle_get_relevant_operation_status_reflects_current_config(
    mock_rules_manager: MagicMock,
    mock_optimization_config_enabled: MagicMock,
    mock_project_root: Path,
) -> None:
    """Test that status reflects current config value, not stale manager initialization.

    This test verifies Step 1 fix: rules manager status should use current
    optimization.rules.rules_folder, not the value from initialization.
    """
    # Arrange: Create rules folder
    rules_folder = mock_project_root / ".cortex" / "rules"
    rules_folder.mkdir(parents=True, exist_ok=True)
    mock_optimization_config_enabled.get_rule_priority.return_value = (
        "local_overrides_shared"
    )
    mock_optimization_config_enabled.is_context_aware_loading.return_value = True
    mock_optimization_config_enabled.get_rules_reindex_interval.return_value = 30

    # Mock indexer.get_status() (used by _build_status_from_config)
    mock_indexer = MagicMock()
    mock_indexer.get_status.return_value = RulesManagerStatusModel(
        enabled=True,
        rules_folder=None,  # Indexer doesn't store folder
        indexed_files=42,
        last_indexed="2026-01-04T10:30:00Z",
        auto_reindex_enabled=True,
        reindex_interval_minutes=30.0,
        total_tokens=15234,
    )
    mock_rules_manager.indexer = mock_indexer

    # Configure config to return different folder than manager's stale status
    # (simulating config update after manager initialization)
    mock_optimization_config_enabled.get_rules_folder.return_value = ".cortex/rules"
    # Manager's get_status() returns stale value (simulating old initialization)
    mock_rules_manager.get_status.return_value = RulesManagerStatusModel(
        enabled=True,
        rules_folder=".cursorrules",  # Stale value
        indexed_files=42,
        last_indexed="2026-01-04T10:30:00Z",
        total_tokens=15234,
    )

    # Act
    result = await handle_get_relevant_operation(
        mock_rules_manager,
        mock_optimization_config_enabled,
        "Test task",
        5000,
        0.7,
    )

    # Assert: Status should reflect current config (.cortex/rules), not stale (.cursorrules)
    result_dict = json.loads(result)
    assert result_dict["status"] == "success"
    status = result_dict["rules_manager_status"]
    assert status["rules_folder"] == ".cortex/rules"  # Current config value
    assert status["rules_folder"] != ".cursorrules"  # Not stale value


# ============================================================================
# Test build_get_relevant_response
# ============================================================================


def test_build_get_relevant_response() -> None:
    """Test build_get_relevant_response constructs correct JSON."""
    # Arrange
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
        RulesOperation.INDEX,
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
    mock_rules_manager: MagicMock,
    mock_optimization_config_enabled: MagicMock,
    mock_project_root: Path,
) -> None:
    """Test dispatch_operation with get_relevant operation."""
    # Arrange: Create rules folder
    rules_folder = mock_project_root / ".cortex" / "rules"
    rules_folder.mkdir(parents=True, exist_ok=True)
    mock_optimization_config_enabled.get_rule_priority.return_value = (
        "local_overrides_shared"
    )
    mock_optimization_config_enabled.is_context_aware_loading.return_value = True

    # Act
    result = await dispatch_operation(
        RulesOperation.GET_RELEVANT,
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
        RulesOperation.GET_RELEVANT,
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
async def test_rules_invalid_operation_returns_error(
    mock_managers_enabled: dict[str, Any], mock_project_root: Path
) -> None:
    """Test rules() with invalid operation returns friendly error."""
    # Act: invalid operation is rejected at parse before dispatch_operation
    result = await rules(operation="invalid_operation")

    # Assert
    result_dict = json.loads(result)
    assert result_dict["status"] == "error"
    assert "invalid" in result_dict["error"].lower()
    assert "available_options" in result_dict
    assert "suggestion" in result_dict


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
            "cortex.tools.rules_operations.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=mock_project_root,
        ),
        patch(
            "cortex.tools.rules_operations.get_managers",
            AsyncMock(return_value=mock_managers_enabled),
        ),
    ):
        # Act
        result = await rules(operation="index", force=False)

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
            "cortex.tools.rules_operations.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=mock_project_root,
        ),
        patch(
            "cortex.tools.rules_operations.get_managers",
            AsyncMock(return_value=mock_managers_enabled),
        ),
    ):
        # Act
        result = await rules(operation="index", force=True)

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
    # Arrange: Create rules folder
    rules_folder = mock_project_root / ".cortex" / "rules"
    rules_folder.mkdir(parents=True, exist_ok=True)
    with (
        patch(
            "cortex.tools.rules_operations.resolve_project_root_async",
            new_callable=AsyncMock,
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
    # Arrange: Create rules folder
    rules_folder = mock_project_root / ".cortex" / "rules"
    rules_folder.mkdir(parents=True, exist_ok=True)
    with (
        patch(
            "cortex.tools.rules_operations.resolve_project_root_async",
            new_callable=AsyncMock,
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
            task_description="Test task",
        )

        # Assert
        result_dict = json.loads(result)
        assert result_dict["max_tokens"] == 5000  # From config
        assert result_dict["min_relevance_score"] == 0.6  # From config


@pytest.mark.asyncio
async def test_get_relevant_rules_returns_json(
    mock_managers_enabled: dict[str, Any], mock_project_root: Path
) -> None:
    """get_relevant_rules returns JSON (zero-arg, session config)."""
    # Arrange: Create rules folder
    rules_folder = mock_project_root / ".cortex" / "rules"
    rules_folder.mkdir(parents=True, exist_ok=True)
    with (
        patch(
            "cortex.core.session_config.read_session_config",
            return_value={"task_description": "Implementing async file operations"},
        ),
        patch(
            "cortex.tools.rules_operations.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=mock_project_root,
        ),
        patch(
            "cortex.tools.rules_operations.get_managers",
            AsyncMock(return_value=mock_managers_enabled),
        ),
    ):
        result_str = await get_relevant_rules()
    result_dict = json.loads(result_str)
    assert result_dict["status"] == "success"
    assert result_dict["operation"] == "get_relevant"
    assert "Implementing async file operations" in result_dict.get(
        "task_description", ""
    )


@pytest.mark.asyncio
async def test_rules_disabled(
    mock_managers_disabled: dict[str, Any], mock_project_root: Path
) -> None:
    """Test rules() when rules are disabled."""
    # Arrange
    with (
        patch(
            "cortex.tools.rules_operations.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=mock_project_root,
        ),
        patch(
            "cortex.tools.rules_operations.get_managers",
            AsyncMock(return_value=mock_managers_disabled),
        ),
    ):
        # Act
        result = await rules(operation="index")

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
            "cortex.tools.rules_operations.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=mock_project_root,
        ),
        patch(
            "cortex.tools.rules_operations.get_managers",
            AsyncMock(return_value=mock_managers_enabled),
        ),
    ):
        # Act
        result = await rules(operation="get_relevant")

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
            "cortex.tools.rules_operations.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=mock_project_root,
        ),
        patch(
            "cortex.tools.rules_operations.get_managers",
            AsyncMock(side_effect=ValueError("Test error")),
        ),
    ):
        # Act
        result = await rules(operation="index")

        # Assert
        result_dict = json.loads(result)
        assert result_dict["status"] == "error"
        assert result_dict["error"] == "Test error"
        assert result_dict["error_type"] == "ValueError"


@pytest.mark.asyncio
async def test_rules_default_project_root(
    mock_managers_enabled: dict[str, Any],
) -> None:
    """Test rules() resolves project root via resolve_project_root_async."""
    # Arrange
    with (
        patch(
            "cortex.tools.rules_operations.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=Path.cwd(),
        ) as mock_resolve_root,
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
        mock_resolve_root.assert_called_once()
        assert mock_resolve_root.call_args[0][0] is None


@pytest.mark.asyncio
async def test_rules_zero_arg_defaults_to_get_relevant(
    mock_managers_enabled: dict[str, Any],
) -> None:
    """rules() with no args defaults to get_relevant with fallback task description."""
    # Arrange
    with (
        patch(
            "cortex.tools.rules_operations.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=Path("/tmp/test"),
        ),
        patch(
            "cortex.tools.rules_operations.get_managers",
            AsyncMock(return_value=mock_managers_enabled),
        ),
    ):
        # Act — zero-arg call should default to get_relevant, not error
        result = await rules()  # type: ignore[call-arg]

        # Assert — should attempt get_relevant (may fail due to env, but not missing-param)
        result_dict = json.loads(result)
        assert "missing required parameter" not in result_dict.get("error", "").lower()


# ============================================================================
# Test rules Context logging (FastMCP)
# ============================================================================


class TestRulesContextLogging:
    """Test rules tool Context logging (FastMCP)."""

    @pytest.mark.asyncio
    async def test_rules_calls_log_client_on_start_and_completion_when_ctx_passed(
        self,
        mock_managers_enabled: dict[str, Any],
    ) -> None:
        """When ctx is passed, rules logs start and completion via log_client."""
        # Arrange
        mock_ctx = AsyncMock()
        with (
            patch(
                "cortex.tools.rules_operations.log_client",
                new_callable=AsyncMock,
            ) as mock_log,
            patch(
                "cortex.tools.rules_operations.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=Path("/tmp/test"),
            ),
            patch(
                "cortex.tools.rules_operations.get_managers",
                AsyncMock(return_value=mock_managers_enabled),
            ),
        ):
            # Act
            result = await rules(operation="index", ctx=mock_ctx)

            # Assert
            assert json.loads(result)["status"] == "success"
            args_list = [c[0] for c in mock_log.call_args_list]
            levels_and_messages = [(a[1], a[2]) for a in args_list]
            assert ("info", "rules: starting") in levels_and_messages
            assert ("info", "rules: completed") in levels_and_messages

    @pytest.mark.asyncio
    async def test_rules_calls_log_client_warning_on_invalid_operation_when_ctx_passed(
        self,
    ) -> None:
        """When operation is invalid and ctx is passed, rules logs warning."""
        # Arrange
        mock_ctx = AsyncMock()
        with patch(
            "cortex.tools.rules_operations.log_client",
            new_callable=AsyncMock,
        ) as mock_log:
            # Act
            result = await rules(operation="invalid_op", ctx=mock_ctx)

            # Assert
            result_data = json.loads(result)
            assert "error" in result_data or "status" in result_data
            assert any(
                c[0][1] == "warning"
                and c[0][2] == "rules: invalid or missing operation"
                for c in mock_log.call_args_list
                if len(c[0]) >= 3
            )

    @pytest.mark.asyncio
    async def test_rules_calls_log_client_error_on_exception_when_ctx_passed(
        self,
    ) -> None:
        """When _execute_rules_operation raises and ctx is passed, rules logs error."""
        # Arrange
        mock_ctx = AsyncMock()
        with (
            patch(
                "cortex.tools.rules_operations.log_client",
                new_callable=AsyncMock,
            ) as mock_log,
            patch(
                "cortex.tools.rules_operations.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=Path("/tmp/test"),
            ),
            patch(
                "cortex.tools.rules_operations.get_managers",
                new_callable=AsyncMock,
                side_effect=RuntimeError("Setup failed"),
            ),
        ):
            # Act
            result = await rules(operation="index", ctx=mock_ctx)

            # Assert
            result_data = json.loads(result)
            assert result_data.get("status") == "error"
            assert any(
                c[0][1] == "error" and "rules: failed:" in str(c[0][2])
                for c in mock_log.call_args_list
                if len(c[0]) >= 3
            )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_rules_get_relevant_returns_at_least_one_rule_for_commit_pipeline() -> (
    None
):
    """Integration: rules(get_relevant, 'Commit pipeline, test coverage') returns >= 1 rule when rules present.

    Ensures rules indexing is effective for commit/analyze workflows.
    Uses real project root and real managers when .cortex/rules exists.
    """
    project_root = get_project_root()
    rules_dir = project_root / ".cortex" / "rules"
    if not rules_dir.exists():
        pytest.skip(
            reason=".cortex/rules not present (ref: cleanup-skipped-legacy-tests)"
        )
    rule_files = list(rules_dir.rglob("*.mdc")) if rules_dir.is_dir() else []
    if not rule_files:
        pytest.skip(
            reason=".cortex/rules has no .mdc files (ref: cleanup-skipped-legacy-tests)"
        )

    async def _return_project_root(_: object, __: object) -> Path:
        return project_root

    with patch(
        "cortex.tools.rules_operations.resolve_project_root_async",
        new_callable=AsyncMock,
        side_effect=_return_project_root,
    ):
        # Index first so get_relevant can return from index
        index_result = await rules(operation="index", force=True)
        index_data = json.loads(index_result)
        if index_data.get("status") == "disabled":
            pytest.skip(
                reason="Rules indexing disabled in config (ref: cleanup-skipped-legacy-tests)"
            )

        get_result = await rules(
            operation="get_relevant",
            task_description="Commit pipeline, test coverage",
            min_relevance_score=0.1,
        )
    get_data = json.loads(get_result)
    assert get_data.get("status") == "success", get_data
    rules_count = get_data.get("rules_count", 0)
    rules_list = get_data.get("rules", [])
    assert rules_count >= 1 or len(rules_list) >= 1, (
        "rules() should return at least one rule for 'Commit pipeline, test coverage' "
        "when rules are present and indexed"
    )
