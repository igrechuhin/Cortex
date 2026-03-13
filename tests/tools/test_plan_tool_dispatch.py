"""
Tests for the unified plan MCP tool dispatcher.

Focus: argument validation/guardrails for operation and required fields.
"""

import json

import pytest

from cortex.tools.plans.plan import plan


class TestPlanToolOperationValidation:
    """Validation for operation argument."""

    @pytest.mark.asyncio
    async def test_no_arguments_returns_missing_operation_error(self) -> None:
        """Calling plan() with no arguments returns clear missing-operation error."""
        result_str = await plan()
        result = json.loads(result_str)
        assert result["status"] == "error"
        # Message should mention that operation is required and list expected values.
        message = (result.get("message") or "").lower()
        assert "operation is required" in message
        assert "create" in message
        assert "complete" in message

    @pytest.mark.asyncio
    async def test_invalid_operation_returns_invalid_operation_error(self) -> None:
        """Calling plan(operation='unknown') returns invalid-operation error."""
        result_str = await plan(operation="unknown")
        result = json.loads(result_str)
        assert result["status"] == "error"
        message = (result.get("message") or "").lower()
        assert "invalid operation" in message
        assert "unknown" in message


class TestPlanToolRequiredFieldValidation:
    """Validation for required fields per operation."""

    @pytest.mark.asyncio
    async def test_complete_missing_plan_title_and_summary(self) -> None:
        """plan(operation='complete') without plan_title/summary returns clear error."""
        result_str = await plan(operation="complete")
        result = json.loads(result_str)
        assert result["status"] == "error"
        message = (result.get("message") or "").lower()
        assert "plan_title and summary are required" in message

    @pytest.mark.asyncio
    async def test_register_missing_plan_title_and_description(self) -> None:
        """plan(operation='register') without plan_title/description returns clear error."""
        result_str = await plan(operation="register")
        result = json.loads(result_str)
        assert result["status"] == "error"
        message = (result.get("message") or "").lower()
        assert "plan_title and description are required" in message

    @pytest.mark.asyncio
    async def test_create_missing_title_and_content(self) -> None:
        """plan(operation='create') without title/content returns clear error."""
        result_str = await plan(operation="create")
        result = json.loads(result_str)
        assert result["status"] == "error"
        message = (result.get("message") or "").lower()
        assert "title and content are required" in message


class TestPlanToolHappyPath:
    """Happy-path: plan() with full payload for operations that need no extra args."""

    @pytest.mark.asyncio
    async def test_plan_operation_list_returns_success(self) -> None:
        """plan(operation='list') with no other required args returns success and plans list."""
        result_str = await plan(operation="list")
        result = json.loads(result_str)
        assert result.get("status") == "success"
        assert "plans" in result
        assert isinstance(result["plans"], list)
