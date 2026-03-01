"""Unit tests for execution_handlers.

Tests handler functions with missing params and validation_failed path
to improve coverage of execution_handlers.py.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cortex.managers.types import ManagersDict
from cortex.tools.execution_handlers import (
    handle_apply_action,
    handle_approve_action,
    handle_rollback_action,
)


@pytest.fixture
def mock_mgrs() -> ManagersDict:
    """Minimal mock managers for handler tests."""
    return MagicMock(spec=ManagersDict)


class TestHandleApproveActionMissingParam:
    """Tests for handle_approve_action with missing suggestion_id."""

    @pytest.mark.asyncio
    async def test_missing_suggestion_id_returns_error_json(
        self, mock_mgrs: ManagersDict
    ) -> None:
        """Missing suggestion_id returns create_missing_param_error JSON."""
        result = await handle_approve_action(
            mock_mgrs, suggestion_id=None, user_comment=None, auto_apply=False
        )
        data = json.loads(result)
        assert data["status"] == "error"
        assert "suggestion_id" in data.get("suggestion", "")
        assert "example" in data


class TestHandleApplyActionMissingParams:
    """Tests for handle_apply_action with missing params."""

    @pytest.mark.asyncio
    async def test_missing_suggestion_id_returns_error_json(
        self, mock_mgrs: ManagersDict
    ) -> None:
        """Missing suggestion_id returns create_missing_param_error JSON."""
        result = await handle_apply_action(
            mock_mgrs,
            suggestion_id=None,
            approval_id="approval-123",
            dry_run=False,
            validate_first=True,
        )
        data = json.loads(result)
        assert data["status"] == "error"
        assert "suggestion_id" in data.get("suggestion", "")
        assert "example" in data

    @pytest.mark.asyncio
    async def test_missing_approval_id_returns_error_json(
        self, mock_mgrs: ManagersDict
    ) -> None:
        """Missing approval_id returns create_missing_param_error JSON."""
        result = await handle_apply_action(
            mock_mgrs,
            suggestion_id="suggestion-123",
            approval_id=None,
            dry_run=False,
            validate_first=True,
        )
        data = json.loads(result)
        assert data["status"] == "error"
        assert "approval_id" in data.get("suggestion", "")
        assert "example" in data


class TestHandleRollbackActionMissingParam:
    """Tests for handle_rollback_action with missing execution_id."""

    @pytest.mark.asyncio
    async def test_missing_execution_id_returns_error_json(
        self, mock_mgrs: ManagersDict
    ) -> None:
        """Missing execution_id returns create_missing_param_error JSON."""
        result = await handle_rollback_action(
            mock_mgrs,
            execution_id=None,
            restore_snapshot=True,
            preserve_manual_changes=True,
            dry_run=False,
        )
        data = json.loads(result)
        assert data["status"] == "error"
        assert "execution_id" in data.get("suggestion", "")
        assert "example" in data


class TestHandleApplyActionSuggestionNotFound:
    """Tests for handle_apply_action when suggestion is not found."""

    @pytest.mark.asyncio
    async def test_suggestion_not_found_returns_validation_failed(
        self, mock_mgrs: ManagersDict
    ) -> None:
        """When get_suggestion returns None, result status is validation_failed."""
        from cortex.tools.execution_handlers import handle_apply_action

        async def get_manager_wrapper(*args: object, **kwargs: object) -> object:
            if args[1] == "refactoring_engine":
                engine = MagicMock()
                engine.get_suggestion = AsyncMock(return_value=None)
                return engine
            return MagicMock()

        with patch(
            "cortex.tools.execution_handlers.get_manager",
            side_effect=get_manager_wrapper,
        ):
            result_json = await handle_apply_action(
                mock_mgrs,
                suggestion_id="nonexistent",
                approval_id="approval-123",
                dry_run=False,
                validate_first=True,
            )
        data = json.loads(result_json)
        assert data["status"] == "validation_failed"
        assert data.get("error") is not None and "not found" in data["error"]
